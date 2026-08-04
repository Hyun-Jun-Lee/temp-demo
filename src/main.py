import json
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client
from src.core.report_charts import build_report_charts
from src.core.run_repository import (
    get_report_chat_messages,
    get_latest_node_statuses,
    get_report,
    get_run_events,
    init_db,
    list_reports,
    run_exists,
    save_report_chat_message,
    save_report,
    save_node_status,
)
from src.graph_builder import graph_builder
from src.prompt.report_chat_prompt import SYSTEM_PROMPT as REPORT_CHAT_SYSTEM_PROMPT
from src.prompt.report_chat_prompt import USER_PROMPT as REPORT_CHAT_USER_PROMPT


app = FastAPI(title="DA Ops Demo")
graph = graph_builder()
init_db()


class GraphRequest(BaseModel):
    user_question: str = Field(min_length=1)
    db_name: str = Field(min_length=1)


class GraphInvokeResponse(BaseModel):
    run_id: str
    run_status: str


class NodeRunRecord(BaseModel):
    run_id: str
    node_name: str
    node_status: str
    node_result: Any | None
    created_at: str


class RunStatusResponse(BaseModel):
    run_id: str
    node_statuses: list[NodeRunRecord]


class RunTasksResponse(BaseModel):
    run_id: str
    tasks: list[NodeRunRecord]


class ReportRecord(BaseModel):
    run_id: str
    report_result: Any
    created_at: str


class ReportListResponse(BaseModel):
    reports: list[ReportRecord]


class ReportChartsResponse(BaseModel):
    run_id: str
    charts: list[dict[str, Any]]


class ReportChatRequest(BaseModel):
    user_question: str = Field(min_length=1)


class ReportChatResult(BaseModel):
    answer: str
    cited_nodes: list[str]
    confidence_score: int = Field(ge=0, le=100)


class ReportChatMessage(BaseModel):
    id: int
    run_id: str
    role: str
    content: str
    metadata: Any | None
    created_at: str


class ReportChatHistoryResponse(BaseModel):
    run_id: str
    messages: list[ReportChatMessage]


class ReportChatResponse(BaseModel):
    run_id: str
    message: ReportChatMessage
    answer: str
    cited_nodes: list[str]
    confidence_score: int


class DatabaseRecord(BaseModel):
    db_name: str
    service_name: str
    role: str
    status: str


@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("src/static/index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/databases", response_model=list[DatabaseRecord])
def list_databases() -> list[dict[str, str]]:
    return [
        {
            "db_name": "TESTDB",
            "service_name": "testdb_svc",
            "role": "PRIMARY",
            "status": "OPEN",
        },
        {
            "db_name": "PAYDB",
            "service_name": "paydb_svc",
            "role": "PRIMARY",
            "status": "OPEN",
        },
        {
            "db_name": "APPDB",
            "service_name": "appdb_svc",
            "role": "PRIMARY",
            "status": "OPEN",
        },
        {
            "db_name": "DWDB",
            "service_name": "dwdb_svc",
            "role": "PRIMARY",
            "status": "OPEN",
        },
    ]


