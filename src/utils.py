"""Utility functions for the pipeline."""

import json
import re
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_json_from_markdown(content: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from a markdown code block."""
    # Pattern to match ```json ... ``` or ``` ... ```
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, content)

    if match:
        json_str = match.group(1).strip()
    else:
        # Try to parse the entire content as JSON
        json_str = content.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.debug(f"Content: {content[:500]}...")
        return None


def format_artifact_digest(artifact: Dict[str, Any], max_length: int = 200) -> str:
    """Create a short digest/summary of an artifact for context."""
    if not artifact:
        return "<empty artifact>"

    # Get top-level keys
    keys = list(artifact.keys())

    # Create summary
    summary_parts = []
    for key in keys[:5]:  # Limit to first 5 keys
        value = artifact[key]
        if isinstance(value, list):
            summary_parts.append(f"{key}: [{len(value)} items]")
        elif isinstance(value, dict):
            summary_parts.append(f"{key}: {{{len(value)}} fields}")
        elif isinstance(value, str) and len(value) > 50:
            summary_parts.append(f"{key}: {value[:50]}...")
        else:
            summary_parts.append(f"{key}: {value}")

    digest = " | ".join(summary_parts)

    if len(digest) > max_length:
        digest = digest[:max_length] + "..."

    return digest


def load_prompt_template(prompt_file: str, snippets_dir: str = "prompts/snippets") -> str:
    """Load a prompt template file with snippet includes."""
    path = Path(prompt_file)

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    content = path.read_text(encoding="utf-8")

    # Process {% include '...' %} directives
    include_pattern = r"\{%\s*include\s+'([^']+)'\s*%\}"

    def replace_include(match):
        snippet_name = match.group(1)
        snippet_path = Path(snippets_dir) / snippet_name

        if not snippet_path.exists():
            logger.warning(f"Snippet not found: {snippet_path}")
            return f"<!-- Snippet not found: {snippet_name} -->"

        return snippet_path.read_text(encoding="utf-8").strip()

    content = re.sub(include_pattern, replace_include, content)

    return content


def render_prompt(template: str, variables: Dict[str, Any]) -> str:
    """Render a Jinja2-style template with variables."""
    result = template

    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"

        # Convert value to string representation
        if isinstance(value, dict):
            str_value = json.dumps(value, ensure_ascii=False, indent=2)
        elif isinstance(value, list):
            str_value = json.dumps(value, ensure_ascii=False)
        else:
            str_value = str(value)

        result = result.replace(placeholder, str_value)

    return result


def setup_logging(log_file: str = "pipeline.log", level: int = logging.INFO) -> None:
    """Configure logging for the pipeline."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def truncate_for_context(data: Any, max_items: int = 10, max_string_length: int = 500) -> Any:
    """Truncate data to fit within context limits."""
    if isinstance(data, dict):
        return {
            k: truncate_for_context(v, max_items, max_string_length)
            for k, v in list(data.items())[:max_items]
        }
    elif isinstance(data, list):
        return [
            truncate_for_context(item, max_items, max_string_length)
            for item in data[:max_items]
        ]
    elif isinstance(data, str) and len(data) > max_string_length:
        return data[:max_string_length] + "... (truncated)"
    else:
        return data
