"""Pytest fixtures."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from src.graph import build_pipeline


@pytest.fixture
def memory_graph():
    """Граф с in-memory checkpointer для быстрых тестов."""
    return build_pipeline(checkpointer=InMemorySaver())


@pytest.fixture
def base_state():
    """Чистое начальное состояние."""
    return {
        "goal": "Test goal",
        "requirements": None,
        "messages": [],
        "artifacts": {},
        "retry_counters": {},
        "flags": {},
        "metadata": {},
        "current_step": "",
        "error": None,
    }
