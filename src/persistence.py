"""Фабрика checkpointer: SQLite (local) или Postgres (production)."""

from __future__ import annotations

import os
import sqlite3
from typing import Any, cast

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    from langgraph_checkpoint_sqlite import SqliteSaver  # type: ignore[no-redef]

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    from langgraph_checkpoint_postgres import PostgresSaver  # type: ignore[no-redef]

_holder: dict[str, Any] = {"saver": None, "conn": None}


def get_checkpointer() -> Any:
    """Возвращает singleton checkpointer с открытым соединением."""
    if _holder["saver"] is not None:
        return _holder["saver"]

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        from psycopg import Connection
        from psycopg.rows import dict_row

        conn = Connection.connect(
            db_url,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        saver = PostgresSaver(conn)
        saver.setup()
        _holder["conn"] = conn
        _holder["saver"] = saver
        return saver

    sqlite_path = os.getenv("CHECKPOINT_DB", "checkpoints.db")
    sqlite_conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    sqlite_saver = SqliteSaver(sqlite_conn)
    _holder["conn"] = cast(Any, sqlite_conn)
    _holder["saver"] = cast(Any, sqlite_saver)
    return sqlite_saver


async def close_checkpointer(checkpointer: Any | None = None) -> None:
    """Graceful shutdown для checkpointer и его соединения."""
    if checkpointer is None:
        checkpointer = _holder["saver"]

    if checkpointer is not None and hasattr(checkpointer, "close"):
        await checkpointer.close()

    conn = _holder["conn"]
    if conn is not None:
        close = getattr(conn, "close", None)
        if callable(close):
            close()
        _holder["conn"] = None
        _holder["saver"] = None
