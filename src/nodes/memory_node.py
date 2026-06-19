import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

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
    sysmetric_data = fetch_sysmetric_data(db_name)
    shared_pool_free_size_trend = fetch_shared_pool_free_size_trend(db_name)
    shared_pool_reserved_area_trend = fetch_shared_pool_reserved_area_trend(db_name)

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

    return {
        "node_result": [
            {
                "node": "memory",
                "result": analysis.model_dump()
            }
        ],
    }


def fetch_sysmetric_data(db_name: str) -> list[dict]:
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
    return []


def fetch_shared_pool_free_size_trend(db_name: str) -> list[dict]:
    """Fetch Shared Pool Free Size trend for the last 30 minutes.

    Required data inferred from the prompt:
    - DB_NAME
    - INST_ID
    - EVENT_TIME
    - NAME, expected value such as "shared pool Free Size"
    - MEGA_BYTES, representing absolute Shared Pool free size in MB
    """
    return []


def fetch_shared_pool_reserved_area_trend(db_name: str) -> list[dict]:
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
    return []


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
