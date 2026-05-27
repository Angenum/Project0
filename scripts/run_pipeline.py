#!/usr/bin/env python3
"""CLI entry point for running the pipeline."""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline_runner import PipelineRunner
from src.utils import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Run the Role-Chaining Pipeline"
    )
    parser.add_argument(
        "--goal",
        type=str,
        required=True,
        help="The goal/objective to achieve",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/pipeline.yaml",
        help="Path to pipeline configuration file",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Run ID to resume from",
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
    import logging
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)

    # Create and run pipeline
    runner = PipelineRunner(config_path=args.config)
    runner.initialize_llm()

    success, meta = runner.run(goal=args.goal, resume_run_id=args.resume)

    if success:
        print(f"\n✅ Pipeline completed successfully!")
        print(f"Run ID: {meta['run_id']}")
        print(f"Artifacts saved to: artifacts/{meta['run_id']}/")
    else:
        print(f"\n❌ Pipeline failed!")
        print(f"Run ID: {meta['run_id']}")
        print(f"Steps completed: {meta.get('steps_completed', [])}")
        print(f"Steps failed: {meta.get('steps_failed', [])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
