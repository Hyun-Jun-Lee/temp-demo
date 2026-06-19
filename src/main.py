from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.graph_builder import graph_builder


app = FastAPI(title="DA Ops Demo")
graph = graph_builder()


class GraphRequest(BaseModel):
    user_question: str = Field(min_length=1)
    db_name: str = Field(min_length=1)


class GraphResponse(BaseModel):
    final_response: str
    validation_result: str
    summary_result: str
    target_nodes: list[str]
    node_result: list[dict[str, Any]]


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/graph/invoke", response_model=GraphResponse)
def invoke_graph(request: GraphRequest) -> dict[str, Any]:
    initial_state = {
        "user_question": request.user_question,
        "db_name": request.db_name,
    }

    try:
        result = graph.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "final_response": result.get("final_response", ""),
        "validation_result": result.get("validation_result", ""),
        "summary_result": result.get("summary_result", ""),
        "target_nodes": result.get("target_nodes", []),
        "node_result": result.get("node_result", []),
    }
