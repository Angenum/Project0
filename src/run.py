"""CLI entrypoint для локального запуска пайплайна."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.types import Command

from .graph import build_pipeline
from .persistence import get_checkpointer
from .state import PipelineState


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


def main() -> None:
    load_dotenv()
    checkpointer = get_checkpointer()
    graph = build_pipeline(checkpointer=checkpointer)

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: PipelineState = {
        "goal": "Build a REST API for user management with JWT auth",
        "requirements": "FastAPI, PostgreSQL, Pydantic v2",
        "messages": [],
        "artifacts": {},
        "retry_counters": {},
        "flags": {},
        "metadata": {"thread_id": thread_id, "budget_usd": 5.0},
        "current_step": "",
        "error": None,
    }

    logger.info("Starting pipeline", extra={"step": "init", "thread_id": thread_id})

    for chunk in graph.stream(initial_state, config, stream_mode="updates"):
        logger.info("Chunk received", extra={"step": "stream", "thread_id": thread_id})

        if "__interrupt__" in str(chunk):
            logger.info("INTERRUPT detected", extra={"step": "hitl", "thread_id": thread_id})
            action = input("Approve? (yes/no): ").strip().lower()
            is_approve = action in ("yes", "y")
            feedback = "" if is_approve else input("Feedback: ").strip()

            resume_payload = {"action": "approve" if is_approve else "reject", "feedback": feedback}
            for _resume_chunk in graph.stream(
                Command(resume=resume_payload), config, stream_mode="updates"
            ):
                logger.info("Resume chunk", extra={"step": "resume", "thread_id": thread_id})

    logger.info("Pipeline finished", extra={"step": "done", "thread_id": thread_id})


if __name__ == "__main__":
    main()
