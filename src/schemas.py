"""Pydantic-контракты для всех артефактов пайплайна."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class OrchestratorPlan(BaseModel):
    steps: list[str] = Field(description="Пошаговый план реализации")
    dependencies: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Граф зависимостей между шагами",
    )


class ResearcherContext(BaseModel):
    technologies: list[str] = Field(description="Рекомендуемый стек")
    constraints: list[str] = Field(description="Ограничения и риски")
    references: list[str] = Field(default_factory=list)


class ArchitectARD(BaseModel):
    components: list[dict[str, Any]] = Field(description="Компоненты системы")
    interfaces: list[dict[str, Any]] = Field(description="Интерфейсы между компонентами")
    data_flow: list[str] = Field(description="Потоки данных")
    tech_stack: dict[str, str] = Field(description="Технологический стек")


class TDDTestSuite(BaseModel):
    tests: list[dict[str, Any]] = Field(description="Список тест-кейсов")
    coverage_target: float = Field(
        default=80.0,
        ge=0,
        le=100,
        description="Целевое покрытие в процентах",
    )


class BuilderCode(BaseModel):
    files: list[dict[str, str]] = Field(
        description="Файлы: [{'filename': '...', 'content': '...'}]",
    )
    entrypoint: str = Field(description="Точка входа в приложение")
    dependencies: list[str] = Field(default_factory=list)


class PromptPackage(BaseModel):
    """Промпт-пакет: системные промпты, few-shot примеры и шаблоны."""

    system_prompts: dict[str, str] = Field(
        default_factory=dict,
        description="Системные промпты по ролям: {'orchestrator': '...'}",
    )
    few_shots: list[dict[str, str]] = Field(
        default_factory=list,
        description="Few-shot примеры: [{'input': '...', 'output': '...'}]",
    )
    templates: dict[str, str] = Field(
        default_factory=dict,
        description="Jinja2-шаблоны: {'user_query': 'Hello {{name}}'}",
    )
    version: str = Field(default="1.0.0", description="Версия промпт-пакета")


class TesterReport(BaseModel):
    passed: bool = Field(description="Все ли тесты пройдены")
    coverage: float = Field(ge=0, le=100)
    logs: list[str] = Field(default_factory=list)
    failed_tests: list[str] = Field(default_factory=list)


class CriticReview(BaseModel):
    passed: bool = Field(description="Код принят ревьюером")
    issues: list[dict[str, Any]] = Field(default_factory=list)
    fix_instructions: list[str] = Field(default_factory=list)


class SecurityAudit(BaseModel):
    passed: bool = Field(description="Аудит пройден")
    risks: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class PipelineError(BaseModel):
    """Типизированная ошибка пайплайна с метаданными для роутинга."""

    step: str = Field(description="Узел, где произошла ошибка")
    category: Literal["validation", "budget", "llm_timeout", "human_reject", "unknown"] = Field(
        description="Категория ошибки",
    )
    message: str = Field(description="Человекочитаемое описание")
    retryable: bool = Field(description="Можно ли retry")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


def make_pipeline_error(
    step: str,
    category: Literal["validation", "budget", "llm_timeout", "human_reject", "unknown"],
    message: str,
    *,
    retryable: bool,
) -> dict[str, Any]:
    return PipelineError(
        step=step,
        category=category,
        message=message,
        retryable=retryable,
    ).model_dump()
