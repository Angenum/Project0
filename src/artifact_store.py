"""Artifact Store for managing pipeline artifacts."""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ArtifactStore:
    """Storage for pipeline artifacts with run isolation."""

    def __init__(self, base_path: str = "artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.run_id: Optional[str] = None
        self.run_path: Optional[Path] = None

    def start_run(self, run_id: Optional[str] = None) -> str:
        """Start a new run and create its directory."""
        if run_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_id = f"run_{timestamp}"

        self.run_id = run_id
        self.run_path = self.base_path / run_id
        self.run_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Started run: {run_id} at {self.run_path}")
        return run_id

    def save_artifact(self, step_id: int, role: str, data: Dict[str, Any]) -> str:
        """Save an artifact for a specific step."""
        if self.run_path is None:
            raise RuntimeError("No active run. Call start_run() first.")

        filename = f"{step_id}_{role.lower().replace(' ', '_')}.json"
        filepath = self.run_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved artifact: {filepath}")
        return str(filepath)

    def load_artifact(self, step_id: int, role: str) -> Optional[Dict[str, Any]]:
        """Load an artifact from the current or specified run."""
        if self.run_path is None:
            raise RuntimeError("No active run. Call start_run() first.")

        filename = f"{step_id}_{role.lower().replace(' ', '_')}.json"
        filepath = self.run_path / filename

        if not filepath.exists():
            logger.warning(f"Artifact not found: {filepath}")
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_artifact_by_name(self, artifact_name: str) -> Optional[Dict[str, Any]]:
        """Load an artifact by its output name (e.g., 'plan.json')."""
        if self.run_path is None:
            raise RuntimeError("No active run. Call start_run() first.")

        filepath = self.run_path / artifact_name

        # Also try with step prefix
        if not filepath.exists():
            for f in self.run_path.glob(f"*_{artifact_name}"):
                filepath = f
                break

        if not filepath.exists():
            logger.warning(f"Artifact not found: {artifact_name}")
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all artifacts in the current run."""
        if self.run_path is None:
            return {"error": "No active run"}

        artifacts = []
        for filepath in sorted(self.run_path.glob("*.json")):
            if filepath.name == "meta.json":
                continue

            artifacts.append({
                "filename": filepath.name,
                "size_bytes": filepath.stat().st_size,
            })

        return {
            "run_id": self.run_id,
            "run_path": str(self.run_path),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        }

    def save_meta(self, meta: Dict[str, Any]) -> str:
        """Save metadata for the current run."""
        if self.run_path is None:
            raise RuntimeError("No active run. Call start_run() first.")

        filepath = self.run_path / "meta.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved metadata: {filepath}")
        return str(filepath)

    def load_meta(self) -> Optional[Dict[str, Any]]:
        """Load metadata for the current run."""
        if self.run_path is None:
            raise RuntimeError("No active run. Call start_run() first.")

        filepath = self.run_path / "meta.json"

        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def list_runs(cls, base_path: str = "artifacts") -> List[str]:
        """List all available runs."""
        path = Path(base_path)
        if not path.exists():
            return []

        return sorted([d.name for d in path.iterdir() if d.is_dir() and d.name.startswith("run_")])
