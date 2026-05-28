"""Бюджетный контроллер и агрегация стоимости."""
from __future__ import annotations

import logging
from typing import Any

from .state import PipelineState
from .validation import estimate_cost

logger = logging.getLogger(__name__)

DEFAULT_BUDGET_USD = 5.0


def check_budget(state: PipelineState, step_name: str) -> dict[str, Any] | None:
    """Возвращает error-dict, если бюджет исчерпан. Иначе None."""
    meta = state.get("metadata", {})
    current_cost = meta.get("pipeline_total_cost_usd", 0.0)
    budget = meta.get("budget_usd", DEFAULT_BUDGET_USD)

    if current_cost >= budget:
        logger.error(
            "[%s] BUDGET EXCEEDED: $%.4f / $%.4f",
            step_name,
            current_cost,
            budget,
        )
        return {
            "error": f"Budget exceeded at step '{step_name}': ${current_cost:.4f} >= ${budget:.4f}",
            "current_step": step_name,
        }
    return None


def merge_step_usage(
    state: PipelineState, step_name: str, usage: dict[str, Any]
) -> dict[str, Any]:
    """Формирует обновление metadata с агрегированными токенами и стоимостью."""
    meta = state.get("metadata", {})
    steps_meta: dict[str, Any] = meta.get("steps", {})

    model = usage.get("model", "gpt-4o")
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cost = estimate_cost(model, inp, out)

    steps_meta[step_name] = {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cost_usd": round(cost, 6),
        "model": model,
    }

    total_cost = sum(s["cost_usd"] for s in steps_meta.values())
    total_tokens = sum(s["total_tokens"] for s in steps_meta.values())

    return {
        "metadata": {
            **meta,
            "steps": steps_meta,
            "pipeline_total_tokens": total_tokens,
            "pipeline_total_cost_usd": round(total_cost, 6),
            "budget_usd": meta.get("budget_usd", DEFAULT_BUDGET_USD),
        }
    }
