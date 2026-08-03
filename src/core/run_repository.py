import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("da_ops_demo.sqlite3")


def get_db_path() -> Path:
    return Path(os.getenv("DA_OPS_DB_PATH", DEFAULT_DB_PATH))


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_runs (
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                node_status TEXT NOT NULL,
                node_result TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                run_id TEXT PRIMARY KEY,
                report_result TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def save_node_status(
    run_id: str,
    node_name: str,
    node_status: str,
    node_result: Any | None = None,
) -> None:
    init_db()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO node_runs (
                run_id,
                node_name,
                node_status,
                node_result,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                node_name,
                node_status,
                _dump_json(node_result) if node_result is not None else None,
                _now(),
            ),
        )


def get_run_events(run_id: str) -> list[dict[str, Any]]:
    init_db()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, node_name, node_status, node_result, created_at
            FROM node_runs
            WHERE run_id = ?
            ORDER BY created_at ASC
            """,
            (run_id,),
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_latest_node_statuses(run_id: str) -> list[dict[str, Any]]:
    latest_by_node: dict[str, dict[str, Any]] = {}

    for event in get_run_events(run_id):
        latest_by_node[event["node_name"]] = event

    return list(latest_by_node.values())


def run_exists(run_id: str) -> bool:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM node_runs WHERE run_id = ? LIMIT 1",
            (run_id,),
        ).fetchone()

    return row is not None


def save_report(run_id: str, report_result: Any) -> None:
    init_db()

    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reports (
                run_id,
                report_result,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                run_id,
                _dump_json(report_result),
                _now(),
            ),
        )


def get_report(run_id: str) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT run_id, report_result, created_at
            FROM reports
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None

    return _report_row_to_dict(row)


def list_reports() -> list[dict[str, Any]]:
    init_db()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, report_result, created_at
            FROM reports
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [_report_row_to_dict(row) for row in rows]


def save_report_chat_message(
    run_id: str,
    role: str,
    content: str,
    metadata: Any | None = None,
) -> dict[str, Any]:
    init_db()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_chat_messages (
                run_id,
                role,
                content,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                role,
                content,
                _dump_json(metadata) if metadata is not None else None,
                _now(),
            ),
        )
        row = conn.execute(
            """
            SELECT id, run_id, role, content, metadata_json, created_at
            FROM report_chat_messages
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _chat_message_row_to_dict(row)


def get_report_chat_messages(run_id: str) -> list[dict[str, Any]]:
    init_db()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, run_id, role, content, metadata_json, created_at
            FROM report_chat_messages
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()

    return [_chat_message_row_to_dict(row) for row in rows]


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "node_name": row["node_name"],
        "node_status": row["node_status"],
        "node_result": _load_json(row["node_result"]),
        "created_at": row["created_at"],
    }


def _report_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "report_result": _load_json(row["report_result"]),
        "created_at": row["created_at"],
    }


def _chat_message_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "role": row["role"],
        "content": row["content"],
        "metadata": _load_json(row["metadata_json"]),
        "created_at": row["created_at"],
    }


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: str | None) -> Any | None:
    if value is None:
        return None

    return json.loads(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
