"""JSON Schema validators for artifact validation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from jsonschema import validate, ValidationError, Draft7Validator

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validator for JSON artifacts against schemas."""

    def __init__(self, schemas_path: str = "config/schemas"):
        self.schemas_path = Path(schemas_path)
        self._schema_cache: Dict[str, Dict] = {}

    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load a JSON schema from file."""
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]

        schema_path = self.schemas_path / schema_name

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self._schema_cache[schema_name] = schema
        return schema

    def validate(
        self, data: Dict[str, Any], schema_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate data against a schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            schema = self.load_schema(schema_name)
            validate(instance=data, schema=schema)
            logger.info(f"Validation passed for {schema_name}")
            return True, None
        except ValidationError as e:
            error_msg = f"Validation failed: {e.message}"
            logger.error(error_msg)
            return False, error_msg
        except FileNotFoundError as e:
            error_msg = str(e)
            logger.error(error_msg)
            return False, error_msg

    def validate_with_fix_request(
        self, data: Dict[str, Any], schema_name: str
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate data and return detailed fix suggestions.

        Returns:
            Tuple of (is_valid, error_message, list_of_suggestions)
        """
        is_valid, error_msg = self.validate(data, schema_name)

        if is_valid:
            return True, None, []

        suggestions = []

        if error_msg and "required" in error_msg.lower():
            # Extract missing required fields
            suggestions.append("Add all required fields to the JSON object.")

        if error_msg and "additional properties" in error_msg.lower():
            suggestions.append("Remove any fields not defined in the schema.")

        if error_msg and "enum" in error_msg.lower():
            suggestions.append("Use one of the allowed enum values.")

        if error_msg and "minimum" in error_msg.lower() or "maximum" in error_msg.lower():
            suggestions.append("Ensure numeric values are within the allowed range.")

        return is_valid, error_msg, suggestions


def get_validation_error_details(error: ValidationError) -> Dict[str, Any]:
    """Extract detailed information from a validation error."""
    details = {
        "message": error.message,
        "path": list(error.absolute_path),
        "schema_path": list(error.absolute_schema_path),
        "validator": error.validator,
        "validator_value": error.validator_value,
    }

    if error.context:
        details["nested_errors"] = [
            get_validation_error_details(e) for e in error.context
        ]

    return details
