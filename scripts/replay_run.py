#!/usr/bin/env python3
"""CLI tool to replay a specific step from a previous run."""

import argparse
import sys
import os
import json
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import LLMClient
from src.artifact_store import ArtifactStore
from src.validators import SchemaValidator
from src.utils import load_prompt_template, render_prompt, setup_logging

logger = logging.getLogger(__name__)


def load_pipeline_config(config_path: str = "config/pipeline.yaml"):
    """Load pipeline configuration."""
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_step_artifacts(artifact_store: ArtifactStore, step_id: int) -> dict:
    """Get all artifacts up to the specified step."""
    config = load_pipeline_config()
    steps = {s["id"]: s for s in config.get("steps", [])}
    
    artifacts = {}
    for sid in range(1, step_id):
        step_config = steps.get(sid)
        if step_config:
            role = step_config.get("role", "").lower().replace(" ", "_")
            artifact = artifact_store.load_artifact(sid, role.replace(" ", "_"))
            if artifact:
                artifacts[sid] = artifact
    
    return artifacts


def execute_step(
    llm_client: LLMClient,
    validator: SchemaValidator,
    artifact_store: ArtifactStore,
    step_config: dict,
    goal: str,
    prior_artifacts: dict,
    log_level: int = logging.INFO,
) -> tuple[bool, dict]:
    """Execute a single step."""
    step_id = step_config["id"]
    role = step_config["role"]
    prompt_file = step_config["prompt"]
    schema_file = step_config.get("schema")
    output_name = step_config.get("output")

    logger.info(f"Executing step {step_id}: {role}")

    # Load and render prompt
    prompt_template = load_prompt_template(prompt_file)
    context = {
        "goal": goal,
        "artifacts": prior_artifacts,
    }
    rendered_prompt = render_prompt(prompt_template, context)

    # Get model for this role
    models_config_path = Path("config/models.yaml")
    import yaml
    with open(models_config_path, "r", encoding="utf-8") as f:
        models_config = yaml.safe_load(f)
    
    model_info = models_config.get("roles", {}).get(role, {})
    model = model_info.get("model", "default")

    # Call LLM
    response = llm_client.generate(
        messages=[{"role": "user", "content": rendered_prompt}],
        model=model,
    )

    # Parse JSON from response
    from src.utils import extract_json_from_response
    result_data = extract_json_from_response(response)

    if result_data is None:
        logger.error(f"Failed to parse JSON from step {step_id} response")
        return False, {"error": "Invalid JSON response"}

    # Validate against schema if specified
    if schema_file:
        schema_path = Path(f"config/schemas/{schema_file}")
        is_valid, error_msg = validator.validate(result_data, str(schema_path))
        
        if not is_valid:
            logger.error(f"Validation failed for step {step_id}: {error_msg}")
            
            # Try auto-correction (one retry)
            logger.info("Attempting auto-correction...")
            correction_prompt = f"The previous response failed validation: {error_msg}\n\nPlease fix the JSON to match the schema."
            
            corrected_response = llm_client.generate(
                messages=[
                    {"role": "user", "content": rendered_prompt},
                    {"role": "assistant", "content": json.dumps(result_data, ensure_ascii=False)},
                    {"role": "user", "content": correction_prompt},
                ],
                model=model,
            )
            
            result_data = extract_json_from_response(corrected_response)
            
            if result_data is None:
                return False, {"error": "Auto-correction failed"}
            
            is_valid, error_msg = validator.validate(result_data, str(schema_path))
            if not is_valid:
                return False, {"error": f"Validation still failed: {error_msg}"}

    # Save artifact
    artifact_data = {
        "step_id": step_id,
        "role": role,
        "data": result_data,
    }
    
    artifact_path = artifact_store.save_artifact(step_id, role, artifact_data)
    logger.info(f"Saved artifact: {artifact_path}")

    # Save with output name if specified
    if output_name:
        output_path = artifact_store.run_path / output_name
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved output: {output_path}")

    return True, result_data


def main():
    parser = argparse.ArgumentParser(
        description="Replay a specific step from a previous pipeline run"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        required=True,
        help="Run ID to replay from (e.g., run_20250101_120000)",
    )
    parser.add_argument(
        "--step",
        type=int,
        required=True,
        help="Step number to replay (1-9)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/pipeline.yaml",
        help="Path to pipeline configuration file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory for replayed artifacts (default: artifacts/replay_<timestamp>)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)

    # Initialize components
    artifact_store = ArtifactStore()
    validator = SchemaValidator()
    llm_client = LLMClient()

    # Check if run exists
    available_runs = ArtifactStore.list_runs()
    if args.run_id not in available_runs:
        logger.error(f"Run ID '{args.run_id}' not found. Available runs: {available_runs}")
        sys.exit(1)

    # Load metadata from the original run
    artifact_store.run_id = args.run_id
    artifact_store.run_path = artifact_store.base_path / args.run_id
    
    if not artifact_store.run_path.exists():
        logger.error(f"Run path does not exist: {artifact_store.run_path}")
        sys.exit(1)

    meta = artifact_store.load_meta()
    if not meta:
        logger.error("Could not load metadata from the specified run")
        sys.exit(1)

    goal = meta.get("goal", "")
    logger.info(f"Replaying step {args.step} from run {args.run_id}")
    logger.info(f"Original goal: {goal}")

    # Create new run for replay
    if args.output_dir:
        replay_run_id = args.output_dir
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        replay_run_id = f"replay_{args.run_id}_step{args.step}_{timestamp}"
    
    replay_store = ArtifactStore()
    replay_store.start_run(replay_run_id)
    logger.info(f"Replay artifacts will be saved to: {replay_store.run_path}")

    # Copy prior artifacts from original run
    prior_artifacts = get_step_artifacts(artifact_store, args.step)
    logger.info(f"Loaded {len(prior_artifacts)} prior artifacts")

    # Load step configuration
    config = load_pipeline_config(args.config)
    steps = {s["id"]: s for s in config.get("steps", [])}
    
    step_config = steps.get(args.step)
    if not step_config:
        logger.error(f"Step {args.step} not found in configuration")
        sys.exit(1)

    # Execute the step
    success, result = execute_step(
        llm_client=llm_client,
        validator=validator,
        artifact_store=replay_store,
        step_config=step_config,
        goal=goal,
        prior_artifacts=prior_artifacts,
        log_level=log_level,
    )

    if success:
        print(f"\n✅ Step {args.step} replayed successfully!")
        print(f"Replay Run ID: {replay_run_id}")
        print(f"Artifacts saved to: {replay_store.run_path}")
        
        # Save replay metadata
        replay_meta = {
            "original_run_id": args.run_id,
            "replayed_step": args.step,
            "replay_run_id": replay_run_id,
            "goal": goal,
            "status": "completed",
        }
        replay_store.save_meta(replay_meta)
    else:
        print(f"\n❌ Step {args.step} replay failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
