import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.demo_scenarios import select_demo_scenario
from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.os_prompt import SYSTEM_PROMPT, USER_PROMPT


OSPattern = Literal[
    "NORMAL",
    "TEMPORARY_SPIKE",
    "SUSTAINED_INCREASE",
    "RECOVERED",
    "FLUCTUATING",
    "MIXED",
]
PressureScope = Literal[
    "CLUSTER_WIDE",
    "INSTANCE_SPECIFIC",
    "MIXED",
    "NONE",
    "INCONCLUSIVE",
]


class OSAnalysisResult(BaseModel):
    overall_pattern: OSPattern = Field(
        description="Cluster-level OS resource pattern classification.",
    )
    severity_score: int = Field(
        ge=0,
        le=100,
        description="Cluster-level OS resource severity score from 0 to 100.",
    )
    confidence_score: int = Field(
        ge=0,
        le=100,
        description="Confidence score for this RAC-level OS analysis.",
    )
    cluster_metrics: dict[str, float] = Field(
        description="Report-ready numeric cluster OS metrics such as max_cpu_util_pct, avg_cpu_util_pct, max_memory_util_pct, max_paging_rate_per_sec, max_pga_mb, and workload_skew_pct.",
    )
    instance_scores: list[dict[str, float | int | str]] = Field(
        description="Per-instance report scores and key values. Include INST_ID, HOST_NAME, severity_score, cpu_util_pct, memory_util_pct, paging_rate_per_sec, and workload_share_pct.",
    )
    resource_timeseries: dict[str, list[dict[str, float | str]]] = Field(
        default_factory=dict,
        description="Report chart-ready OS resource time series. Keys should include cpu_util_pct, memory_util_pct, and paging_rate_per_sec when available.",
    )
    bottleneck_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Report chart-ready distribution of bottleneck evidence such as CPU, Memory, Paging, PGA, and Workload Imbalance.",
    )
    imbalance_score: int = Field(
        ge=0,
        le=100,
        description="Cross-instance workload/resource imbalance score from 0 to 100.",
    )
    cpu_pressure_score: int = Field(
        ge=0,
        le=100,
        description="CPU pressure score from 0 to 100.",
    )
    memory_pressure_score: int = Field(
        ge=0,
        le=100,
        description="Memory, swap, paging, and PGA pressure score from 0 to 100.",
    )
    pressure_scope: PressureScope = Field(
        description="Whether pressure is cluster-wide, instance-specific, mixed, absent, or inconclusive.",
    )
    cluster_health_summary: str = Field(
        description="Korean summary of cluster-level OS resource health.",
    )
    cpu_pressure_summary: str = Field(
        description="Korean summary of RAC-wide or node-local CPU pressure.",
    )
    memory_pressure_summary: str = Field(
        description="Korean summary of RAC-wide or node-local memory pressure, including swap or paging.",
    )
    workload_imbalance_summary: str = Field(
        description="Korean summary of workload skew or cross-instance resource imbalance.",
    )
    node_local_abnormalities: list[str] = Field(
        description="Korean descriptions of node-local abnormalities. Empty if none are identified.",
    )
    dominant_bottlenecks: list[str] = Field(
        description="Korean list of dominant resource bottlenecks. Empty if none are identified.",
    )
    recommendations: list[str] = Field(
        description="Korean operational recommendations.",
    )
    needs_deeper_analysis: bool = Field(
        description="Whether deeper OS or instance-level analysis is required.",
    )


def os_node(state: MainState) -> dict:
    db_name = state["db_name"]
    instance_os_analysis_results = fetch_instance_os_analysis_results(
        db_name,
        state.get("run_id"),
    )

    client = get_llm_client().with_structured_output(OSAnalysisResult)
    analysis = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    user_question=state["user_question"],
                    db_name=db_name,
                    instance_os_analysis_results=_to_json(
                        instance_os_analysis_results
                    ),
                )
            ),
        ]
    )

    result = analysis.model_dump()
    result["resource_timeseries"] = _build_resource_timeseries(
        instance_os_analysis_results,
    )
    result["bottleneck_distribution"] = _build_bottleneck_distribution(
        instance_os_analysis_results,
    )

    return {
        "node_result": [
            {
                "node": "os",
                "result": result,
            }
        ],
    }


