"""Фабрика checkpointer: SQLite (local) или Postgres (production)."""
from __future__ import annotations

import os
from typing import Any

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    from langgraph_checkpoint_sqlite import SqliteSaver  # type: ignore[no-redef]

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    from langgraph_checkpoint_postgres import PostgresSaver  # type: ignore[no-redef]


def get_checkpointer() -> Any:
    """Возвращает checkpointer в зависимости от окружения."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        saver = PostgresSaver.from_conn_string(db_url)
        saver.setup()
        return saver
    sqlite_path = os.getenv("CHECKPOINT_DB", "checkpoints.db")
    return SqliteSaver.from_conn_string(sqlite_path)


async def close_checkpointer(checkpointer: Any) -> None:
    """Graceful shutdown для async checkpointer."""
    if checkpointer is None:
        return
    if hasattr(checkpointer, "close"):
        await checkpointer.close()
    elif hasattr(checkpointer, "__aexit__"):
        await checkpointer.__aexit__(None, None, None)
