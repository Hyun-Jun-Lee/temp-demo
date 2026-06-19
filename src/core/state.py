from operator import add
from typing import Annotated, NotRequired, TypedDict


class MainState(TypedDict):
    db_name: str
    user_question: str

    node_result: NotRequired[Annotated[list, add]]
    target_nodes: NotRequired[list[str]]
    summary_result: NotRequired[str]
    validation_result: NotRequired[str]
    final_response: NotRequired[str]
