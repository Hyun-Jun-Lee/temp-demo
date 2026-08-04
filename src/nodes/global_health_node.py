import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.demo_scenarios import scenario_has_warning, select_demo_scenario
from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.global_health_prompt import SYSTEM_PROMPT, USER_PROMPT


TargetNode = Literal["memory", "os", "tempspace", "log_write"]


class GlobalHealthResult(BaseModel):
    target_nodes: list[TargetNode] = Field(
        description="Specialized diagnostic nodes that should run next.",
    )
    overall_health_score: int = Field(
        ge=0,
        le=100,
        description="Overall database health score. Higher means healthier.",
    )
    memory_signal_score: int = Field(
        ge=0,
        le=100,
        description="Memory risk signal score. Higher means greater memory concern.",
    )
    os_signal_score: int = Field(
        ge=0,
        le=100,
        description="OS/server resource risk signal score. Higher means greater OS concern.",
    )
    tempspace_signal_score: int = Field(
        ge=0,
        le=100,
        description="TEMP tablespace risk signal score. Higher means greater TEMP concern.",
    )
    log_write_signal_score: int = Field(
        ge=0,
        le=100,
        description="Redo/log write risk signal score. Higher means greater log write concern.",
    )
    routing_confidence: int = Field(
        ge=0,
        le=100,
        description="Confidence score for the selected target nodes.",
    )
    detected_signals: list[str] = Field(
        description="Korean list of major signals used for routing.",
    )
    reason: str = Field(
        description="Short reason for the routing decision.",
    )


def global_health_node(state: MainState) -> dict:
    user_question = state["user_question"]
    db_name = state["db_name"]
    global_health_overview = fetch_global_health_overview(db_name, state.get("run_id"))
    client = get_llm_client().with_structured_output(GlobalHealthResult)
    classification = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    user_question=user_question,
                    db_name=db_name,
                    global_health_overview=_to_json(global_health_overview),
                )
            ),
        ]
    )
    llm_target_nodes = list(dict.fromkeys(classification.target_nodes))
    signal_target_nodes = target_nodes_from_warning_signals(global_health_overview)
    target_nodes = signal_target_nodes or llm_target_nodes

    return {
        "target_nodes": target_nodes,
        "node_result": [
            {
                "node": "global_health",
                "result": {
                    "target_nodes": target_nodes,
                    "llm_target_nodes": llm_target_nodes,
                    "signal_target_nodes": signal_target_nodes,
                    "overall_health_score": classification.overall_health_score,
                    "memory_signal_score": classification.memory_signal_score,
                    "os_signal_score": classification.os_signal_score,
                    "tempspace_signal_score": classification.tempspace_signal_score,
                    "log_write_signal_score": classification.log_write_signal_score,
                    "routing_confidence": classification.routing_confidence,
                    "detected_signals": classification.detected_signals,
                    "reason": classification.reason,
                },
                "source": {
                    "db_name": db_name,
                    "global_health_overview": global_health_overview,
                },
            }
        ],
    }


