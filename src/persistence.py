"""LangGraph checkpointers — официальные backend'ы.

Рекомендации LangGraph (https://docs.langchain.com/oss/python/langgraph/persistence):
- InMemorySaver       — тесты и отладка
- SqliteSaver         — sync CLI, локальные demo (файл checkpoints.db)
- AsyncSqliteSaver    — async FastAPI (aiosqlite)
- PostgresSaver       — production (optional extra, CHECKPOINT_BACKEND=postgres)
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None  # type: ignore[misc, assignment]

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ImportError:
    AsyncSqliteSaver = None  # type: ignore[misc, assignment]

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None  # type: ignore[misc, assignment]


def checkpoint_backend() -> str:
    """memory | sqlite (default) | postgres."""
    return os.getenv("CHECKPOINT_BACKEND", "sqlite").lower()


def sqlite_path() -> str:
    return os.getenv("CHECKPOINT_DB", "checkpoints.db")


def create_sync_checkpointer() -> Any:
    """Sync checkpointer для CLI и graph.stream()."""
    backend = checkpoint_backend()

    if backend == "memory":
        return InMemorySaver()

    if backend == "postgres":
        if PostgresSaver is None:
            raise RuntimeError(
                "Postgres checkpointer requires: pip install -e '.[postgres]'"
            )
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("CHECKPOINT_BACKEND=postgres requires DATABASE_URL")

        from psycopg import Connection
        from psycopg.rows import dict_row

        pg_conn = Connection.connect(
            db_url,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        saver = PostgresSaver(pg_conn)
        saver.setup()
        return saver

    # sqlite — рекомендованный LangGraph backend для local/small projects
    conn = sqlite3.connect(sqlite_path(), check_same_thread=False)
    return SqliteSaver(conn)


# Alias для обратной совместимости
get_checkpointer = create_sync_checkpointer


@asynccontextmanager
async def async_checkpointer_lifecycle() -> AsyncIterator[Any]:
    """Async checkpointer lifecycle для FastAPI (async with по доке LangGraph)."""
    backend = checkpoint_backend()

    if backend == "memory":
        yield InMemorySaver()
        return

    if backend == "postgres":
        if AsyncPostgresSaver is None:
            raise RuntimeError(
                "Async Postgres checkpointer requires: pip install -e '.[postgres]'"
            )
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("CHECKPOINT_BACKEND=postgres requires DATABASE_URL")

        async with AsyncPostgresSaver.from_conn_string(db_url) as saver:
            await saver.setup()
            yield saver
        return

    if AsyncSqliteSaver is None:
        raise RuntimeError(
            "Async SQLite checkpointer requires: pip install aiosqlite"
        )

    async with AsyncSqliteSaver.from_conn_string(sqlite_path()) as saver:
        yield cast(Any, saver)
