"""Конфигурация ролей и фабрика LLM-обёрток (single engine, many faces)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSerializable
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RoleConfig:
    """Настройки одной роли в пайплайне."""

    name: str
    system_prompt: str
    temperature: float
    max_tokens: int
    output_schema: Optional[dict[str, Any]] = None
    langsmith_tags: tuple[str, ...] = ()


# Единый базовый engine — без глобальных temperature/max_tokens
BASE_LLM: ChatOpenAI = ChatOpenAI(
    model="gpt-4o",
    streaming=False,
)


def create_role_runnable(config: RoleConfig) -> RunnableSerializable:
    """
    Создаёт изолированный runnable для конкретной роли.
    bind() не мутирует BASE_LLM.
    """
    bound_llm = BASE_LLM.bind(
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            ("placeholder", "{messages}"),
        ]
    )
    runnable: RunnableSerializable = prompt | bound_llm
    logger.debug(
        "Created runnable '%s' (temp=%.2f, max_tokens=%d)",
        config.name,
        config.temperature,
        config.max_tokens,
    )
    return runnable


def prepare_role_messages(
    config: RoleConfig,
    user_prompt: str,
    context_messages: Optional[list[BaseMessage]] = None,
) -> list[BaseMessage]:
    """Формирует список сообщений: SystemMessage + контекст + задача."""
    messages: list[BaseMessage] = [SystemMessage(content=config.system_prompt)]
    if context_messages:
        messages.extend(context_messages)
    messages.append(HumanMessage(content=user_prompt))
    return messages


# --- Реестр ролей ---
ROLES: dict[str, RoleConfig] = {
    "orchestrator": RoleConfig(
        name="orchestrator",
        system_prompt=(
            "You are an expert Software Architect and Project Manager. "
            "Decompose the user's goal into a structured execution plan. "
            "Output ONLY valid JSON matching the required schema."
        ),
        temperature=0.1,
        max_tokens=2048,
    ),
    "researcher": RoleConfig(
        name="researcher",
        system_prompt=(
            "You are a Research Analyst. Gather context, best practices, "
            "and relevant technology constraints for the given goal. "
            "Output ONLY valid JSON."
        ),
        temperature=0.2,
        max_tokens=4096,
    ),
    "architect": RoleConfig(
        name="architect",
        system_prompt=(
            "You are a Senior System Architect. Design Architecture Requirements Document (ARD). "
            "Include components, interfaces, data flow, and tech stack. "
            "Output ONLY valid JSON."
        ),
        temperature=0.1,
        max_tokens=4096,
    ),
    "tdd_engineer": RoleConfig(
        name="tdd_engineer",
        system_prompt=(
            "You are a TDD Expert. Write comprehensive test cases BEFORE implementation. "
            "Cover edge cases, failure modes, and integration scenarios. "
            "Output ONLY valid JSON with test suite."
        ),
        temperature=0.1,
        max_tokens=4096,
    ),
    "builder": RoleConfig(
        name="builder",
        system_prompt=(
            "You are a Senior Software Engineer. Implement production-ready code "
            "based on ARD and tests. Follow best practices, add docstrings, handle errors. "
            "Output ONLY valid JSON with code artifacts."
        ),
        temperature=0.3,
        max_tokens=8192,
    ),
    "prompt_engineer": RoleConfig(
        name="prompt_engineer",
        system_prompt=(
            "You are an LLM Prompt Engineer. Create optimized prompt templates "
            "and few-shot examples for the system. Output ONLY valid JSON."
        ),
        temperature=0.4,
        max_tokens=4096,
    ),
    "tester": RoleConfig(
        name="tester",
        system_prompt=(
            "You are a QA Automation Engineer. Execute tests, analyze coverage, "
            "and report pass/fail status with detailed logs. Output ONLY valid JSON."
        ),
        temperature=0.1,
        max_tokens=4096,
    ),
    "critic": RoleConfig(
        name="critic",
        system_prompt=(
            "You are a Code Reviewer. Perform strict review: style, bugs, security smells, "
            "performance. Output ONLY valid JSON with verdict and fix instructions."
        ),
        temperature=0.1,
        max_tokens=4096,
    ),
    "security_auditor": RoleConfig(
        name="security_auditor",
        system_prompt=(
            "You are a Security Auditor. Check for injection risks, secrets leakage, "
            "auth flaws, dependency vulnerabilities. Output ONLY valid JSON."
        ),
        temperature=0.1,
        max_tokens=4096,
    ),
}
