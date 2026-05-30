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

# 3. Локальный запуск (CLI, sync SqliteSaver)
make run

# 4. Тесты
make test

# 5. Docker (AsyncSqliteSaver → файл /data/checkpoints.db)
make docker-up
```

## Checkpointing (LangGraph)

По [доке LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence):

| Backend | Checkpointer | Когда |
|---------|--------------|-------|
| `sqlite` (default) | `SqliteSaver` / `AsyncSqliteSaver` | Локально, demo, Docker — один файл `checkpoints.db` |
| `memory` | `InMemorySaver` | Тесты, отладка (state не переживает рестарт) |
| `postgres` | `PostgresSaver` / `AsyncPostgresSaver` | Production (`pip install -e ".[postgres]"`) |

```bash
# .env
CHECKPOINT_BACKEND=sqlite
CHECKPOINT_DB=checkpoints.db

# Postgres (optional)
CHECKPOINT_BACKEND=postgres
DATABASE_URL=postgresql://...
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up
```

Checkpoint хранит **state графа** для HITL resume (`interrupt` → `Command(resume=...)`).
Это не deliverables (plan/ARD/code) — они в `state["artifacts"]`.

## Архитектура

- **Single-LLM**: один `ChatOpenAI(gpt-4o)` с `bind(temperature, max_tokens)` per node
- **State**: `TypedDict` с `Annotated` reducers для артефактов и retry-счётчиков
- **Validation**: Pydantic-модели + fail-fast + retry (max 2)
- **Feedback Loops**: `add_conditional_edges` для Tester→Builder и Critic→Builder
- **Human-in-the-Loop**: `interrupt()` после Architect, Builder, Security Auditor
- **Cost Control**: токен-трекинг per step + budget guard + LangSmith tracing

## API Endpoints (FastAPI)

- `POST /pipeline` — запустить пайплайн
- `POST /pipeline/stream` — SSE streaming
- `POST /pipeline/{thread_id}/resume` — resume после human approval
- `GET /pipeline/{thread_id}/state` — текущее состояние
- `GET /health` — health check
