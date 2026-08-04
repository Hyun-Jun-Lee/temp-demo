import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["DA_OPS_DB_PATH"] = str(Path(_TEMP_DIR.name) / "test.sqlite3")

from src.core.demo_scenarios import select_demo_scenario  # noqa: E402
from src.core.report_charts import build_report_charts  # noqa: E402
from src.core.run_repository import (  # noqa: E402
    get_report_chat_messages,
    init_db,
    save_report,
    save_report_chat_message,
)
from src.nodes.global_health_node import (  # noqa: E402
    fetch_global_health_overview,
    target_nodes_from_warning_signals,
)
from src.main import ReportChatResult, app  # noqa: E402
import src.main as main_module  # noqa: E402


class ReportFeatureTest(unittest.TestCase):
    def setUp(self) -> None:
        db_path = Path(os.environ["DA_OPS_DB_PATH"])
        if db_path.exists():
            db_path.unlink()
        init_db()

    def test_report_chat_messages_persist_metadata_in_order(self) -> None:
        save_report_chat_message("run-1", "user", "OS 상태는?")
        save_report_chat_message(
            "run-1",
            "assistant",
            "OS 부하 경고입니다.",
            metadata={"cited_nodes": ["os"], "confidence_score": 91},
        )

        messages = get_report_chat_messages("run-1")

        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[1]["metadata"]["cited_nodes"], ["os"])
        self.assertEqual(messages[1]["metadata"]["confidence_score"], 91)

    def test_build_report_charts_tolerates_missing_nodes(self) -> None:
        charts = build_report_charts(
            {
                "node_result": [
                    {
                        "node": "summary",
                        "result": {"overall_score": 42},
                    },
                    {
                        "node": "memory",
                        "result": {
                            "severity_score": 12,
                            "key_metrics": {
                                "shared_pool_free_pct": 44.5,
                                "library_cache_hit_ratio": 98.2,
                            },
                        },
                    },
                ]
            }
        )

        chart_ids = [chart["id"] for chart in charts]

        self.assertIn("risk_scores", chart_ids)
        self.assertIn("memory_metrics", chart_ids)
        self.assertNotIn("os_cluster_metrics", chart_ids)

    def test_build_report_charts_supports_multiple_chart_types(self) -> None:
        charts = build_report_charts(
            {
                "node_result": [
                    {
                        "node": "memory",
                        "result": {
                            "metric_timeseries": {
                                "shared_pool_free_mb": [
                                    {"time": "09:50", "value": 180},
                                    {"time": "09:55", "value": 140},
                                    {"time": "10:00", "value": 96},
                                ],
                            },
                            "memory_breakdown": {
                                "used_mb": 774,
                                "free_mb": 96,
                                "reserved_used_mb": 154,
                            },
                        },
                    },
                    {
                        "node": "os",
                        "result": {
                            "resource_timeseries": {
                                "cpu_util_pct": [
                                    {"time": "09:50", "value": 60},
                                    {"time": "09:55", "value": 78},
                                    {"time": "10:00", "value": 86},
                                ],
                                "memory_util_pct": [
                                    {"time": "09:50", "value": 70},
                                    {"time": "09:55", "value": 82},
                                    {"time": "10:00", "value": 84},
                                ],
                            },
                            "bottleneck_distribution": {
                                "CPU": 3,
                                "Memory": 2,
                                "Paging": 1,
                            },
                        },
                    },
                    {
                        "node": "tempspace",
                        "result": {
                            "key_metrics": {"temp_used_pct": 87.7},
                            "temp_usage_timeseries": {
                                "temp_used_pct": [
                                    {"time": "09:50", "value": 52.4},
                                    {"time": "09:55", "value": 68.1},
                                    {"time": "10:00", "value": 87.7},
                                ],
                            },
                            "temp_space_breakdown": {
                                "used_mb": 28736,
                                "free_mb": 4032,
                            },
                        },
                    },
                    {
                        "node": "log_write",
                        "result": {
                            "key_metrics": {"log_file_sync_avg_ms": 31.2},
                            "redo_write_timeseries": {
                                "redo_mb_per_sec": [
                                    {"time": "09:50", "value": 72.6},
                                    {"time": "09:55", "value": 86.8},
                                    {"time": "10:00", "value": 92.4},
                                ],
                            },
                            "wait_event_distribution": {
                                "log file sync": 568000,
                                "log file parallel write": 214000,
                            },
                        },
                    },
                ]
            }
        )

        chart_types = {chart["id"]: chart["type"] for chart in charts}

        self.assertEqual(chart_types["memory_trends"], "line")
        self.assertEqual(chart_types["memory_breakdown"], "doughnut")
        self.assertEqual(chart_types["os_resource_trends"], "line")
        self.assertEqual(chart_types["os_bottleneck_distribution"], "pie")
        self.assertEqual(chart_types["tempspace_trends"], "line")
        self.assertEqual(chart_types["tempspace_breakdown"], "doughnut")
        self.assertEqual(chart_types["log_write_trends"], "line")
        self.assertEqual(chart_types["log_write_wait_distribution"], "pie")

    def test_global_health_routes_from_warning_signals(self) -> None:
        cases = {
            "memory_warning": ["memory"],
            "os_warning": ["os"],
            "memory_os_warning": ["memory", "os"],
            "tempspace_warning": ["tempspace"],
            "log_write_warning": ["log_write"],
            "tempspace_log_write_warning": ["tempspace", "log_write"],
            "mixed_warning": ["memory", "os", "tempspace", "log_write"],
        }
        original_scenario = os.environ.get("DA_OPS_DEMO_SCENARIO")

        try:
            for scenario, expected_nodes in cases.items():
                with self.subTest(scenario=scenario):
                    os.environ["DA_OPS_DEMO_SCENARIO"] = scenario
                    overview = fetch_global_health_overview("TESTDB", f"run-{scenario}")

                    self.assertEqual(
                        target_nodes_from_warning_signals(overview),
                        expected_nodes,
                    )
        finally:
            if original_scenario is None:
                os.environ.pop("DA_OPS_DEMO_SCENARIO", None)
            else:
                os.environ["DA_OPS_DEMO_SCENARIO"] = original_scenario

    def test_demo_db_names_map_to_fixed_scenarios(self) -> None:
        original_scenario = os.environ.get("DA_OPS_DEMO_SCENARIO")
        os.environ.pop("DA_OPS_DEMO_SCENARIO", None)

        try:
            self.assertEqual(select_demo_scenario("TESTDB", "run-test"), "mixed_warning")
            self.assertEqual(select_demo_scenario("APPDB", "run-app"), "normal")
            self.assertEqual(select_demo_scenario("PAYDB", "run-pay"), "memory_os_warning")
            self.assertEqual(
                select_demo_scenario("DWDB", "run-dw"),
                "tempspace_log_write_warning",
            )
            self.assertEqual(select_demo_scenario("UNKNOWNDB", "run-unknown"), "normal")
        finally:
            if original_scenario is not None:
                os.environ["DA_OPS_DEMO_SCENARIO"] = original_scenario

    def test_report_chart_and_chat_api(self) -> None:
        run_id = "run-api-1"
        save_report(
            run_id,
            {
                "run_id": run_id,
                "db_name": "TESTDB",
                "node_result": [
                    {
                        "node": "summary",
                        "result": {"overall_score": 65},
                    },
                    {
                        "node": "os",
                        "result": {
                            "severity_score": 70,
                            "cluster_metrics": {"max_cpu_util_pct": 88},
                            "instance_scores": [
                                {
                                    "HOST_NAME": "host01",
                                    "severity_score": 70,
                                    "cpu_util_pct": 88,
                                }
                            ],
                        },
                    },
                ],
            },
        )

        def fake_report_chat(*args, **kwargs):
            return ReportChatResult(
                answer="보고서 기준으로 OS 부하가 높습니다.",
                cited_nodes=["os", "summary"],
                confidence_score=88,
            )

        original_report_chat = main_module._invoke_report_chat
        main_module._invoke_report_chat = fake_report_chat
        client = TestClient(app)

        try:
            charts_response = client.get(f"/reports/{run_id}/charts")
            chat_response = client.post(
                f"/reports/{run_id}/chat",
                json={"user_question": "OS 문제 원인은?"},
            )
            history_response = client.get(f"/reports/{run_id}/chat")
        finally:
            main_module._invoke_report_chat = original_report_chat

        self.assertEqual(charts_response.status_code, 200)
        self.assertIn("risk_scores", [chart["id"] for chart in charts_response.json()["charts"]])
        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(chat_response.json()["cited_nodes"], ["os", "summary"])
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.json()["messages"]), 2)

    def test_report_chat_api_records_assistant_error_on_llm_failure(self) -> None:
        run_id = "run-api-failure"
        save_report(run_id, {"run_id": run_id, "db_name": "TESTDB", "node_result": []})

        def failing_report_chat(*args, **kwargs):
            raise RuntimeError("llm unavailable")

        original_report_chat = main_module._invoke_report_chat
        main_module._invoke_report_chat = failing_report_chat
        client = TestClient(app)

        try:
            chat_response = client.post(
                f"/reports/{run_id}/chat",
                json={"user_question": "보고서 요약해줘"},
            )
            history_response = client.get(f"/reports/{run_id}/chat")
        finally:
            main_module._invoke_report_chat = original_report_chat

        self.assertEqual(chat_response.status_code, 500)
        self.assertEqual(history_response.status_code, 200)
        messages = history_response.json()["messages"]
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[1]["metadata"]["confidence_score"], 0)
        self.assertIn("오류", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
