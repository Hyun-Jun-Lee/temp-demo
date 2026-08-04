import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.demo_scenarios import scenario_has_warning, select_demo_scenario
from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.memory_prompt import SYSTEM_PROMPT, USER_PROMPT


MemoryClassification = Literal[
    "NORMAL",
    "WARNING",
    "CRITICAL",
    "LOW_IMPACT",
    "INCONCLUSIVE",
]
MemoryTrend = Literal[
    "NORMAL",
    "TEMPORARY_SPIKE",
    "SUSTAINED_INCREASE",
    "SUSTAINED_PRESSURE",
    "RECOVERED",
    "FLUCTUATING",
    "MIXED",
    "INCONCLUSIVE",
]


class MemoryAnalysisResult(BaseModel):
    classification: MemoryClassification = Field(
        description="Overall memory pressure classification for this instance.",
    )
    trend: MemoryTrend = Field(
        description="Overall memory-related trend classification.",
    )
    severity_score: int = Field(
        ge=0,
        le=100,
        description="Memory pressure severity score from 0 to 100.",
    )
    confidence_score: int = Field(
        ge=0,
        le=100,
        description="Confidence score for this memory analysis.",
    )
    key_metrics: dict[str, float] = Field(
        description="Report-ready numeric memory metrics such as request_failures, request_misses, hard_parse_per_sec, soft_parse_ratio, library_cache_hit_ratio, row_cache_hit_ratio, shared_pool_free_pct, and shared_pool_free_mb.",
    )
    metric_timeseries: dict[str, list[dict[str, float | str]]] = Field(
        default_factory=dict,
        description="Report chart-ready memory time series. Keys should include shared_pool_free_mb, hard_parse_per_sec, and soft_parse_ratio when available.",
    )
    memory_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Report chart-ready memory composition values such as used_mb, free_mb, and reserved_used_mb.",
    )
    risk_factors: list[str] = Field(
        description="Korean list of memory risk factors. Empty if none are found.",
    )
    normal_factors: list[str] = Field(
        description="Korean list of healthy memory signals.",
    )
    allocation_failure_risk: str = Field(
        description="Korean assessment of REQUEST_FAILURES and ORA-04031 risk.",
    )
    reserved_pool_pressure: str = Field(
        description="Korean assessment of REQUEST_MISSES and reserved pool pressure.",
    )
    fragmentation_risk: str = Field(
        description="Korean assessment of fragmentation indicators.",
    )
    parse_efficiency: str = Field(
        description="Korean assessment of hard parse, total parse, and soft parse ratio.",
    )
    cache_efficiency: str = Field(
        description="Korean assessment of library cache and row cache hit ratios.",
    )
    shared_pool_free_behavior: str = Field(
        description="Korean assessment of Shared Pool Free % and Free Size MB behavior.",
    )
    operational_impact: str = Field(
        description="Korean assessment of likely user or operational impact.",
    )
    summary: str = Field(
        description="Concise Korean operational summary.",
    )
    recommendations: list[str] = Field(
        description="Korean operational recommendations.",
    )


def memory_node(state: MainState) -> dict:
    db_name = state["db_name"]
    run_id = state.get("run_id")
    sysmetric_data = fetch_sysmetric_data(db_name, run_id)
    shared_pool_free_size_trend = fetch_shared_pool_free_size_trend(db_name, run_id)
    shared_pool_reserved_area_trend = fetch_shared_pool_reserved_area_trend(db_name, run_id)

    client = get_llm_client().with_structured_output(MemoryAnalysisResult)
    analysis = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    db_name=db_name,
                    sysmetric_data=_to_json(sysmetric_data),
                    shared_pool_free_size_trend=_to_json(shared_pool_free_size_trend),
                    shared_pool_reserved_area_trend=_to_json(
                        shared_pool_reserved_area_trend
                    ),
                )
            ),
        ]
    )

    result = analysis.model_dump()
    result["metric_timeseries"] = _build_metric_timeseries(
        sysmetric_data,
        shared_pool_free_size_trend,
    )
    result["memory_breakdown"] = _build_memory_breakdown(
        shared_pool_free_size_trend,
        shared_pool_reserved_area_trend,
    )

    return {
        "node_result": [
            {
                "node": "memory",
                "result": result,
            }
        ],
    }


