"""Human-in-the-Loop узлы с interrupt()."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langgraph.types import interrupt

from .schemas import make_pipeline_error
from .state import PipelineState

logger = logging.getLogger(__name__)


def make_approval_node(
    step_name: str, artifact_key: str
) -> Callable[[PipelineState], dict[str, Any]]:
    """Фабрика approval-узлов. Ожидает {"action": "approve"} или {"action": "reject", "feedback": "..."}."""

    def approval_node(state: PipelineState) -> dict[str, Any]:
        artifact = state["artifacts"].get(artifact_key, {})
        human_response = interrupt(
            {
                "step": step_name,
                "task": f"Review and approve the output from '{step_name}'",
                "artifact_preview": str(artifact)[:2000],
                "artifact_key": artifact_key,
            }
        )
        action = human_response.get("action") if isinstance(human_response, dict) else "reject"
        feedback = (
            human_response.get("feedback", "No feedback")
            if isinstance(human_response, dict)
            else str(human_response)
        )
        if action == "approve":
            logger.info("[%s_approval] Approved", step_name)
            return {
                "flags": {f"{step_name}_approved": True},
                "current_step": f"{step_name}_approved",
            }
        logger.warning("[%s_approval] Rejected: %s", step_name, feedback)
        return {
            "flags": {f"{step_name}_approved": False},
            "error": make_pipeline_error(
                step_name,
                "human_reject",
                f"Human rejected {step_name}: {feedback}",
                retryable=False,
            ),
            "current_step": f"{step_name}_rejected",
        }

    return approval_node


approve_architect = make_approval_node("architect", "architect_ard")
approve_builder = make_approval_node("builder", "builder_code")
approve_security = make_approval_node("security_auditor", "security_audit")
