"""Реализация всех 9 узлов пайплайна + budget guard + validation."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableSerializable

from .cost_control import check_budget, merge_step_usage
from .metrics import STEP_COST, STEP_DURATION, STEP_TOKENS
from .roles import ROLES, create_role_runnable, prepare_role_messages
from .schemas import (
    ArchitectARD,
    BuilderCode,
    CriticReview,
    OrchestratorPlan,
    PromptPackage,
    ResearcherContext,
    SecurityAudit,
    TDDTestSuite,
    TesterReport,
    make_pipeline_error,
)
from .state import PipelineState
from .validation import ArtifactValidationError, invoke_with_validation

logger = logging.getLogger(__name__)

_orchestrator_runnable: RunnableSerializable[Any, Any] | None = None
_researcher_runnable: RunnableSerializable[Any, Any] | None = None
_architect_runnable: RunnableSerializable[Any, Any] | None = None
_tdd_runnable: RunnableSerializable[Any, Any] | None = None
_builder_runnable: RunnableSerializable[Any, Any] | None = None
_prompt_runnable: RunnableSerializable[Any, Any] | None = None
_tester_runnable: RunnableSerializable[Any, Any] | None = None
_critic_runnable: RunnableSerializable[Any, Any] | None = None
_security_runnable: RunnableSerializable[Any, Any] | None = None


def _get_runnable(attr: str, role: str) -> RunnableSerializable[Any, Any]:
    """Lazy-init runnable; поддерживает patch в тестах через globals()[attr]."""
    cached = globals().get(attr)
    if cached is not None:
        return cached
    runnable = create_role_runnable(ROLES[role])
    globals()[attr] = runnable
    return runnable


def _thread_id(state: PipelineState) -> str:
    return str(state.get("metadata", {}).get("thread_id", "unknown"))


def _validation_error(step: str, exc: Exception) -> dict[str, Any]:
    return {
        "error": make_pipeline_error(step, "validation", str(exc), retryable=True),
        "current_step": step,
    }


def _unknown_error(step: str, exc: Exception) -> dict[str, Any]:
    return {
        "error": make_pipeline_error(step, "unknown", str(exc), retryable=False),
        "current_step": step,
    }


def orchestrator_node(state: PipelineState) -> dict[str, Any]:
    """Узел 1: Декомпозиция цели."""
    step = "orchestrator"
    if stop := check_budget(state, step):
        return stop
    try:
        goal = state["goal"]
        messages = prepare_role_messages(
            ROLES["orchestrator"],
            f"Decompose the following goal into a structured plan:\n\n{goal}",
        )
        validated, usage = invoke_with_validation(
            _get_runnable("_orchestrator_runnable", "orchestrator"),
            messages,
            OrchestratorPlan,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=2,
        )
        cost_update = merge_step_usage(state, step, usage)
        STEP_TOKENS.labels(step_name=step, model=usage.get("model", "gpt-4o")).inc(
            usage.get("total_tokens", 0)
        )
        STEP_COST.labels(step_name=step, model=usage.get("model", "gpt-4o")).inc(
            usage.get("cost_usd", 0.0)
        )
        return {
            "artifacts": {"orchestrator_plan": validated.model_dump()},
            "messages": [HumanMessage(content="Orchestrator plan generated.")],
            "current_step": step,
            "metadata": cost_update["metadata"],
        }
    except ArtifactValidationError as exc:
        logger.exception("[%s] Failed", step, extra={"step": step, "thread_id": _thread_id(state)})
        return _validation_error(step, exc)
    except Exception as exc:
        logger.exception(
            "[%s] Unexpected error", step, extra={"step": step, "thread_id": _thread_id(state)}
        )
        return _unknown_error(step, exc)


def researcher_node(state: PipelineState) -> dict[str, Any]:
    """Узел 2: Сбор контекста."""
    step = "researcher"
    if stop := check_budget(state, step):
        return stop
    try:
        plan = state["artifacts"].get("orchestrator_plan", {})
        prompt = f"Research context and best practices for this plan:\n\n{plan}"
        messages = prepare_role_messages(ROLES["researcher"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_researcher_runnable", "researcher"),
            messages,
            ResearcherContext,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=2,
        )
        return {
            "artifacts": {"researcher_context": validated.model_dump()},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)


def architect_node(state: PipelineState) -> dict[str, Any]:
    """Узел 3: Проектирование ARD."""
    step = "architect"
    if stop := check_budget(state, step):
        return stop
    try:
        ctx = state["artifacts"].get("researcher_context", {})
        plan = state["artifacts"].get("orchestrator_plan", {})
        prompt = f"Design ARD based on plan and research context.\n\nPlan: {plan}\n\nContext: {ctx}"
        messages = prepare_role_messages(ROLES["architect"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_architect_runnable", "architect"),
            messages,
            ArchitectARD,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=2,
        )
        return {
            "artifacts": {"architect_ard": validated.model_dump()},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)


def tdd_engineer_node(state: PipelineState) -> dict[str, Any]:
    """Узел 4: Генерация тестов."""
    step = "tdd_engineer"
    if stop := check_budget(state, step):
        return stop
    try:
        ard = state["artifacts"].get("architect_ard", {})
        prompt = f"Write tests for the following ARD:\n\n{ard}"
        messages = prepare_role_messages(ROLES["tdd_engineer"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_tdd_runnable", "tdd_engineer"),
            messages,
            TDDTestSuite,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=2,
        )
        return {
            "artifacts": {"tdd_tests": validated.model_dump()},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)


def builder_node(state: PipelineState) -> dict[str, Any]:
    """Узел 5: Реализация кода с feedback-контекстом."""
    step = "builder"
    if stop := check_budget(state, step):
        return stop
    start = time.monotonic()
    try:
        ard = state["artifacts"].get("architect_ard", {})
        tests = state["artifacts"].get("tdd_tests", {})

        feedback_parts: list[str] = []
        if not state["flags"].get("tests_passed", True):
            report = state["artifacts"].get("tester_report", {})
            feedback_parts.append(
                f"[TESTER FEEDBACK] Failed: {report.get('failed_tests', [])}\nLogs: {report.get('logs', [])}"
            )
        if not state["flags"].get("critic_passed", True):
            review = state["artifacts"].get("critic_review", {})
            feedback_parts.append(f"[CRITIC FEEDBACK] Fix: {review.get('fix_instructions', [])}")
        feedback = "\n\n".join(feedback_parts) if feedback_parts else "No prior feedback."

        prompt = (
            f"Implement production-ready code based on ARD and tests.\n\n"
            f"ARD: {ard}\n\nTests: {tests}\n\n"
            f"Previous feedback:\n{feedback}\n\n"
            f"Output ONLY valid JSON matching BuilderCode schema."
        )
        messages = prepare_role_messages(ROLES["builder"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_builder_runnable", "builder"),
            messages,
            BuilderCode,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=2,
        )
        cost_update = merge_step_usage(state, step, usage)
        STEP_DURATION.labels(step_name=step).observe(time.monotonic() - start)
        STEP_TOKENS.labels(step_name=step, model=usage.get("model", "gpt-4o")).inc(
            usage.get("total_tokens", 0)
        )
        return {
            "artifacts": {"builder_code": validated.model_dump()},
            "flags": {"tests_passed": False, "critic_passed": False},
            "current_step": step,
            "metadata": cost_update["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)
    except Exception as exc:
        return _unknown_error(step, exc)


def prompt_engineer_node(state: PipelineState) -> dict[str, Any]:
    """Узел 6: Создание промпт-пакета."""
    step = "prompt_engineer"
    if stop := check_budget(state, step):
        return stop
    try:
        code = state["artifacts"].get("builder_code", {})
        prompt = f"Create prompt templates for this system:\n\n{code}"
        messages = prepare_role_messages(ROLES["prompt_engineer"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_prompt_runnable", "prompt_engineer"),
            messages,
            PromptPackage,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=2,
        )
        return {
            "artifacts": {"prompt_package": validated.model_dump()},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)


def tester_node(state: PipelineState) -> dict[str, Any]:
    """Узел 7: Запуск тестов. Устанавливает флаги и инкрементирует retry при fail."""
    step = "tester"
    if stop := check_budget(state, step):
        return stop
    try:
        code = state["artifacts"].get("builder_code", {})
        tests = state["artifacts"].get("tdd_tests", {})
        prompt = f"Execute tests against implementation.\n\nCode: {code}\n\nTests: {tests}"
        messages = prepare_role_messages(ROLES["tester"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_tester_runnable", "tester"),
            messages,
            TesterReport,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=1,
        )
        retries = state["retry_counters"].get("tester_builder", 0)
        if not validated.passed:
            retries += 1
            logger.warning("[%s] Tests FAILED. Retry counter=%d", step, retries)
        return {
            "artifacts": {"tester_report": validated.model_dump()},
            "flags": {"tests_passed": validated.passed},
            "retry_counters": {"tester_builder": retries},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)


def critic_node(state: PipelineState) -> dict[str, Any]:
    """Узел 8: Code review. Устанавливает флаги и инкрементирует retry при fail."""
    step = "critic"
    if stop := check_budget(state, step):
        return stop
    try:
        code = state["artifacts"].get("builder_code", {})
        prompt = f"Perform strict code review:\n\n{code}"
        messages = prepare_role_messages(ROLES["critic"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_critic_runnable", "critic"),
            messages,
            CriticReview,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=1,
        )
        retries = state["retry_counters"].get("critic_builder", 0)
        if not validated.passed:
            retries += 1
            logger.warning("[%s] Review FAILED. Retry counter=%d", step, retries)
        return {
            "artifacts": {"critic_review": validated.model_dump()},
            "flags": {"critic_passed": validated.passed},
            "retry_counters": {"critic_builder": retries},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)


def security_auditor_node(state: PipelineState) -> dict[str, Any]:
    """Узел 9: Security audit."""
    step = "security_auditor"
    if stop := check_budget(state, step):
        return stop
    try:
        code = state["artifacts"].get("builder_code", {})
        prompt = f"Audit security of this implementation:\n\n{code}"
        messages = prepare_role_messages(ROLES["security_auditor"], prompt)
        validated, usage = invoke_with_validation(
            _get_runnable("_security_runnable", "security_auditor"),
            messages,
            SecurityAudit,
            step_name=step,
            thread_id=_thread_id(state),
            max_retries=1,
        )
        return {
            "artifacts": {"security_audit": validated.model_dump()},
            "current_step": step,
            "metadata": merge_step_usage(state, step, usage)["metadata"],
        }
    except ArtifactValidationError as exc:
        return _validation_error(step, exc)
