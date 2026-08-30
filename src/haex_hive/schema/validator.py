"""JSON Schema Draft 2020-12 validation with FR-034/SC-006 diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from haex_hive.schema import loader


@dataclass(frozen=True)
class SchemaError:
    field_path: str
    message: str


class SchemaValidationError(ValueError):
    def __init__(self, schema_name: str, errors: list[SchemaError]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        first = errors[0] if errors else None
        formatted = (
            f"{schema_name}: {first.field_path} {first.message}"
            if first
            else f"{schema_name}: unknown error"
        )
        super().__init__(formatted)


def _json_pointer(path: list[Any]) -> str:
    if not path:
        return "/"
    return "/" + "/".join(
        str(token).replace("~", "~0").replace("/", "~1") for token in path
    )


def validate(data: Any, schema_name: str) -> None:
    schema = loader.load(schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    formatted = [
        SchemaError(
            field_path=_json_pointer(list(e.absolute_path)),
            message=e.message,
        )
        for e in errors
    ]
    raise SchemaValidationError(schema_name, formatted)
