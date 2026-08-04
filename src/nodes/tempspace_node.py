import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.demo_scenarios import scenario_has_warning, select_demo_scenario
from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.tempspace_prompt import SYSTEM_PROMPT, USER_PROMPT


TempClassification = Literal["NORMAL", "WARNING", "CRITICAL", "INCONCLUSIVE"]


class TempSpaceAnalysisResult(BaseModel):
    classification: TempClassification = Field(
        description="Overall TEMP tablespace pressure classification.",
    )
    severity_score: int = Field(
        ge=0,
        le=100,
        description="TEMP pressure severity score from 0 to 100.",
    )
    confidence_score: int = Field(
        ge=0,
        le=100,
        description="Confidence score for this TEMP analysis.",
    )
    key_metrics: dict[str, float] = Field(
        description="Report-ready numeric TEMP metrics such as temp_used_pct, temp_used_mb, temp_free_mb, active_temp_sessions, and workarea_spill_mb.",
    )
    temp_usage_timeseries: dict[str, list[dict[str, float | str]]] = Field(
        default_factory=dict,
        description="Report chart-ready TEMP usage time series.",
    )
    temp_space_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Report chart-ready TEMP used/free composition in MB.",
    )
    top_consumers: list[dict[str, float | int | str]] = Field(
        description="Top TEMP-consuming sessions or SQLs.",
    )
    risk_factors: list[str] = Field(
        description="Korean list of TEMP risk factors.",
    )
    normal_factors: list[str] = Field(
        description="Korean list of healthy TEMP signals.",
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


def tempspace_node(state: MainState) -> dict:
    db_name = state["db_name"]
    run_id = state.get("run_id")
    temp_tablespace_overview = fetch_temp_tablespace_overview(db_name, run_id)
    top_temp_sessions = fetch_top_temp_sessions(db_name, run_id)
    temp_usage_timeseries = fetch_temp_usage_timeseries(db_name, run_id)
    workarea_spill_summary = fetch_workarea_spill_summary(db_name, run_id)

    client = get_llm_client().with_structured_output(TempSpaceAnalysisResult)
    analysis = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    user_question=state["user_question"],
                    db_name=db_name,
                    temp_tablespace_overview=_to_json(temp_tablespace_overview),
                    top_temp_sessions=_to_json(top_temp_sessions),
                    temp_usage_timeseries=_to_json(temp_usage_timeseries),
                    workarea_spill_summary=_to_json(workarea_spill_summary),
                )
            ),
        ]
    )

    result = analysis.model_dump()
    result["temp_usage_timeseries"] = {
        "temp_used_pct": [
            {"time": str(row["EVENT_TIME"])[11:16], "value": float(row["TEMP_USED_PCT"])}
            for row in temp_usage_timeseries
        ],
        "workarea_spill_mb": [
            {
                "time": str(row["EVENT_TIME"])[11:16],
                "value": float(row["WORKAREA_SPILL_MB"]),
            }
            for row in temp_usage_timeseries
        ],
    }
    result["temp_space_breakdown"] = {
        "used_mb": float(temp_tablespace_overview["TEMP_USED_MB"]),
        "free_mb": float(temp_tablespace_overview["TEMP_FREE_MB"]),
    }
    result["top_consumers"] = top_temp_sessions

    return {
        "node_result": [
            {
                "node": "tempspace",
                "result": result,
            }
        ],
    }


def fetch_temp_tablespace_overview(db_name: str, run_id: str | None = None) -> dict:
    """Fetch TEMP tablespace capacity and current usage summary.

    Required data inferred from the prompt:
    - DB_NAME
    - TABLESPACE_NAME
    - TEMP_TOTAL_MB
    - TEMP_USED_MB
    - TEMP_FREE_MB
    - TEMP_USED_PCT
    - AUTOEXTENSIBLE
    - MAX_SIZE_MB
    - ACTIVE_TEMP_SESSIONS
    """
    warning = scenario_has_warning(select_demo_scenario(db_name, run_id), "tempspace")

    if warning:
        return {
            "DB_NAME": db_name,
            "TABLESPACE_NAME": "TEMP",
            "TEMP_TOTAL_MB": 32768,
            "TEMP_USED_MB": 28736,
            "TEMP_FREE_MB": 4032,
            "TEMP_USED_PCT": 87.7,
            "AUTOEXTENSIBLE": "YES",
            "MAX_SIZE_MB": 40960,
            "ACTIVE_TEMP_SESSIONS": 9,
        }

    return {
        "DB_NAME": db_name,
        "TABLESPACE_NAME": "TEMP",
        "TEMP_TOTAL_MB": 32768,
        "TEMP_USED_MB": 8192,
        "TEMP_FREE_MB": 24576,
        "TEMP_USED_PCT": 25.0,
        "AUTOEXTENSIBLE": "YES",
        "MAX_SIZE_MB": 40960,
        "ACTIVE_TEMP_SESSIONS": 2,
    }