def fetch_sysmetric_data(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch Oracle Sysmetric data for the last 30 minutes at 1-minute granularity.

    Required data inferred from the prompt:
    - EVENT_TIME
    - INST_ID
    - METRIC_ID
    - METRIC_NAME
    - VALUE
    - Metrics: 2044 Total Parse Count Per Sec, 2046 Hard Parse Count Per Sec,
      2055 Soft Parse Ratio, 2110 Row Cache Hit Ratio, 2112 Library Cache Hit Ratio,
      2114 Shared Pool Free %
    - Optional baseline fields if available for trend/anomaly comparison
    """
    if scenario_has_warning(select_demo_scenario(db_name, run_id), "memory"):
        return [
            {
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "INST_ID": 1,
                "METRIC_ID": 2044,
                "METRIC_NAME": "Total Parse Count Per Sec",
                "VALUE": 130.5,
            },
            {
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "INST_ID": 1,
                "METRIC_ID": 2046,
                "METRIC_NAME": "Hard Parse Count Per Sec",
                "VALUE": 18.4,
            },
            {
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "INST_ID": 1,
                "METRIC_ID": 2055,
                "METRIC_NAME": "Soft Parse Ratio",
                "VALUE": 88.2,
            },
            {
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "INST_ID": 1,
                "METRIC_ID": 2110,
                "METRIC_NAME": "Row Cache Hit Ratio",
                "VALUE": 94.1,
            },
            {
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "INST_ID": 1,
                "METRIC_ID": 2112,
                "METRIC_NAME": "Library Cache Hit Ratio",
                "VALUE": 91.8,
            },
            {
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "INST_ID": 1,
                "METRIC_ID": 2114,
                "METRIC_NAME": "Shared Pool Free %",
                "VALUE": 0.9,
            },
        ]

    return [
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 1,
            "METRIC_ID": 2044,
            "METRIC_NAME": "Total Parse Count Per Sec",
            "VALUE": 42.1,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 1,
            "METRIC_ID": 2046,
            "METRIC_NAME": "Hard Parse Count Per Sec",
            "VALUE": 0.8,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 1,
            "METRIC_ID": 2055,
            "METRIC_NAME": "Soft Parse Ratio",
            "VALUE": 98.7,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 1,
            "METRIC_ID": 2110,
            "METRIC_NAME": "Row Cache Hit Ratio",
            "VALUE": 99.2,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 1,
            "METRIC_ID": 2112,
            "METRIC_NAME": "Library Cache Hit Ratio",
            "VALUE": 99.5,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 1,
            "METRIC_ID": 2114,
            "METRIC_NAME": "Shared Pool Free %",
            "VALUE": 3.4,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 2,
            "METRIC_ID": 2044,
            "METRIC_NAME": "Total Parse Count Per Sec",
            "VALUE": 39.6,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 2,
            "METRIC_ID": 2046,
            "METRIC_NAME": "Hard Parse Count Per Sec",
            "VALUE": 0.6,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 2,
            "METRIC_ID": 2055,
            "METRIC_NAME": "Soft Parse Ratio",
            "VALUE": 99.0,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 2,
            "METRIC_ID": 2110,
            "METRIC_NAME": "Row Cache Hit Ratio",
            "VALUE": 99.4,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 2,
            "METRIC_ID": 2112,
            "METRIC_NAME": "Library Cache Hit Ratio",
            "VALUE": 99.6,
        },
        {
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "INST_ID": 2,
            "METRIC_ID": 2114,
            "METRIC_NAME": "Shared Pool Free %",
            "VALUE": 4.1,
        },
    ]


def fetch_shared_pool_free_size_trend(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch Shared Pool Free Size trend for the last 30 minutes.

    Required data inferred from the prompt:
    - DB_NAME
    - INST_ID
    - EVENT_TIME
    - NAME, expected value such as "shared pool Free Size"
    - MEGA_BYTES, representing absolute Shared Pool free size in MB
    """
    if scenario_has_warning(select_demo_scenario(db_name, run_id), "memory"):
        return [
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T09:35:00+09:00",
                "NAME": "shared pool Free Size",
                "MEGA_BYTES": 420,
            },
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T09:40:00+09:00",
                "NAME": "shared pool Free Size",
                "MEGA_BYTES": 312,
            },
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T09:45:00+09:00",
                "NAME": "shared pool Free Size",
                "MEGA_BYTES": 238,
            },
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T09:50:00+09:00",
                "NAME": "shared pool Free Size",
                "MEGA_BYTES": 164,
            },
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T09:55:00+09:00",
                "NAME": "shared pool Free Size",
                "MEGA_BYTES": 118,
            },
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "NAME": "shared pool Free Size",
                "MEGA_BYTES": 96,
            },
        ]

    return [
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T09:35:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 512,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T09:40:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 508,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T09:45:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 511,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T09:50:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 504,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T09:55:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 509,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 506,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 2,
            "EVENT_TIME": "2026-07-08T09:30:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 488,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 2,
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "NAME": "shared pool Free Size",
            "MEGA_BYTES": 492,
        },
    ]