def fetch_global_health_overview(db_name: str, run_id: str | None = None) -> dict:
    """Fetch database-wide overview signals used to route to specialized agents.

    Required data inferred from the global health prompt:
    - DB_NAME
    - High-level database availability and service status
    - Instance or RAC node count and per-instance status
    - Memory overview signals: memory pressure, Shared Pool warnings,
      reserved pool misses/failures, hard parse increase, cache degradation
    - OS overview signals: CPU pressure, memory pressure, swap or paging activity,
      PGA pressure, disk/filesystem warnings, network/process/load issues,
      workload skew, node imbalance
    - Signal freshness or data quality indicators
    - Short operational summary for broad health routing

    This demo function returns a warning OS scenario with normal memory signals.
    """
    scenario = select_demo_scenario(db_name, run_id)
    memory_warning = scenario_has_warning(scenario, "memory")
    os_warning = scenario_has_warning(scenario, "os")
    tempspace_warning = scenario_has_warning(scenario, "tempspace")
    log_write_warning = scenario_has_warning(scenario, "log_write")

    return {
        "DB_NAME": db_name,
        "SNAPSHOT_TIME": "2026-07-09T10:00:00+09:00",
        "DATABASE_STATUS": "OPEN",
        "SERVICE_STATUS": "AVAILABLE",
        "INSTANCE_COUNT": 2,
        "DATA_QUALITY": "COMPLETE",
        "DEMO_SCENARIO": scenario,
        "MEMORY_OVERVIEW": {
            "SIGNAL": "WARNING" if memory_warning else "NORMAL",
            "SHARED_POOL_FREE_TREND": "DECREASING" if memory_warning else "STABLE",
            "REQUEST_MISSES": 4 if memory_warning else 0,
            "REQUEST_FAILURES": 0,
            "HARD_PARSE_TREND": "INCREASING" if memory_warning else "STABLE",
            "CACHE_EFFICIENCY": "DEGRADED" if memory_warning else "HEALTHY",
            "ROUTING_HINT": "memory node should run"
            if memory_warning
            else "memory node is optional unless user asks for memory details",
        },
        "OS_OVERVIEW": {
            "SIGNAL": "WARNING" if os_warning else "NORMAL",
            "CPU_PRESSURE": "INSTANCE_SPECIFIC" if os_warning else "NORMAL",
            "MEMORY_PRESSURE": "MODERATE_ON_ONE_NODE" if os_warning else "NORMAL",
            "SWAP_OR_PAGING": "OBSERVED_ON_INST_2" if os_warning else "NONE",
            "PGA_PRESSURE": "MODERATE_ON_INST_2" if os_warning else "LOW",
            "WORKLOAD_SKEW": "INST_2_HANDLES_66_PERCENT" if os_warning else "LOW",
            "NODE_IMBALANCE": "MODERATE" if os_warning else "LOW",
            "ROUTING_HINT": "os node should run"
            if os_warning
            else "os node is optional unless user asks for OS details",
        },
        "TEMPSPACE_OVERVIEW": {
            "SIGNAL": "WARNING" if tempspace_warning else "NORMAL",
            "TEMP_USED_PCT": 87.7 if tempspace_warning else 25.0,
            "ACTIVE_TEMP_SESSIONS": 9 if tempspace_warning else 2,
            "WORKAREA_SPILL_MB": 4096 if tempspace_warning else 58,
            "ROUTING_HINT": "tempspace node should run"
            if tempspace_warning
            else "tempspace node is optional unless user asks for TEMP details",
        },
        "LOG_WRITE_OVERVIEW": {
            "SIGNAL": "WARNING" if log_write_warning else "NORMAL",
            "LOG_FILE_SYNC_AVG_MS": 31.2 if log_write_warning else 4.1,
            "LOG_FILE_PARALLEL_WRITE_AVG_MS": 18.4 if log_write_warning else 2.2,
            "REDO_MB_PER_SEC": 92.4 if log_write_warning else 18.7,
            "LOG_SWITCH_COUNT_LAST_HOUR": 18 if log_write_warning else 4,
            "ROUTING_HINT": "log_write node should run"
            if log_write_warning
            else "log_write node is optional unless user asks for redo or commit details",
        },
        "SUMMARY": _build_overview_summary(
            memory_warning,
            os_warning,
            tempspace_warning,
            log_write_warning,
        ),
    }


def _build_overview_summary(
    memory_warning: bool,
    os_warning: bool,
    tempspace_warning: bool,
    log_write_warning: bool,
) -> str:
    warnings = []

    if memory_warning:
        warnings.append("메모리")

    if os_warning:
        warnings.append("OS")

    if tempspace_warning:
        warnings.append("TEMP")

    if log_write_warning:
        warnings.append("redo/log write")

    if len(warnings) > 1:
        return f"DB는 open 상태이나 {', '.join(warnings)} 영역에서 경고 신호가 확인되어 세부 점검이 필요합니다."

    if memory_warning:
        return "DB는 open 상태이나 Shared Pool/parse/cache 관련 메모리 경고 신호가 확인되어 메모리 점검이 필요합니다."

    if os_warning:
        return "DB는 open 상태이며 메모리 지표는 안정적입니다. 다만 특정 RAC 노드에서 OS 리소스 경고 신호가 있어 OS 점검이 필요합니다."

    if tempspace_warning:
        return "DB는 open 상태이나 TEMP 사용률과 workarea spill 증가가 확인되어 TEMP 점검이 필요합니다."

    if log_write_warning:
        return "DB는 open 상태이나 commit latency와 redo write 지연 신호가 확인되어 log write 점검이 필요합니다."

    return "DB는 open 상태이며 메모리, OS, TEMP, redo/log write 전반 지표가 안정적입니다."


def target_nodes_from_warning_signals(global_health_overview: dict) -> list[str]:
    """Return deterministic routing targets from overview WARNING signals."""
    signal_mapping = [
        ("MEMORY_OVERVIEW", "memory"),
        ("OS_OVERVIEW", "os"),
        ("TEMPSPACE_OVERVIEW", "tempspace"),
        ("LOG_WRITE_OVERVIEW", "log_write"),
    ]

    return [
        node_name
        for overview_key, node_name in signal_mapping
        if (global_health_overview.get(overview_key) or {}).get("SIGNAL") == "WARNING"
    ]


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