def fetch_top_temp_sessions(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch top sessions or SQLs consuming TEMP.

    Required data inferred from the prompt:
    - SID
    - SERIAL#
    - USERNAME
    - SQL_ID
    - PROGRAM
    - TEMP_USED_MB
    - WORKAREA_OPERATION such as SORT, HASH JOIN, GROUP BY, or CREATE INDEX
    """
    warning = scenario_has_warning(select_demo_scenario(db_name, run_id), "tempspace")

    if warning:
        return [
            {
                "SID": 184,
                "SERIAL#": 9932,
                "USERNAME": "BATCH_APP",
                "SQL_ID": "8x1ktemp9q2",
                "PROGRAM": "JDBC Thin Client",
                "TEMP_USED_MB": 12288,
                "WORKAREA_OPERATION": "HASH JOIN",
            },
            {
                "SID": 219,
                "SERIAL#": 1204,
                "USERNAME": "REPORT_APP",
                "SQL_ID": "2p7sort31ab",
                "PROGRAM": "report-runner",
                "TEMP_USED_MB": 6144,
                "WORKAREA_OPERATION": "SORT GROUP BY",
            },
        ]

    return [
        {
            "SID": 141,
            "SERIAL#": 882,
            "USERNAME": "APP",
            "SQL_ID": "7n2normalq",
            "PROGRAM": "JDBC Thin Client",
            "TEMP_USED_MB": 1024,
            "WORKAREA_OPERATION": "SORT",
        }
    ]


def fetch_temp_usage_timeseries(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch TEMP usage and workarea spill trend for recent intervals.

    Required data inferred from the prompt:
    - EVENT_TIME
    - TEMP_USED_PCT
    - TEMP_USED_MB
    - WORKAREA_SPILL_MB
    - ACTIVE_TEMP_SESSIONS
    """
    warning = scenario_has_warning(select_demo_scenario(db_name, run_id), "tempspace")
    rows = [
        ("09:35", 31.0, 10158, 120, 2),
        ("09:40", 35.2, 11534, 180, 3),
        ("09:45", 41.8, 13697, 240, 3),
        ("09:50", 52.4, 17170, 420, 5),
        ("09:55", 68.1, 22315, 970, 7),
        ("10:00", 87.7, 28736, 2048, 9),
    ] if warning else [
        ("09:35", 20.8, 6816, 0, 1),
        ("09:40", 22.6, 7406, 24, 1),
        ("09:45", 24.1, 7897, 18, 2),
        ("09:50", 23.9, 7831, 0, 1),
        ("09:55", 25.4, 8323, 16, 2),
        ("10:00", 25.0, 8192, 0, 2),
    ]

    return [
        {
            "DB_NAME": db_name,
            "EVENT_TIME": f"2026-07-08T{time}+09:00",
            "TEMP_USED_PCT": used_pct,
            "TEMP_USED_MB": used_mb,
            "WORKAREA_SPILL_MB": spill_mb,
            "ACTIVE_TEMP_SESSIONS": sessions,
        }
        for time, used_pct, used_mb, spill_mb, sessions in rows
    ]


def fetch_workarea_spill_summary(db_name: str, run_id: str | None = None) -> dict:
    """Fetch summarized one-pass and multi-pass workarea spill indicators.

    Required data inferred from the prompt:
    - DB_NAME
    - ONEPASS_EXECUTIONS
    - MULTIPASS_EXECUTIONS
    - TOTAL_SPILL_MB
    - TOP_OPERATION
    - PGA_TARGET_ADVICE or memory sizing context if available
    """
    warning = scenario_has_warning(select_demo_scenario(db_name, run_id), "tempspace")

    if warning:
        return {
            "DB_NAME": db_name,
            "ONEPASS_EXECUTIONS": 184,
            "MULTIPASS_EXECUTIONS": 27,
            "TOTAL_SPILL_MB": 4096,
            "TOP_OPERATION": "HASH JOIN",
        }

    return {
        "DB_NAME": db_name,
        "ONEPASS_EXECUTIONS": 12,
        "MULTIPASS_EXECUTIONS": 0,
        "TOTAL_SPILL_MB": 58,
        "TOP_OPERATION": "SORT",
    }


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
