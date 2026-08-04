import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.demo_scenarios import select_demo_scenario
from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.log_write_prompt import SYSTEM_PROMPT, USER_PROMPT


LogWriteClassification = Literal["NORMAL", "WARNING", "CRITICAL", "INCONCLUSIVE"]


class LogWriteAnalysisResult(BaseModel):
    classification: LogWriteClassification = Field(
        description="Overall redo/log write pressure classification.",
    )
    severity_score: int = Field(
        ge=0,
        le=100,
        description="Redo/log write severity score from 0 to 100.",
    )
    confidence_score: int = Field(
        ge=0,
        le=100,
        description="Confidence score for this log write analysis.",
    )
    key_metrics: dict[str, float] = Field(
        description="Report-ready numeric log write metrics such as redo_mb_per_sec, commits_per_sec, log_file_sync_avg_ms, log_file_parallel_write_avg_ms, and log_switch_count.",
    )
    redo_write_timeseries: dict[str, list[dict[str, float | str]]] = Field(
        default_factory=dict,
        description="Report chart-ready redo, commit, and wait latency time series.",
    )
    wait_event_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Report chart-ready distribution of log write wait time by event.",
    )
    risk_factors: list[str] = Field(
        description="Korean list of redo/log write risk factors.",
    )
    normal_factors: list[str] = Field(
        description="Korean list of healthy redo/log write signals.",
    )
    commit_latency_assessment: str = Field(
        description="Korean assessment of commit latency and log file sync.",
    )
    redo_write_assessment: str = Field(
        description="Korean assessment of LGWR write and log file parallel write.",
    )
    operational_impact: str = Field(
        description="Korean assessment of operational impact.",
    )
    summary: str = Field(
        description="Concise Korean operational summary.",
    )
    recommendations: list[str] = Field(
        description="Korean operational recommendations.",
    )


def log_write_node(state: MainState) -> dict:
    db_name = state["db_name"]
    run_id = state.get("run_id")
    redo_commit_overview = fetch_redo_commit_overview(db_name, run_id)
    log_wait_events = fetch_log_wait_events(db_name, run_id)
    redo_write_timeseries = fetch_redo_write_timeseries(db_name, run_id)
    log_switch_history = fetch_log_switch_history(db_name, run_id)

    client = get_llm_client().with_structured_output(LogWriteAnalysisResult)
    analysis = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    user_question=state["user_question"],
                    db_name=db_name,
                    redo_commit_overview=_to_json(redo_commit_overview),
                    log_wait_events=_to_json(log_wait_events),
                    redo_write_timeseries=_to_json(redo_write_timeseries),
                    log_switch_history=_to_json(log_switch_history),
                )
            ),
        ]
    )

    result = analysis.model_dump()
    result["redo_write_timeseries"] = {
        "redo_mb_per_sec": [
            {"time": str(row["EVENT_TIME"])[11:16], "value": float(row["REDO_MB_PER_SEC"])}
            for row in redo_write_timeseries
        ],
        "commits_per_sec": [
            {"time": str(row["EVENT_TIME"])[11:16], "value": float(row["COMMITS_PER_SEC"])}
            for row in redo_write_timeseries
        ],
        "log_file_sync_avg_ms": [
            {
                "time": str(row["EVENT_TIME"])[11:16],
                "value": float(row["LOG_FILE_SYNC_AVG_MS"]),
            }
            for row in redo_write_timeseries
        ],
    }
    result["wait_event_distribution"] = {
        str(row["EVENT_NAME"]): float(row["TIME_WAITED_MS"])
        for row in log_wait_events
    }

    return {
        "node_result": [
            {
                "node": "log_write",
                "result": result,
            }
        ],
    }


def fetch_redo_commit_overview(db_name: str, run_id: str | None = None) -> dict:
    """Fetch redo generation, commit rate, and LGWR summary metrics.

    Required data inferred from the prompt:
    - DB_NAME
    - REDO_MB_PER_SEC
    - COMMITS_PER_SEC
    - AVG_COMMIT_LATENCY_MS
    - LOG_FILE_SYNC_AVG_MS
    - LOG_FILE_PARALLEL_WRITE_AVG_MS
    - REDO_WRITE_MB_PER_SEC
    - LOG_SWITCH_COUNT_LAST_HOUR
    """
    warning = select_demo_scenario(db_name, run_id) in {"log_write_warning", "mixed_warning"}

    if warning:
        return {
            "DB_NAME": db_name,
            "REDO_MB_PER_SEC": 92.4,
            "COMMITS_PER_SEC": 1180.0,
            "AVG_COMMIT_LATENCY_MS": 28.6,
            "LOG_FILE_SYNC_AVG_MS": 31.2,
            "LOG_FILE_PARALLEL_WRITE_AVG_MS": 18.4,
            "REDO_WRITE_MB_PER_SEC": 94.1,
            "LOG_SWITCH_COUNT_LAST_HOUR": 18,
        }

    return {
        "DB_NAME": db_name,
        "REDO_MB_PER_SEC": 18.7,
        "COMMITS_PER_SEC": 220.0,
        "AVG_COMMIT_LATENCY_MS": 3.4,
        "LOG_FILE_SYNC_AVG_MS": 4.1,
        "LOG_FILE_PARALLEL_WRITE_AVG_MS": 2.2,
        "REDO_WRITE_MB_PER_SEC": 19.3,
        "LOG_SWITCH_COUNT_LAST_HOUR": 4,
    }


