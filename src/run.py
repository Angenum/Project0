"""CLI entrypoint для локального запуска пайплайна."""
from __future__ import annotations

import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.types import Command

from .graph import build_pipeline
from .persistence import get_checkpointer
from .state import PipelineState

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
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

    logger.info("Starting pipeline thread=%s", thread_id)

    for chunk in graph.stream(initial_state, config, stream_mode="updates"):
        logger.info("Chunk: %s", chunk)

        if "__interrupt__" in str(chunk):
            logger.info("⏸️  INTERRUPT detected. Waiting for human input...")
            action = input("Approve? (yes/no): ").strip().lower()
            is_approve = action in ("yes", "y")
            feedback = "" if is_approve else input("Feedback: ").strip()

            resume_payload = {"action": "approve" if is_approve else "reject", "feedback": feedback}
            for resume_chunk in graph.stream(Command(resume=resume_payload), config, stream_mode="updates"):
                logger.info("Resume chunk: %s", resume_chunk)

    logger.info("Pipeline finished thread=%s", thread_id)


if __name__ == "__main__":
    main()
