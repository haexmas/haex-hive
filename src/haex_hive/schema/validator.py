"""JSON Schema Draft 2020-12 validation with FR-034/SC-006 diagnostics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from haex_hive.schema import loader

_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _is_uri(value: object) -> bool:
    """Check the URI format omitted by jsonschema's default checker set."""
    if not isinstance(value, str) or any(char.isspace() for char in value):
        return False
    if not _URI_SCHEME_RE.match(value):
        return False
    try:
        urlsplit(value)
    except ValueError:
        return False
    return True


Draft202012Validator.FORMAT_CHECKER.checks("uri")(_is_uri)


@dataclass(frozen=True)
class SchemaError:
    field_path: str
    message: str


class SchemaValidationError(ValueError):
    def __init__(self, schema_name: str, errors: list[SchemaError]) -> None:
        """Create a validation error with the first field diagnostic in its message."""
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
    """Render a jsonschema path as an escaped JSON Pointer."""
    if not path:
        return "/"
    return "/" + "/".join(
        str(token).replace("~", "~0").replace("/", "~1") for token in path
    )


def validate(data: Any, schema_name: str) -> None:
    """Validate JSON structurally and apply schema-specific semantic checks."""
    schema = loader.load(schema_name)
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    formatted = [
        SchemaError(
            field_path=_json_pointer(list(e.absolute_path)),
            message=e.message,
        )
        for e in errors
    ]
    if not formatted:
        formatted = _semantic_errors(data, schema_name)
    if not formatted:
        return
    raise SchemaValidationError(schema_name, formatted)


def _semantic_errors(data: Any, schema_name: str) -> list[SchemaError]:
    """Return semantic errors that Draft 2020-12 cannot express."""
    if not isinstance(data, dict):
        return []

    errors: list[SchemaError] = []
    if schema_name == "install-lock.v2.schema.json":
        _check_unique_keys(data, "participating_roots", "root", errors)
        _check_unique_keys(data.get("ownership"), "paths", "path", errors, prefix="/ownership")
    elif schema_name == "visibility-marker.v1.schema.json":
        roots = data.get("participating_roots")
        _check_unique_keys(data, "participating_roots", "root", errors)
        if isinstance(roots, list) and all(
            isinstance(item, dict) and isinstance(item.get("root"), str) for item in roots
        ):
            values = [item["root"] for item in roots]
            if values != sorted(values):
                errors.append(
                    SchemaError(
                        field_path="/participating_roots",
                        message="roots must be in lexicographic order",
                    )
                )
    return errors


def _check_unique_keys(
    container: Any,
    array_key: str,
    identity_key: str,
    errors: list[SchemaError],
    *,
    prefix: str = "",
) -> None:
    """Add an error when object identities repeat in a validated array."""
    if not isinstance(container, dict) or not isinstance(container.get(array_key), list):
        return
    seen: set[str] = set()
    for index, item in enumerate(container[array_key]):
        if not isinstance(item, dict) or not isinstance(item.get(identity_key), str):
            continue
        identity = item[identity_key]
        if identity in seen:
            errors.append(
                SchemaError(
                    field_path=f"{prefix}/{array_key}/{index}/{identity_key}",
                    message=f"duplicate {identity_key} values are not allowed",
                )
            )
        seen.add(identity)
