import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["DA_OPS_DB_PATH"] = str(Path(_TEMP_DIR.name) / "test.sqlite3")

from src.core.report_charts import build_report_charts  # noqa: E402
from src.core.run_repository import (  # noqa: E402
    get_report_chat_messages,
    init_db,
    save_report,
    save_report_chat_message,
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