def fetch_instance_os_analysis_results(db_name: str, run_id: str | None = None) -> list[dict]:
    """Fetch summarized instance-level OS Resource analysis results for a RAC database.

    Required data inferred from the prompt:
    - DB_NAME
    - INST_ID
    - HOST_NAME
    - Instance-level OS resource summary
    - Instance-level severity score
    - Instance-level pattern classification
    - CPU pressure findings
    - Memory pressure findings
    - Swap or paging activity findings
    - PGA spill indicators
    - Top PGA process summaries
    - Workload skew or resource imbalance indicators
    - Repeated spike or sustained pressure indicators

    This demo function is a placeholder for the real DB or monitoring repository query.
    """
    if select_demo_scenario(db_name, run_id) not in {"os_warning", "mixed_warning"}:
        return [
            {
                "DB_NAME": db_name,
                "INST_ID": 1,
                "HOST_NAME": "rac-node-01",
                "SUMMARY": "CPU, 메모리, PGA 사용량이 안정적이며 swap/paging 징후가 없습니다.",
                "SEVERITY_SCORE": 14,
                "PATTERN": "NORMAL",
                "CPU_FINDINGS": {
                    "AVG_CPU_UTIL_PCT": 34.2,
                    "MAX_CPU_UTIL_PCT": 48.5,
                    "SUSTAINED_CPU_PRESSURE": False,
                },
                "RESOURCE_TIMESERIES": [
                    {"EVENT_TIME": "2026-07-08T09:35:00+09:00", "CPU_UTIL_PCT": 29.4, "MEMORY_UTIL_PCT": 55.8, "PAGING_RATE_PER_SEC": 0.0},
                    {"EVENT_TIME": "2026-07-08T09:40:00+09:00", "CPU_UTIL_PCT": 32.1, "MEMORY_UTIL_PCT": 57.2, "PAGING_RATE_PER_SEC": 0.0},
                    {"EVENT_TIME": "2026-07-08T09:45:00+09:00", "CPU_UTIL_PCT": 35.8, "MEMORY_UTIL_PCT": 58.0, "PAGING_RATE_PER_SEC": 0.0},
                    {"EVENT_TIME": "2026-07-08T09:50:00+09:00", "CPU_UTIL_PCT": 37.0, "MEMORY_UTIL_PCT": 58.9, "PAGING_RATE_PER_SEC": 0.0},
                    {"EVENT_TIME": "2026-07-08T09:55:00+09:00", "CPU_UTIL_PCT": 33.7, "MEMORY_UTIL_PCT": 58.5, "PAGING_RATE_PER_SEC": 0.0},
                    {"EVENT_TIME": "2026-07-08T10:00:00+09:00", "CPU_UTIL_PCT": 34.2, "MEMORY_UTIL_PCT": 58.4, "PAGING_RATE_PER_SEC": 0.0},
                ],
                "MEMORY_FINDINGS": {
                    "AVG_MEMORY_UTIL_PCT": 58.4,
                    "SWAP_ACTIVITY": False,
                    "PAGING_RATE_PER_SEC": 0.0,
                },
                "PGA_FINDINGS": {
                    "PGA_PRESSURE": "LOW",
                    "PGA_SPILL_INDICATORS": False,
                    "TOP_PGA_PROCESSES": [
                        {"PID": 18421, "PROGRAM": "oracle@rac-node-01", "PGA_MB": 420}
                    ],
                },
                "IMBALANCE_INDICATORS": {
                    "WORKLOAD_SHARE_PCT": 49.0,
                    "RESOURCE_SKEW": "LOW",
                },
                "REPEATED_PRESSURE": False,
            },
            {
                "DB_NAME": db_name,
                "INST_ID": 2,
                "HOST_NAME": "rac-node-02",
                "SUMMARY": "CPU, 메모리, PGA 사용량이 안정적이며 노드 간 부하가 균형적입니다.",
                "SEVERITY_SCORE": 16,
                "PATTERN": "NORMAL",
                "CPU_FINDINGS": {
                    "AVG_CPU_UTIL_PCT": 37.1,
                    "MAX_CPU_UTIL_PCT": 51.2,
                    "SUSTAINED_CPU_PRESSURE": False,
                },
                "MEMORY_FINDINGS": {
                    "AVG_MEMORY_UTIL_PCT": 60.1,
                    "SWAP_ACTIVITY": False,
                    "PAGING_RATE_PER_SEC": 0.0,
                },
                "PGA_FINDINGS": {
                    "PGA_PRESSURE": "LOW",
                    "PGA_SPILL_INDICATORS": False,
                    "TOP_PGA_PROCESSES": [
                        {"PID": 20991, "PROGRAM": "oracle@rac-node-02", "PGA_MB": 460}
                    ],
                },
                "IMBALANCE_INDICATORS": {
                    "WORKLOAD_SHARE_PCT": 51.0,
                    "RESOURCE_SKEW": "LOW",
                },
                "REPEATED_PRESSURE": False,
            },
        ]

    return [
        {
            "DB_NAME": db_name,
            "INST_ID": 1,
            "HOST_NAME": "rac-node-01",
            "SUMMARY": "CPU와 메모리 사용률은 안정적이며 swap/paging 징후가 없습니다.",
            "SEVERITY_SCORE": 18,
            "PATTERN": "NORMAL",
            "CPU_FINDINGS": {
                "AVG_CPU_UTIL_PCT": 38.4,
                "MAX_CPU_UTIL_PCT": 52.1,
                "SUSTAINED_CPU_PRESSURE": False,
            },
            "RESOURCE_TIMESERIES": [
                {"EVENT_TIME": "2026-07-08T09:35:00+09:00", "CPU_UTIL_PCT": 37.6, "MEMORY_UTIL_PCT": 60.2, "PAGING_RATE_PER_SEC": 0.0},
                {"EVENT_TIME": "2026-07-08T09:40:00+09:00", "CPU_UTIL_PCT": 39.1, "MEMORY_UTIL_PCT": 60.9, "PAGING_RATE_PER_SEC": 0.0},
                {"EVENT_TIME": "2026-07-08T09:45:00+09:00", "CPU_UTIL_PCT": 40.3, "MEMORY_UTIL_PCT": 61.4, "PAGING_RATE_PER_SEC": 0.0},
                {"EVENT_TIME": "2026-07-08T09:50:00+09:00", "CPU_UTIL_PCT": 38.8, "MEMORY_UTIL_PCT": 61.1, "PAGING_RATE_PER_SEC": 0.0},
                {"EVENT_TIME": "2026-07-08T09:55:00+09:00", "CPU_UTIL_PCT": 37.9, "MEMORY_UTIL_PCT": 60.7, "PAGING_RATE_PER_SEC": 0.0},
                {"EVENT_TIME": "2026-07-08T10:00:00+09:00", "CPU_UTIL_PCT": 38.4, "MEMORY_UTIL_PCT": 61.2, "PAGING_RATE_PER_SEC": 0.0},
            ],
            "MEMORY_FINDINGS": {
                "AVG_MEMORY_UTIL_PCT": 61.2,
                "SWAP_ACTIVITY": False,
                "PAGING_RATE_PER_SEC": 0.0,
            },
            "PGA_FINDINGS": {
                "PGA_PRESSURE": "LOW",
                "PGA_SPILL_INDICATORS": False,
                "TOP_PGA_PROCESSES": [
                    {"PID": 18421, "PROGRAM": "oracle@rac-node-01", "PGA_MB": 420}
                ],
            },
            "IMBALANCE_INDICATORS": {
                "WORKLOAD_SHARE_PCT": 34.0,
                "RESOURCE_SKEW": "LOW",
            },
            "REPEATED_PRESSURE": False,
        },
        {
            "DB_NAME": db_name,
            "INST_ID": 2,
            "HOST_NAME": "rac-node-02",
            "SUMMARY": "CPU 사용률과 PGA 사용량이 다른 인스턴스보다 높고, 짧은 swap 증가가 반복 관찰됩니다.",
            "SEVERITY_SCORE": 48,
            "PATTERN": "SUSTAINED_INCREASE",
            "CPU_FINDINGS": {
                "AVG_CPU_UTIL_PCT": 76.8,
                "MAX_CPU_UTIL_PCT": 91.4,
                "SUSTAINED_CPU_PRESSURE": True,
            },
            "RESOURCE_TIMESERIES": [
                {"EVENT_TIME": "2026-07-08T09:35:00+09:00", "CPU_UTIL_PCT": 62.4, "MEMORY_UTIL_PCT": 76.8, "PAGING_RATE_PER_SEC": 2.1},
                {"EVENT_TIME": "2026-07-08T09:40:00+09:00", "CPU_UTIL_PCT": 68.7, "MEMORY_UTIL_PCT": 79.4, "PAGING_RATE_PER_SEC": 4.8},
                {"EVENT_TIME": "2026-07-08T09:45:00+09:00", "CPU_UTIL_PCT": 74.2, "MEMORY_UTIL_PCT": 82.1, "PAGING_RATE_PER_SEC": 8.4},
                {"EVENT_TIME": "2026-07-08T09:50:00+09:00", "CPU_UTIL_PCT": 81.5, "MEMORY_UTIL_PCT": 84.5, "PAGING_RATE_PER_SEC": 11.2},
                {"EVENT_TIME": "2026-07-08T09:55:00+09:00", "CPU_UTIL_PCT": 88.1, "MEMORY_UTIL_PCT": 86.1, "PAGING_RATE_PER_SEC": 13.4},
                {"EVENT_TIME": "2026-07-08T10:00:00+09:00", "CPU_UTIL_PCT": 91.4, "MEMORY_UTIL_PCT": 84.7, "PAGING_RATE_PER_SEC": 12.6},
            ],
            "MEMORY_FINDINGS": {
                "AVG_MEMORY_UTIL_PCT": 84.7,
                "SWAP_ACTIVITY": True,
                "PAGING_RATE_PER_SEC": 12.6,
            },
            "PGA_FINDINGS": {
                "PGA_PRESSURE": "MODERATE",
                "PGA_SPILL_INDICATORS": True,
                "TOP_PGA_PROCESSES": [
                    {"PID": 20991, "PROGRAM": "oracle@rac-node-02", "PGA_MB": 1850},
                    {"PID": 21034, "PROGRAM": "oracle@rac-node-02", "PGA_MB": 1440},
                ],
            },
            "IMBALANCE_INDICATORS": {
                "WORKLOAD_SHARE_PCT": 66.0,
                "RESOURCE_SKEW": "MODERATE",
            },
            "REPEATED_PRESSURE": True,
        },
    ]


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _build_resource_timeseries(
    instance_os_analysis_results: list[dict],
) -> dict[str, list[dict[str, float | str]]]:
    """Build chart-ready cluster resource time series from instance demo rows."""
    return {
        "cpu_util_pct": _average_series_points(instance_os_analysis_results, "CPU_UTIL_PCT"),
        "memory_util_pct": _average_series_points(instance_os_analysis_results, "MEMORY_UTIL_PCT"),
        "paging_rate_per_sec": _average_series_points(instance_os_analysis_results, "PAGING_RATE_PER_SEC"),
    }


