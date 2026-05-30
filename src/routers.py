"""Conditional edge functions для feedback loops и approval."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Literal

from .state import PipelineState

logger = logging.getLogger(__name__)


def _is_human_rejection(state: PipelineState) -> bool:
    error = state.get("error")
    if not error:
        return False
    if isinstance(error, dict):
        return error.get("category") == "human_reject"
    return "Human rejected" in str(error)


def make_route_unless_error(next_node: str) -> Callable[[PipelineState], str]:
    """Фабрика: при error -> END, иначе -> next_node."""

    def _route(state: PipelineState) -> str:
        if state.get("error"):
            return "__end__"
        return next_node

    return _route


def route_after_tester(state: PipelineState) -> Literal["builder", "critic", "__end__"]:
    """Маршрут после Tester."""
    if state.get("error"):
        return "__end__"
    passed = state["flags"].get("tests_passed", True)
    retries = state["retry_counters"].get("tester_builder", 0)
    if not passed:
        if retries < 2:
            logger.info("[router] Tests fail (retry=%d/2) -> builder", retries)
            return "builder"
        logger.warning("[router] Tester retries exhausted -> critic")
    return "critic"


def route_after_critic(state: PipelineState) -> Literal["builder", "security_auditor", "__end__"]:
    """Маршрут после Critic."""
    if state.get("error"):
        return "__end__"
    passed = state["flags"].get("critic_passed", True)
    retries = state["retry_counters"].get("critic_builder", 0)
    if not passed:
        if retries < 2:
            logger.info("[router] Critic fail (retry=%d/2) -> builder", retries)
            return "builder"
        logger.warning("[router] Critic retries exhausted -> security_auditor")
    return "security_auditor"


def route_after_approval(state: PipelineState) -> str:
    """Если human rejected — останавливаем граф."""
    if _is_human_rejection(state):
        return "__end__"
    return "__continue__"


def route_after_builder(state: PipelineState) -> Literal["builder", "approve_builder", "__end__"]:
    """После builder: retry при retryable error, иначе approval или END."""
    error = state.get("error")
    if error:
        if isinstance(error, dict) and error.get("retryable") and error.get("step") == "builder":
            logger.info("[router] Retryable builder error -> builder")
            return "builder"
        return "__end__"
    return "approve_builder"
