"""Conditional edge functions для feedback loops и approval."""
from __future__ import annotations

import logging
from typing import Literal

from .state import PipelineState

logger = logging.getLogger(__name__)


def route_after_tester(state: PipelineState) -> Literal["builder", "critic"]:
    """Маршрут после Tester."""
    passed = state["flags"].get("tests_passed", True)
    retries = state["retry_counters"].get("tester_builder", 0)
    if not passed:
        if retries <= 2:
            logger.info("[router] Tests fail (retry=%d/2) -> builder", retries)
            return "builder"
        logger.warning("[router] Tester retries exhausted -> critic")
    return "critic"


def route_after_critic(state: PipelineState) -> Literal["builder", "security_auditor"]:
    """Маршрут после Critic."""
    passed = state["flags"].get("critic_passed", True)
    retries = state["retry_counters"].get("critic_builder", 0)
    if not passed:
        if retries <= 2:
            logger.info("[router] Critic fail (retry=%d/2) -> builder", retries)
            return "builder"
        logger.warning("[router] Critic retries exhausted -> security_auditor")
    return "security_auditor"


def route_after_approval(state: PipelineState) -> str:
    """Если human rejected — останавливаем граф."""
    if state.get("error") and "Human rejected" in state["error"]:
        return "__end__"
    return "__continue__"


def route_on_error(state: PipelineState) -> Literal["__end__", "builder"]:
    """Если ошибка retryable — возвращаемся к builder для recovery. Иначе — END."""
    error = state.get("error")
    if isinstance(error, dict) and error.get("retryable"):
        logger.info("[router] Retryable error at %s -> builder", error.get("step"))
        return "builder"
    return "__end__"
