from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.global_health_prompt import SYSTEM_PROMPT, USER_PROMPT


TargetNode = Literal["memory", "os"]


class GlobalHealthResult(BaseModel):
    target_nodes: list[TargetNode] = Field(
        description="Specialized diagnostic nodes that should run next.",
    )
    reason: str = Field(
        description="Short reason for the routing decision.",
    )


def global_health_node(state: MainState) -> dict:
    user_question = state["user_question"]
    client = get_llm_client().with_structured_output(GlobalHealthResult)
    classification = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT.format(user_question=user_question)),
        ]
    )
    target_nodes = list(dict.fromkeys(classification.target_nodes))

    return {
        "target_nodes": target_nodes,
        "node_result": [
            {
                "node": "global_health",
                "result": {
                    "target_nodes": target_nodes,
                    "reason": classification.reason,
                },
            }
        ],
    }
