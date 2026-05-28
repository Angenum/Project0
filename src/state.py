"""Схема состояния пайплайна с reducers для слияния словарей."""
from __future__ import annotations

from typing import TypedDict, Annotated, Any, Optional
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
    requirements: Optional[str]

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
    error: Optional[str]