def fetch_log_wait_events(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch redo/log write wait event summary.

    Required data inferred from the prompt:
    - EVENT_NAME
    - TOTAL_WAITS
    - TIME_WAITED_MS
    - AVG_WAIT_MS
    - P95_WAIT_MS
    """
    warning = select_demo_scenario(db_name, run_id) in {"log_write_warning", "mixed_warning"}

    if warning:
        return [
            {
                "EVENT_NAME": "log file sync",
                "TOTAL_WAITS": 182400,
                "TIME_WAITED_MS": 568000,
                "AVG_WAIT_MS": 31.2,
                "P95_WAIT_MS": 64.0,
            },
            {
                "EVENT_NAME": "log file parallel write",
                "TOTAL_WAITS": 58400,
                "TIME_WAITED_MS": 214000,
                "AVG_WAIT_MS": 18.4,
                "P95_WAIT_MS": 39.0,
            },
        ]

    return [
        {
            "EVENT_NAME": "log file sync",
            "TOTAL_WAITS": 38400,
            "TIME_WAITED_MS": 15600,
            "AVG_WAIT_MS": 4.1,
            "P95_WAIT_MS": 9.0,
        },
        {
            "EVENT_NAME": "log file parallel write",
            "TOTAL_WAITS": 12100,
            "TIME_WAITED_MS": 2660,
            "AVG_WAIT_MS": 2.2,
            "P95_WAIT_MS": 5.0,
        },
    ]


def fetch_redo_write_timeseries(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch recent redo generation and commit latency trend.

    Required data inferred from the prompt:
    - EVENT_TIME
    - REDO_MB_PER_SEC
    - COMMITS_PER_SEC
    - LOG_FILE_SYNC_AVG_MS
    - LOG_FILE_PARALLEL_WRITE_AVG_MS
    """
    warning = select_demo_scenario(db_name, run_id) in {"log_write_warning", "mixed_warning"}
    rows = [
        ("09:35", 36.4, 580.0, 8.4, 4.2),
        ("09:40", 44.8, 710.0, 11.6, 6.1),
        ("09:45", 61.2, 880.0, 17.4, 9.8),
        ("09:50", 72.6, 970.0, 21.9, 13.4),
        ("09:55", 86.8, 1100.0, 27.6, 16.7),
        ("10:00", 92.4, 1180.0, 31.2, 18.4),
    ] if warning else [
        ("09:35", 16.4, 190.0, 3.2, 1.8),
        ("09:40", 17.8, 210.0, 3.8, 2.1),
        ("09:45", 18.1, 218.0, 4.0, 2.2),
        ("09:50", 19.2, 225.0, 4.4, 2.3),
        ("09:55", 18.9, 230.0, 4.2, 2.1),
        ("10:00", 18.7, 220.0, 4.1, 2.2),
    ]

    return [
        {
            "DB_NAME": db_name,
            "EVENT_TIME": f"2026-07-08T{time}+09:00",
            "REDO_MB_PER_SEC": redo_mb,
            "COMMITS_PER_SEC": commits,
            "LOG_FILE_SYNC_AVG_MS": sync_ms,
            "LOG_FILE_PARALLEL_WRITE_AVG_MS": parallel_write_ms,
        }
        for time, redo_mb, commits, sync_ms, parallel_write_ms in rows
    ]


def fetch_log_switch_history(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch redo log switch history.

    Required data inferred from the prompt:
    - SWITCH_TIME
    - THREAD#
    - SEQUENCE#
    - REDO_MB
    - SWITCH_INTERVAL_MINUTES
    """
    warning = select_demo_scenario(db_name, run_id) in {"log_write_warning", "mixed_warning"}
    intervals = [4, 3, 4, 3, 3, 4] if warning else [18, 16, 21, 19]

    return [
        {
            "DB_NAME": db_name,
            "SWITCH_TIME": f"2026-07-08T09:{30 + index * 5:02d}:00+09:00",
            "THREAD#": 1,
            "SEQUENCE#": 12880 + index,
            "REDO_MB": 2048,
            "SWITCH_INTERVAL_MINUTES": interval,
        }
        for index, interval in enumerate(intervals)
    ]


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
