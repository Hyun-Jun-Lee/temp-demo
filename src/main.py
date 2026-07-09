from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.core.run_repository import (
    get_latest_node_statuses,
    get_report,
    get_run_events,
    init_db,
    list_reports,
    run_exists,
    save_report,
    save_node_status,
)
from src.graph_builder import graph_builder


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
            "db_name": "LOGDB",
            "service_name": "logdb_svc",
            "role": "STANDBY",
            "status": "READ ONLY",
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
