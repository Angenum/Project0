"""FastAPI обёртка для пайплайна с SSE streaming и graceful shutdown."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from .graph import build_pipeline
from .persistence import get_checkpointer
from .state import PipelineState


# --- JSON structured logging ---
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "step"):
            log["step"] = record.step
        if hasattr(record, "thread_id"):
            log["thread_id"] = record.thread_id
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JSONFormatter())
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)

# Глобальный граф (singleton)
_graph: CompiledStateGraph | None = None
_checkpointer: Any | None = None


def _require_graph() -> CompiledStateGraph:
    if _graph is None:
        raise HTTPException(status_code=503, detail="Pipeline graph is not initialized")
    return _graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _checkpointer
    _checkpointer = get_checkpointer()
    _graph = build_pipeline(checkpointer=_checkpointer)
    logger.info("Pipeline graph compiled", extra={"step": "init", "thread_id": "system"})
    yield
    if _checkpointer and hasattr(_checkpointer, "close"):
        await _checkpointer.close()
        logger.info("Checkpointer closed", extra={"step": "shutdown", "thread_id": "system"})


app = FastAPI(title="Project0 Role-Chaining Pipeline", lifespan=lifespan)


class PipelineRequest(BaseModel):
    goal: str = Field(description="Цель проекта")
    requirements: str | None = Field(default=None, description="Доп. требования")
    thread_id: str | None = Field(default=None, description="ID потока (опционально)")
    budget_usd: float = Field(default=5.0, ge=0.1, le=100.0)


class ResumeRequest(BaseModel):
    action: str = Field(description="approve или reject")
    feedback: str = Field(default="", description="Обратная связь при reject")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/pipeline")
async def run_pipeline(req: PipelineRequest) -> dict[str, Any]:
    thread_id = req.thread_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: PipelineState = {
        "goal": req.goal,
        "requirements": req.requirements,
        "messages": [],
        "artifacts": {},
        "retry_counters": {},
        "flags": {},
        "metadata": {
            "thread_id": thread_id,
            "budget_usd": req.budget_usd,
        },
        "current_step": "",
        "error": None,
    }

    try:
        result = _require_graph().invoke(initial_state, config)
    except Exception as exc:
        logger.exception(
            "Pipeline invocation failed", extra={"step": "api", "thread_id": thread_id}
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "thread_id": thread_id,
        "status": result.get("current_step"),
        "error": result.get("error"),
        "artifacts_keys": list(result.get("artifacts", {}).keys()),
        "metadata": result.get("metadata", {}),
    }


@app.post("/pipeline/stream")
async def run_pipeline_stream(req: PipelineRequest):
    """SSE streaming с interrupt detection. Клиент видит каждый узел в реальном времени."""
    thread_id = req.thread_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: PipelineState = {
        "goal": req.goal,
        "requirements": req.requirements,
        "messages": [],
        "artifacts": {},
        "retry_counters": {},
        "flags": {},
        "metadata": {"thread_id": thread_id, "budget_usd": req.budget_usd},
        "current_step": "",
        "error": None,
    }

    async def event_generator():
        async for chunk in _require_graph().astream(initial_state, config, stream_mode="updates"):
            payload = json.dumps(chunk, default=str)
            yield f"data: {payload}\n\n"

            for node_name, value in chunk.items():
                if isinstance(value, dict) and "__interrupt__" in str(value):
                    yield f"event: interrupt\ndata: {json.dumps({'thread_id': thread_id, 'node': node_name})}\n\n"
                    return

        yield f"event: done\ndata: {json.dumps({'thread_id': thread_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/pipeline/{thread_id}/resume")
async def resume_pipeline(thread_id: str, req: ResumeRequest) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    payload = {"action": req.action, "feedback": req.feedback}

    try:
        result = _require_graph().invoke(Command(resume=payload), config)
    except Exception as exc:
        logger.exception("Resume failed", extra={"step": "api", "thread_id": thread_id})
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "thread_id": thread_id,
        "status": result.get("current_step"),
        "error": result.get("error"),
        "artifacts_keys": list(result.get("artifacts", {}).keys()),
        "metadata": result.get("metadata", {}),
    }


@app.get("/pipeline/{thread_id}/state")
async def get_state(thread_id: str) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = _require_graph().get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "thread_id": thread_id,
        "current_step": state.values.get("current_step"),
        "error": state.values.get("error"),
        "interrupts": [i.value for i in state.interrupts] if state.interrupts else [],
    }
