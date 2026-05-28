"""Pydantic-контракты для всех артефактов пайплайна."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrchestratorPlan(BaseModel):
    steps: List[str] = Field(description="Пошаговый план реализации")
    dependencies: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Граф зависимостей между шагами",
    )


class ResearcherContext(BaseModel):
    technologies: List[str] = Field(description="Рекомендуемый стек")
    constraints: List[str] = Field(description="Ограничения и риски")
    references: List[str] = Field(default_factory=list)


class ArchitectARD(BaseModel):
    components: List[Dict[str, Any]] = Field(description="Компоненты системы")
    interfaces: List[Dict[str, Any]] = Field(description="Интерфейсы между компонентами")
    data_flow: List[str] = Field(description="Потоки данных")
    tech_stack: Dict[str, str] = Field(description="Технологический стек")


class TDDTestSuite(BaseModel):
    tests: List[Dict[str, Any]] = Field(description="Список тест-кейсов")
    coverage_target: float = Field(
        default=80.0,
        ge=0,
        le=100,
        description="Целевое покрытие в процентах",
    )


class BuilderCode(BaseModel):
    files: List[Dict[str, str]] = Field(
        description="Файлы: [{'filename': '...', 'content': '...'}]",
    )
    entrypoint: str = Field(description="Точка входа в приложение")
    dependencies: List[str] = Field(default_factory=list)


class TesterReport(BaseModel):
    passed: bool = Field(description="Все ли тесты пройдены")
    coverage: float = Field(ge=0, le=100)
    logs: List[str] = Field(default_factory=list)
    failed_tests: List[str] = Field(default_factory=list)


class CriticReview(BaseModel):
    passed: bool = Field(description="Код принят ревьюером")
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    fix_instructions: List[str] = Field(default_factory=list)


class SecurityAudit(BaseModel):
    passed: bool = Field(description="Аудит пройден")
    risks: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
