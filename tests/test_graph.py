"""Интеграционные тесты mini-graph."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.state import PipelineState


def test_linear_flow(memory_graph, base_state):
    """Проверяем, что граф проходит от START до interrupt после architect."""
    fake = MagicMock()
    fake.content = '{"result": "ok"}'
    fake.usage_metadata = {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}

    with patch.multiple(
        "src.nodes",
        _orchestrator_runnable=MagicMock(invoke=MagicMock(return_value=fake)),
        _researcher_runnable=MagicMock(invoke=MagicMock(return_value=fake)),
        _architect_runnable=MagicMock(invoke=MagicMock(return_value=fake)),
    ):
        config = {"configurable": {"thread_id": "test_001"}}
        result = memory_graph.invoke(base_state, config)
        # При interrupt_after узел architect отработает, затем граф остановится
        assert result["current_step"] == "architect"