def fetch_shared_pool_reserved_area_trend(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch V$SHARED_POOL_RESERVED trend for the last 30 minutes.

    Required data inferred from the prompt:
    - DB_NAME
    - INST_ID
    - EVENT_TIME
    - FREE_SPACE_MB
    - FREE_COUNT
    - MAX_FREE_SIZE_MB
    - USED_SPACE_MB
    - USED_COUNT
    - REQUESTS
    - REQUEST_MISSES
    - LAST_MISS_SIZE
    - REQUEST_FAILURES
    """
    if scenario_has_warning(select_demo_scenario(db_name, run_id), "memory"):
        return [
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "EVENT_TIME": "2026-07-08T10:00:00+09:00",
                "FREE_SPACE_MB": 72,
                "FREE_COUNT": 88,
                "MAX_FREE_SIZE_MB": 4,
                "USED_SPACE_MB": 154,
                "USED_COUNT": 44,
                "REQUESTS": 2680,
                "REQUEST_MISSES": 6,
                "LAST_MISS_SIZE": 4194304,
                "REQUEST_FAILURES": 0,
            }
        ]

    return [
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "FREE_SPACE_MB": 128,
            "FREE_COUNT": 42,
            "MAX_FREE_SIZE_MB": 36,
            "USED_SPACE_MB": 64,
            "USED_COUNT": 18,
            "REQUESTS": 1280,
            "REQUEST_MISSES": 0,
            "LAST_MISS_SIZE": 0,
            "REQUEST_FAILURES": 0,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 2,
            "EVENT_TIME": "2026-07-08T10:00:00+09:00",
            "FREE_SPACE_MB": 136,
            "FREE_COUNT": 45,
            "MAX_FREE_SIZE_MB": 40,
            "USED_SPACE_MB": 58,
            "USED_COUNT": 16,
            "REQUESTS": 1195,
            "REQUEST_MISSES": 0,
            "LAST_MISS_SIZE": 0,
            "REQUEST_FAILURES": 0,
        },
    ]


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _build_metric_timeseries(
    sysmetric_data: list[dict],
    shared_pool_free_size_trend: list[dict],
) -> dict[str, list[dict[str, float | str]]]:
    """Build chart-ready memory time series from the demo source rows."""
    return {
        "shared_pool_free_mb": [
            {
                "time": str(row["EVENT_TIME"])[11:16],
                "value": float(row["MEGA_BYTES"]),
            }
            for row in shared_pool_free_size_trend
            if row.get("INST_ID") == 1
        ],
        "hard_parse_per_sec": _metric_points(sysmetric_data, "Hard Parse Count Per Sec"),
        "soft_parse_ratio": _metric_points(sysmetric_data, "Soft Parse Ratio"),
    }


def _metric_points(rows: list[dict], metric_name: str) -> list[dict[str, float | str]]:
    return [
        {
            "time": str(row["EVENT_TIME"])[11:16],
            "value": float(row["VALUE"]),
        }
        for row in rows
        if row.get("INST_ID") == 1 and row.get("METRIC_NAME") == metric_name
    ]


def _build_memory_breakdown(
    shared_pool_free_size_trend: list[dict],
    shared_pool_reserved_area_trend: list[dict],
) -> dict[str, float]:
    latest_free = _latest_number(shared_pool_free_size_trend, "MEGA_BYTES")
    latest_reserved_used = _latest_number(shared_pool_reserved_area_trend, "USED_SPACE_MB")

    if latest_free is None and latest_reserved_used is None:
        return {}

    free_mb = latest_free or 0.0
    reserved_used_mb = latest_reserved_used or 0.0
    estimated_total_mb = max(1024.0, free_mb + reserved_used_mb + 512.0)
    used_mb = max(estimated_total_mb - free_mb - reserved_used_mb, 0.0)

    return {
        "used_mb": round(used_mb, 2),
        "free_mb": round(free_mb, 2),
        "reserved_used_mb": round(reserved_used_mb, 2),
    }


def _latest_number(rows: list[dict], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return values[-1] if values else None
