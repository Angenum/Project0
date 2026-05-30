"""LangSmith tracing и конфигурация RunnableConfig per step."""

from __future__ import annotations

import os

from langchain_core.runnables import RunnableConfig


def get_step_config(step_name: str, thread_id: str) -> RunnableConfig:
    """RunnableConfig для LangSmith: каждый узел — отдельный run в trace tree."""
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "run_name": f"role_{step_name}",
        "tags": ["role-chaining", step_name, "project0"],
        "metadata": {
            "step": step_name,
            "pipeline": "role-chaining-pipeline",
            "project": "Project0",
            "env": os.getenv("ENV", "local"),
        },
    }


def init_langsmith() -> None:
    """Проверяет, что переменные окружения заданы."""
    if not os.getenv("LANGSMITH_API_KEY"):
        import warnings

        warnings.warn("LANGSMITH_API_KEY not set. Tracing disabled.", stacklevel=2)
