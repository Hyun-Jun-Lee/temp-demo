import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.summary_prompt import SYSTEM_PROMPT, USER_PROMPT


class SummaryResult(BaseModel):
    summary_result: str = Field(
        description="Korean integrated summary of executed diagnostic node results.",
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
    }
