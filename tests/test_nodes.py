"""Unit-тесты отдельных узлов с моками LLM."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from src.nodes import orchestrator_node, builder_node
from src.state import PipelineState


def make_state(overrides: dict[str, Any] | None = None) -> PipelineState:
    base: PipelineState = {
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
    if overrides:
        base.update(overrides)  # type: ignore[typeddict-item]
    return base


@pytest.fixture
def valid_json_plan():
    return json.dumps({"steps": ["Step 1"], "dependencies": {}})


def test_orchestrator_success(valid_json_plan: str):
    state = make_state({"goal": "Build a chatbot"})
    fake = MagicMock()
    fake.content = valid_json_plan
    fake.usage_metadata = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}

    with patch("src.nodes._orchestrator_runnable") as mock:
        mock.invoke.return_value = fake
        result = orchestrator_node(state)

    assert "orchestrator_plan" in result.get("artifacts", {})
    assert result["current_step"] == "orchestrator"
    assert result.get("error") is None
    assert result["metadata"]["steps"]["orchestrator"]["input_tokens"] == 100


def test_orchestrator_validation_failure():
    state = make_state({"goal": "Bad"})
    fake = MagicMock()
    fake.content = "not json"

    with patch("src.nodes._orchestrator_runnable") as mock:
        mock.invoke.return_value = fake
        result = orchestrator_node(state)

    assert result.get("error") is not None
    assert "orchestrator_plan" not in result.get("artifacts", {})


def test_builder_reads_feedback():
    state = make_state({
        "artifacts": {
            "architect_ard": {"components": []},
            "tdd_tests": {"tests": []},
            "tester_report": {"failed_tests": ["test_a"], "logs": ["error"]},
        },
        "flags": {"tests_passed": False, "critic_passed": True},
    })
    fake = MagicMock()
    fake.content = json.dumps({"files": [], "entrypoint": "main.py", "dependencies": []})
    fake.usage_metadata = {"input_tokens": 200, "output_tokens": 100, "total_tokens": 300}

    with patch("src.nodes._builder_runnable") as mock:
        mock.invoke.return_value = fake
        result = builder_node(state)

    assert "builder_code" in result.get("artifacts", {})
    assert result["flags"]["tests_passed"] is False  # сброшено для нового цикла
