## Контекст

Я разработчик, который ранее создал собственный фреймворк «Role-Chaining Pipeline» (Project0) для решения сложных многошаговых задач через последовательную смену ролей одной LLM. Пайплайн состоит из 9 шагов:

1. Orchestrator — декомпозиция цели
2. Researcher — сбор контекста
3. Architect — проектирование архитектуры (ARD)
4. TDD Engineer — написание тестов
5. Builder — реализация кода
6. Prompt Engineer — создание промпт-пакета
7. Tester — запуск тестов и отчёт
8. Critic — код-ревью
9. Security Auditor — аудит безопасности

Каждый шаг генерирует JSON-артефакт, который валидируется по JSON Schema и передаётся следующему шагу. Есть feedback loops (Tester→Builder, Critic→Builder) и fail-fast валидация.

Я хочу мигрировать эту концепцию на LangGraph, сохранив:
- Возможность работы на одной LLM (например, GPT-4o), но с разными параметрами (temperature, max_tokens, system prompt) для каждой роли
- Полную тестируемость каждого узла изолированно (unit-тесты)
- Контролируемость: checkpointing, resume после сбоя, human-in-the-loop точки для утверждения артефактов
- Feedback loops как first-class citizens (не костыли в while-цикле)
- Артефактную модель с JSON Schema валидацией между узлами
- Лимиты на токены/стоимость на шаг

## Задача

Проведи меня по LangGraph от установки до production-ready реализации моего пайплайна.

### Формат ответа

1. **Архитектура**: Как мои 9 ролей отобразить на LangGraph-абстракции (StateGraph, Nodes, Edges, Conditional Edges)? Какая структура state подойдёт для хранения артефактов?
2. **Single-LLM + Role Config**: Покажи паттерн использования одной модели (ChatOpenAI) с разными `bind(temperature=..., max_tokens=...)` и разными system prompts для каждого узла. Как избежать «загрязнения» системного промпта между узлами?
3. **Валидация артефактов**: Где и как встроить JSON Schema валидацию (например, через Pydantic модели или jsonschema) между узлами? Как реализовать fail-fast с retry?
4. **Feedback Loops**: Как реализовать Tester→Builder (макс. 2 ретрая) и Critic→Builder через conditional edges? Покажи код с `add_conditional_edges`.
5. **Human-in-the-Loop**: Где встроить `interrupt` после Architect, Builder и Security Auditor? Как resume работает после human approval?
6. **Тестируемость**: Как писать unit-тесты для отдельных узлов без запуска всего графа? Покажи пример pytest для одного узла.
7. **Checkpointing & Resume**: Как настроить persistence (SQLite/Postgres) для checkpointing? Как продолжить выполнение с конкретного шага после падения?
8. **Cost Control**: Как отслеживать токены/стоимость на уровне шага? Интеграция с LangSmith для tracing.
9. **Пошаговый план**: Дай roadmap из 5-7 итераций, чтобы я мог двигаться incrementally от простого графа к полному пайплайну.

### Ограничения

- Используй Python, langgraph &gt;= 0.3, langchain-openai
- Не предлагай CrewAI, Swarm или другие фреймворки — только LangGraph
- Код должен быть production-ready (type hints, error handling, logging)
- Предполагай, что я запускаю это локально, но планирую deploy в контейнере

### Что я уже знаю

- Python, Pydantic, asyncio
- OpenAI API, JSON Schema
- Основы LangChain (LLMChain, PromptTemplate)
- Не знаю: LangGraph StateGraph, checkpointing, interrupts, conditional edges

Начни с раздела 1 (Архитектура) и 2 (Single-LLM + Role Config). Давай код с комментариями на русском.