#!/usr/bin/env python3
"""Validate export-raw-transcript metadata against the bundled JSON schema."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    """Raised when data does not satisfy the supported schema subset."""


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    prefix = "#/"
    if not ref.startswith(prefix):
        msg = f"unsupported $ref {ref!r}"
        raise ValidationError(msg)

    target: Any = schema
    for part in ref[len(prefix) :].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or key not in target:
            msg = f"unresolvable $ref {ref!r}"
            raise ValidationError(msg)
        target = target[key]

    if not isinstance(target, dict):
        msg = f"$ref {ref!r} does not point to a schema object"
        raise ValidationError(msg)
    return target


def type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    msg = f"unsupported JSON Schema type {expected!r}"
    raise ValidationError(msg)


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def validate(instance: Any, schema_node: dict[str, Any], root: dict[str, Any], path: str) -> None:
    if "$ref" in schema_node:
        validate(instance, resolve_ref(root, str(schema_node["$ref"])), root, path)
        return

    if "const" in schema_node and instance != schema_node["const"]:
        msg = f"{path}: expected constant {schema_node['const']!r}, got {instance!r}"
        raise ValidationError(msg)

    if "enum" in schema_node and instance not in schema_node["enum"]:
        msg = f"{path}: expected one of {schema_node['enum']!r}, got {instance!r}"
        raise ValidationError(msg)

    if "type" in schema_node:
        expected_types = schema_node["type"]
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        if not isinstance(expected_types, list) or not all(
            isinstance(item, str) for item in expected_types
        ):
            msg = f"{path}: invalid schema type declaration"
            raise ValidationError(msg)
        if not any(type_matches(instance, expected) for expected in expected_types):
            msg = f"{path}: expected {' or '.join(expected_types)}, got {json_type_name(instance)}"
            raise ValidationError(msg)

    if instance is None:
        return

    if isinstance(instance, dict):
        required = schema_node.get("required", [])
        if not isinstance(required, list):
            msg = f"{path}: invalid schema required declaration"
            raise ValidationError(msg)
        for key in required:
            if key not in instance:
                msg = f"{path}: missing required property {key!r}"
                raise ValidationError(msg)

        properties = schema_node.get("properties", {})
        if not isinstance(properties, dict):
            msg = f"{path}: invalid schema properties declaration"
            raise ValidationError(msg)

        if schema_node.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                msg = f"{path}: unexpected properties {', '.join(extra)}"
                raise ValidationError(msg)

        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], root, f"{path}.{key}")

    if isinstance(instance, str):
        min_length = schema_node.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            msg = f"{path}: string is shorter than {min_length}"
            raise ValidationError(msg)

        max_length = schema_node.get("maxLength")
        if isinstance(max_length, int) and len(instance) > max_length:
            msg = f"{path}: string is longer than {max_length}"
            raise ValidationError(msg)

        pattern = schema_node.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            msg = f"{path}: string does not match pattern {pattern!r}"
            raise ValidationError(msg)

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema_node.get("minimum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            msg = f"{path}: number is less than minimum {minimum}"
            raise ValidationError(msg)


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: validate-metadata.py <metadata.schema.json> <metadata.json>",
            file=sys.stderr,
        )
        return 2

    schema_path = Path(sys.argv[1])
    metadata_path = Path(sys.argv[2])

    try:
        schema = load_json(schema_path)
        metadata = load_json(metadata_path)
        if not isinstance(schema, dict):
            raise ValidationError("schema root must be an object")
        validate(metadata, schema, schema, "$")
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"metadata validation failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