@app.post("/graph/invoke", response_model=GraphInvokeResponse)
def invoke_graph(
    request: GraphRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    run_id = str(uuid4())

    save_node_status(
        run_id=run_id,
        node_name="graph",
        node_status="QUEUED",
        node_result={
            "user_question": request.user_question,
            "db_name": request.db_name,
        },
    )
    background_tasks.add_task(
        run_graph,
        run_id,
        request.user_question,
        request.db_name,
    )

    return {
        "run_id": run_id,
        "run_status": "QUEUED",
    }


@app.get("/graph/runs/{run_id}/status", response_model=RunStatusResponse)
def get_run_status(run_id: str) -> dict[str, Any]:
    if not run_exists(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")

    return {
        "run_id": run_id,
        "node_statuses": get_latest_node_statuses(run_id),
    }


@app.get("/graph/runs/{run_id}/tasks", response_model=RunTasksResponse)
def get_run_tasks(run_id: str) -> dict[str, Any]:
    if not run_exists(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")

    return {
        "run_id": run_id,
        "tasks": get_run_events(run_id),
    }


@app.get("/reports", response_model=ReportListResponse)
def get_reports() -> dict[str, Any]:
    return {
        "reports": list_reports(),
    }


@app.get("/reports/{run_id}", response_model=ReportRecord)
def get_report_by_run_id(run_id: str) -> dict[str, Any]:
    report = get_report(run_id)

    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    return report


@app.get("/reports/{run_id}/charts", response_model=ReportChartsResponse)
def get_report_charts(run_id: str) -> dict[str, Any]:
    report = get_report(run_id)

    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    return {
        "run_id": run_id,
        "charts": build_report_charts(report["report_result"]),
    }


@app.get("/reports/{run_id}/chat", response_model=ReportChatHistoryResponse)
def get_report_chat(run_id: str) -> dict[str, Any]:
    if get_report(run_id) is None:
        raise HTTPException(status_code=404, detail="report not found")

    return {
        "run_id": run_id,
        "messages": get_report_chat_messages(run_id),
    }


@app.post("/reports/{run_id}/chat", response_model=ReportChatResponse)
def create_report_chat_message(
    run_id: str,
    request: ReportChatRequest,
) -> dict[str, Any]:
    report = get_report(run_id)

    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    question = request.user_question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="user_question is required")

    history_before = get_report_chat_messages(run_id)
    save_report_chat_message(run_id, "user", question)

    try:
        chat_result = _invoke_report_chat(
            user_question=question,
            report_result=report["report_result"],
            chat_history=history_before,
        )
    except Exception as exc:
        save_report_chat_message(
            run_id,
            "assistant",
            "답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            metadata={
                "error": str(exc),
                "confidence_score": 0,
                "cited_nodes": [],
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    metadata = {
        "cited_nodes": chat_result.cited_nodes,
        "confidence_score": chat_result.confidence_score,
    }
    assistant_message = save_report_chat_message(
        run_id,
        "assistant",
        chat_result.answer,
        metadata=metadata,
    )

    return {
        "run_id": run_id,
        "message": assistant_message,
        "answer": chat_result.answer,
        "cited_nodes": chat_result.cited_nodes,
        "confidence_score": chat_result.confidence_score,
    }


def run_graph(run_id: str, user_question: str, db_name: str) -> None:
    initial_state = {
        "run_id": run_id,
        "user_question": user_question,
        "db_name": db_name,
    }

    try:
        save_node_status(run_id, "graph", "RUNNING")
        result = graph.invoke(initial_state)
    except Exception as exc:
        save_node_status(run_id, "graph", "FAILED", {"error": str(exc)})
        return

    report_result = {
        "run_id": run_id,
        "db_name": db_name,
        "user_question": user_question,
        "final_response": result.get("final_response", ""),
        "validation_result": result.get("validation_result", ""),
        "summary_result": result.get("summary_result", ""),
        "target_nodes": result.get("target_nodes", []),
        "node_result": result.get("node_result", []),
    }

    save_report(run_id, report_result)
    save_node_status(run_id, "graph", "COMPLETE", report_result)


def _invoke_report_chat(
    user_question: str,
    report_result: dict[str, Any],
    chat_history: list[dict[str, Any]],
) -> ReportChatResult:
    client = get_llm_client().with_structured_output(ReportChatResult)

    return client.invoke(
        [
            SystemMessage(content=REPORT_CHAT_SYSTEM_PROMPT),
            HumanMessage(
                content=REPORT_CHAT_USER_PROMPT.format(
                    user_question=user_question,
                    report_result=json.dumps(
                        report_result,
                        ensure_ascii=False,
                        default=str,
                    ),
                    chat_history=json.dumps(
                        chat_history,
                        ensure_ascii=False,
                        default=str,
                    ),
                )
            ),
        ]
    )
