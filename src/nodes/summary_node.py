import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.summary_prompt import SYSTEM_PROMPT, USER_PROMPT


OverallStatus = Literal["NORMAL", "WARNING", "CRITICAL", "INCONCLUSIVE"]


class SummaryResult(BaseModel):
    summary_result: str = Field(
        description="Korean integrated summary of executed diagnostic node results.",
    )
    overall_status: OverallStatus = Field(
        description="Overall report status derived from executed diagnostic node results.",
    )
    overall_score: int = Field(
        ge=0,
        le=100,
        description="Overall risk score from 0 to 100. Higher means riskier.",
    )
    node_scores: dict[str, int] = Field(
        description="Risk or severity score by node name.",
    )
    key_findings: list[str] = Field(
        description="Korean list of key report findings.",
    )
    recommended_actions: list[str] = Field(
        description="Korean list of recommended operational actions.",
    )


def summary_node(state: MainState) -> dict:
    client = get_llm_client().with_structured_output(SummaryResult)
    summary = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    user_question=state["user_question"],
                    db_name=state["db_name"],
                    node_result=json.dumps(
                        state.get("node_result", []),
                        ensure_ascii=False,
                        default=str,
                    ),
                )
            ),
        ]
    )

    return {
        "summary_result": summary.summary_result,
        "node_result": [
            {
                "node": "summary",
                "result": summary.model_dump(),
            }
        ],
    }
