"""Shared Protocol + helpers for primitive modules."""
from __future__ import annotations

from typing import Protocol


class PrimitiveModule(Protocol):
    NAME: str
    DESCRIPTION: str
    CUE_EVENTS: set[str]
    AUDIO_SPANS: list[dict]
    DATA_SCHEMA: dict
    NEEDS_CONTENT: bool
    DEPRECATED: bool
    PARAMS: dict

    def render(self, clip: dict, duration: float,
               images_dir: str, theme) -> str: ...


REQUIRED_ATTRS = ("NAME", "DESCRIPTION", "CUE_EVENTS", "AUDIO_SPANS",
                  "DATA_SCHEMA", "PARAMS", "NEEDS_CONTENT", "DEPRECATED",
                  "render")


def validate_schema(data: dict, schema: dict, path: str) -> list[str]:
    """Walk data against schema and return error strings.

    Schema keys:
      required: list of required field names
      types: dict field -> type | tuple of types
      enums: dict field -> allowed values set
      children: dict field -> nested schema (recursed into each list element
                              if the field is a list)
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{path}: expected object, got {type(data).__name__}"]

    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"{path}: missing required field {field!r}")

    for field, expected in schema.get("types", {}).items():
        if field not in data:
            continue
        if not isinstance(data[field], expected):
            name = (expected.__name__ if isinstance(expected, type)
                    else "/".join(t.__name__ for t in expected))
            errors.append(
                f"{path}.{field}: expected {name}, "
                f"got {type(data[field]).__name__}"
            )

    for field, allowed in schema.get("enums", {}).items():
        if field in data and data[field] not in allowed:
            errors.append(
                f"{path}.{field}: {data[field]!r} not in {sorted(allowed)}"
            )

    for field, child_schema in schema.get("children", {}).items():
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, list):
            for i, elem in enumerate(value):
                errors.extend(validate_schema(elem, child_schema,
                                              f"{path}.{field}[{i}]"))
        elif isinstance(value, dict):
            errors.extend(validate_schema(value, child_schema,
                                          f"{path}.{field}"))
    return errors
