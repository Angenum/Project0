# Project0 — Role-Chaining Pipeline (LangGraph)

Production-ready реализация 9-шагового пайплайна на LangGraph 0.3+:

1. Orchestrator — декомпозиция цели
2. Researcher — сбор контекста
3. Architect — проектирование ARD
4. TDD Engineer — написание тестов
5. Builder — реализация кода
6. Prompt Engineer — создание промпт-пакета
7. Tester — запуск тестов и отчёт
8. Critic — код-ревью
9. Security Auditor — аудит безопасности

## Быстрый старт

```bash
# 1. Установка
make install

# 2. Переменные окружения
cp .env.example .env
# Отредактируй .env, добавь OPENAI_API_KEY

# 3. Локальный запуск
make run

# 4. Тесты
make test

# 5. Docker (с Postgres)
make docker-up
```

## Архитектура

- **Single-LLM**: один `ChatOpenAI(gpt-4o)` с `bind(temperature, max_tokens)` per node
- **State**: `TypedDict` с `Annotated` reducers для артефактов и retry-счётчиков
- **Validation**: Pydantic-модели + fail-fast + retry (max 2)
- **Feedback Loops**: `add_conditional_edges` для Tester→Builder и Critic→Builder
- **Human-in-the-Loop**: `interrupt()` после Architect, Builder, Security Auditor
- **Checkpointing**: SQLite (local) / Postgres (production)
- **Cost Control**: токен-трекинг per step + budget guard + LangSmith tracing

## API Endpoints (FastAPI)

- `POST /pipeline` — запустить пайплайн
- `POST /pipeline/{thread_id}/resume` — resume после human approval
- `GET /pipeline/{thread_id}/state` — текущее состояние
- `GET /health` — health check
