import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client
from src.core.state import MainState
from src.prompt.validation_prompt import SYSTEM_PROMPT, USER_PROMPT


ValidationResultValue = Literal["PASS", "FAIL", "INCONCLUSIVE"]


class ValidationResult(BaseModel):
    validation_result: ValidationResultValue = Field(
        description="Whether the generated final response is grounded and adequate.",
    )
    final_response: str = Field(
        description="Final Korean response for the user.",
    )


def validation_node(state: MainState) -> dict:
    client = get_llm_client().with_structured_output(ValidationResult)
    validation = client.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT.format(
                    user_question=state["user_question"],
                    db_name=state["db_name"],
                    summary_result=state.get("summary_result", ""),
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
        "validation_result": validation.validation_result,
        "final_response": validation.final_response,
        "node_result": [
            {
                "node": "validation",
                "result": validation.model_dump(),
            }
        ],
    }
