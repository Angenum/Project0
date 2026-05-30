"""Схема состояния пайплайна с reducers для слияния словарей."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def _merge_dicts(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Reducer: глубокое слияние словарей (artifacts, flags, metadata)."""
    merged = dict(old)
    for key, value in new.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


class PipelineState(TypedDict):
    """Глобальное состояние графа."""

    # --- Входные данные ---
    goal: str
    requirements: str | None

    # --- Коммуникация с LLM ---
    messages: Annotated[list[BaseMessage], add_messages]

    # --- Артефакты пайплайна ---
    artifacts: Annotated[dict[str, Any], _merge_dicts]

    # --- Управление feedback loops ---
    retry_counters: Annotated[dict[str, int], _merge_dicts]
    flags: Annotated[dict[str, bool], _merge_dicts]

    # --- Метаданные и observability ---
    metadata: Annotated[dict[str, Any], _merge_dicts]
    current_step: str
    error: Any | None


def get_retry_count(state: PipelineState, key: str) -> int:
    """Безопасный getter для retry counter."""
    return state.get("retry_counters", {}).get(key, 0)


def get_flag(state: PipelineState, key: str, default: bool = False) -> bool:
    """Безопасный getter для флага."""
    return state.get("flags", {}).get(key, default)
