"""Main pipeline runner engine."""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import yaml

from .llm_client import LLMClient
from .artifact_store import ArtifactStore
from .validators import SchemaValidator
from .utils import load_prompt_template, render_prompt, format_artifact_digest, setup_logging

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Main engine for running the Role-Chaining Pipeline."""

    def __init__(
        self,
        config_path: str = "config/pipeline.yaml",
        models_config: str = "config/models.yaml",
    ):
        self.config_path = Path(config_path)
        self.models_config = Path(models_config)

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.artifact_store = ArtifactStore(
            self.config.get("global", {}).get("artifact_store_path", "artifacts")
        )
        self.validator = SchemaValidator()
        self.llm_client: Optional[LLMClient] = None

        self.steps = {s["id"]: s for s in self.config.get("steps", [])}
        self.current_run_meta: Dict[str, Any] = {}

    def initialize_llm(self, **kwargs) -> None:
        """Initialize the LLM client."""
        self.llm_client = LLMClient(**kwargs)

    def run(
        self, goal: str, resume_run_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Run the full pipeline.

        Args:
            goal: The user's goal/objective.
            resume_run_id: Optional run ID to resume from.

        Returns:
            Tuple of (success, final_meta)
        """
        if self.llm_client is None:
            self.initialize_llm()

        # Start or resume run
        run_id = self.artifact_store.start_run(resume_run_id)

        self.current_run_meta = {
            "run_id": run_id,
            "goal": goal,
            "started_at": datetime.now().isoformat(),
            "steps_completed": [],
            "steps_failed": [],
            "feedback_loops": 0,
            "status": "running",
        }

        logger.info(f"Starting pipeline run: {run_id}")
        logger.info(f"Goal: {goal}")

        # Load existing artifacts if resuming
        start_step = 1
        if resume_run_id:
            meta = self.artifact_store.load_meta()
            if meta:
                completed = meta.get("steps_completed", [])
                if completed:
                    start_step = max(completed) + 1
                    logger.info(f"Resuming from step {start_step}")

        # Execute steps
        current_step = 1
        max_steps = len(self.steps)

        while current_step <= max_steps:
            step_config = self.steps.get(current_step)

            if not step_config:
                logger.error(f"Step {current_step} not found in config")
                break

            success, artifact = self._execute_step(step_config, goal)

            if success and artifact:
                self.current_run_meta["steps_completed"].append(current_step)
                current_step += 1
            else:
                # Handle failure with retry logic
                on_failure = step_config.get("on_failure", {})
                retry_step = on_failure.get("retry_step", current_step)
                max_retries = on_failure.get("max_retries", 2)

                retry_count = self._get_retry_count(current_step)

                if retry_count < max_retries:
                    logger.warning(
                        f"Step {current_step} failed, retrying ({retry_count + 1}/{max_retries})"
                    )
                    self._increment_retry_count(current_step)
                    # Stay on same step or go to retry_step
                    current_step = retry_step
                else:
                    logger.error(f"Step {current_step} failed after {max_retries} retries")
                    self.current_run_meta["steps_failed"].append(current_step)

                    # Check if we should go back due to feedback loop
                    if step_config.get("name") in ["tester", "critic"]:
                        # Feedback loop to builder
                        feedback_target = 5  # Builder step
                        if self.current_run_meta["feedback_loops"] < self.config.get(
                            "global", {}
                        ).get("max_feedback_loops", 2):
                            self.current_run_meta["feedback_loops"] += 1
                            logger.info(
                                f"Feedback loop triggered, going back to step {feedback_target}"
                            )
                            current_step = feedback_target
                            continue

                    break

        # Finalize
        self.current_run_meta["completed_at"] = datetime.now().isoformat()
        self.current_run_meta["status"] = (
            "completed" if current_step > max_steps else "failed"
        )

        self.artifact_store.save_meta(self.current_run_meta)
        logger.info(f"Pipeline run finished: {self.current_run_meta['status']}")

        return self.current_run_meta["status"] == "completed", self.current_run_meta

    def _get_retry_count(self, step_id: int) -> int:
        """Get current retry count for a step."""
        key = f"retry_count_{step_id}"
        return self.current_run_meta.get(key, 0)

    def _increment_retry_count(self, step_id: int) -> None:
        """Increment retry count for a step."""
        key = f"retry_count_{step_id}"
        self.current_run_meta[key] = self._get_retry_count(step_id) + 1

    def _execute_step(
        self, step_config: Dict[str, Any], goal: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Execute a single pipeline step."""
        step_id = step_config["id"]
        role = step_config["role"]
        prompt_file = step_config["prompt_file"]
        schema_file = step_config.get("schema")
        timeout = step_config.get("timeout", 180)

        logger.info(f"Executing step {step_id}: {role}")

        # Gather input artifacts
        input_artifacts = self._gather_inputs(step_config.get("input_from", []))
        input_artifacts["goal"] = goal

        # Load and render prompt
        try:
            prompt_template = load_prompt_template(prompt_file)
            rendered_prompt = render_prompt(prompt_template, input_artifacts)
        except Exception as e:
            logger.error(f"Failed to load/render prompt: {e}")
            return False, None

        # Call LLM
        system_prompt = "You are a helpful assistant that outputs valid JSON."
        
        try:
            result = self.llm_client.chat(system_prompt, rendered_prompt, parse_json=True)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return False, None

        # Validate result
        if schema_file:
            is_valid, error_msg = self.validator.validate(result, schema_file)

            if not is_valid:
                logger.error(f"Validation failed for step {step_id}: {error_msg}")
                return False, None

        # Save artifact
        artifact_name = step_config.get("output_artifact", f"{step_id}_{role}.json")
        self.artifact_store.save_artifact(step_id, role, result)

        # Also save with output_artifact name for easy reference
        artifact_path = self.artifact_store.run_path / artifact_name
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Step {step_id} completed successfully")
        return True, result

    def _gather_inputs(self, input_from: List[int]) -> Dict[str, Any]:
        """Gather input artifacts from previous steps."""
        inputs = {}

        for step_id in input_from:
            step_config = self.steps.get(step_id)
            if not step_config:
                continue

            artifact_name = step_config.get("output_artifact")
            role = step_config.get("role", f"step_{step_id}")

            # Try loading by output_artifact name first
            artifact = self.artifact_store.load_artifact_by_name(artifact_name)

            if artifact is None:
                # Try loading by step_id and role
                artifact = self.artifact_store.load_artifact(step_id, role)

            if artifact:
                # Use digest for context to save tokens
                key = step_config.get("name", f"step_{step_id}")
                inputs[key] = artifact
                inputs[f"{key}_digest"] = format_artifact_digest(artifact)

        return inputs