def _average_series_points(
    instance_os_analysis_results: list[dict],
    key: str,
) -> list[dict[str, float | str]]:
    grouped: dict[str, list[float]] = {}

    for instance in instance_os_analysis_results:
        for row in instance.get("RESOURCE_TIMESERIES") or []:
            if row.get(key) is None:
                continue

            grouped.setdefault(str(row["EVENT_TIME"]), []).append(float(row[key]))

    return [
        {
            "time": event_time[11:16],
            "value": round(sum(values) / len(values), 2),
        }
        for event_time, values in sorted(grouped.items())
    ]


def _build_bottleneck_distribution(
    instance_os_analysis_results: list[dict],
) -> dict[str, float]:
    distribution = {
        "CPU": 0.0,
        "Memory": 0.0,
        "Paging": 0.0,
        "PGA": 0.0,
        "Workload Imbalance": 0.0,
    }

    for row in instance_os_analysis_results:
        cpu = row.get("CPU_FINDINGS") or {}
        memory = row.get("MEMORY_FINDINGS") or {}
        pga = row.get("PGA_FINDINGS") or {}
        imbalance = row.get("IMBALANCE_INDICATORS") or {}

        distribution["CPU"] += 2 if cpu.get("SUSTAINED_CPU_PRESSURE") else 1
        distribution["Memory"] += 2 if memory.get("AVG_MEMORY_UTIL_PCT", 0) >= 80 else 1
        distribution["Paging"] += 2 if memory.get("SWAP_ACTIVITY") else 0
        distribution["PGA"] += 2 if pga.get("PGA_SPILL_INDICATORS") else 1
        distribution["Workload Imbalance"] += (
            2 if imbalance.get("RESOURCE_SKEW") in {"MODERATE", "HIGH"} else 1
        )

    return {
        label: value
        for label, value in distribution.items()
        if value > 0
    }
