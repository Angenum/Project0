"""Интеграционные тесты mini-graph."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def _fake_llm(content: str) -> MagicMock:
    fake = MagicMock()
    fake.content = content
    fake.usage_metadata = {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
    return fake


def _fake_runnable(content: str) -> MagicMock:
    runnable = MagicMock()
    runnable.invoke.return_value = _fake_llm(content)
    return runnable


def test_linear_flow(memory_graph, base_state):
    """Граф проходит до interrupt на approve_architect после architect."""
    orchestrator_json = json.dumps({"steps": ["Step 1"], "dependencies": {}})
    researcher_json = json.dumps({"technologies": ["Python"], "constraints": [], "references": []})
    architect_json = json.dumps(
        {
            "components": [],
            "interfaces": [],
            "data_flow": [],
            "tech_stack": {"backend": "FastAPI"},
        }
    )

    with patch.multiple(
        "src.nodes",
        _orchestrator_runnable=_fake_runnable(orchestrator_json),
        _researcher_runnable=_fake_runnable(researcher_json),
        _architect_runnable=_fake_runnable(architect_json),
    ):
        config = {"configurable": {"thread_id": "test_001"}}
        result = memory_graph.invoke(base_state, config)
        assert result["current_step"] == "architect"
