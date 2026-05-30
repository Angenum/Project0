"""Движок валидации артефактов с retry и cost-трекингом."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig, RunnableSerializable
from pydantic import BaseModel, ValidationError

from .observability import get_step_config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ArtifactValidationError(Exception):
    """Артефакт не прошёл JSON Schema / Pydantic валидацию."""

    pass


def _extract_content(response: Any) -> str:
    return str(response.content) if hasattr(response, "content") else str(response)


def _strip_markdown_fences(raw: str) -> str:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def parse_json_output(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(_strip_markdown_fences(raw))
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ArtifactValidationError("Expected JSON object")
    return data


def validate_artifact(raw_output: str, schema_cls: type[T]) -> T:
    data = parse_json_output(raw_output)
    try:
        return schema_cls.model_validate(data)
    except ValidationError as exc:
        raise ArtifactValidationError(f"Schema validation failed: {exc}") from exc


# Ценообразование OpenAI (per 1M tokens)
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, PRICING["gpt-4o"])
    return (input_tokens * p["input"]) + (output_tokens * p["output"])


def invoke_with_validation(
    runnable: RunnableSerializable[Any, Any],
    messages: list[BaseMessage],
    schema_cls: type[T],
    step_name: str,
    thread_id: str,
    model: str = "gpt-4o",
    max_retries: int = 2,
) -> tuple[T, dict[str, Any]]:
    """
    Вызывает LLM, валидирует JSON, при ошибке retry.
    Возвращает (validated_model, usage_metadata).
    """
    last_error: ArtifactValidationError | None = None
    current_messages = list(messages)
    config: RunnableConfig = get_step_config(step_name, thread_id)

    for attempt in range(max_retries + 1):
        try:
            response = runnable.invoke({"messages": current_messages}, config=config)
            content = _extract_content(response)
            validated = validate_artifact(content, schema_cls)

            usage: dict[str, Any] = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                usage = {
                    "input_tokens": um.get("input_tokens", 0),
                    "output_tokens": um.get("output_tokens", 0),
                    "total_tokens": um.get("total_tokens", 0),
                    "model": model,
                }
                cost = estimate_cost(model, usage["input_tokens"], usage["output_tokens"])
                usage["cost_usd"] = cost
                logger.info(
                    "[%s] Tokens in=%d out=%d cost=$%.6f",
                    step_name,
                    usage["input_tokens"],
                    usage["output_tokens"],
                    cost,
                )
            return validated, usage

        except ArtifactValidationError as exc:
            last_error = exc
            logger.warning(
                "[%s] Validation failed attempt %d/%d: %s",
                step_name,
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if attempt < max_retries:
                current_messages.append(
                    HumanMessage(
                        content=(
                            f"Your previous response failed validation: {exc}. "
                            f"Please output ONLY valid JSON strictly matching the required schema. "
                            f"Attempt {attempt + 2} of {max_retries + 1}."
                        )
                    )
                )

    assert last_error is not None
    raise ArtifactValidationError(
        f"Failed after {max_retries} retries. Last error: {last_error}"
    ) from last_error
