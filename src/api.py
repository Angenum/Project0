"""FastAPI обёртка для пайплайна."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command

from .graph import build_pipeline
from .persistence import get_checkpointer
from .state import PipelineState

logger = logging.getLogger(__name__)

# Глобальный граф (singleton)
_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    _graph = build_pipeline(checkpointer=get_checkpointer())
    logger.info("Pipeline graph compiled")
    yield
    logger.info("Shutting down")


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
        result = _graph.invoke(initial_state, config)
    except Exception as exc:
        logger.exception("Pipeline invocation failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "thread_id": thread_id,
        "status": result.get("current_step"),
        "error": result.get("error"),
        "artifacts_keys": list(result.get("artifacts", {}).keys()),
        "metadata": result.get("metadata", {}),
    }


@app.post("/pipeline/{thread_id}/resume")
async def resume_pipeline(thread_id: str, req: ResumeRequest) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    payload = {"action": req.action, "feedback": req.feedback}

    try:
        result = _graph.invoke(Command(resume=payload), config)
    except Exception as exc:
        logger.exception("Resume failed")
        raise HTTPException(status_code=500, detail=str(exc))

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
        state = _graph.get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "thread_id": thread_id,
        "current_step": state.values.get("current_step"),
        "error": state.values.get("error"),
        "interrupts": [i.value for i in state.interrupts] if state.interrupts else [],
    }
