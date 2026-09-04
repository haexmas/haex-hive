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

_SCHEMA_BY_KIND = {
    "consumer": "consumer-manifest.v3.schema.json",
    "publisher": "publisher-manifest.v3.schema.json",
    "molecule": "molecule-manifest.v3.schema.json",
    "install-lock": "install-lock.v3.schema.json",
}


def schema_name_for_kind(kind: str) -> str:
    """Return the v3 schema payload name for a manifest kind.

    `kind` is one of "consumer", "publisher", "molecule", "install-lock".
    """
    try:
        return _SCHEMA_BY_KIND[kind]
    except KeyError:
        raise KeyError(f"unknown manifest kind: {kind!r}") from None


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
    if schema_name == "install-lock.v3.schema.json":
        _check_unique_keys(data, "participating_roots", "root", errors)
        _check_unique_keys(data.get("ownership"), "paths", "path", errors, prefix="/ownership")
        _check_generation_input_identities(data, errors)
    elif schema_name == "visibility-marker.v1.schema.json":
        roots = data.get("participating_roots")
        _check_unique_keys(data, "participating_roots", "root", errors)
        if isinstance(roots, list) and all(isinstance(item, str) for item in roots):
            values = roots
        elif isinstance(roots, list) and all(
            isinstance(item, dict) and isinstance(item.get("root"), str) for item in roots
        ):
            values = [item["root"] for item in roots]
        else:
            values = None
        if values is not None and values != sorted(values):
            errors.append(
                SchemaError(
                    field_path="/participating_roots",
                    message="roots must be in lexicographic order",
                )
            )
    return errors


def _check_generation_input_identities(
    data: dict[str, Any], errors: list[SchemaError]
) -> None:
    """Enforce generation-input identity uniqueness and canonical ordering."""
    entries = data.get("generation_inputs")
    if not isinstance(entries, list):
        return

    identities: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        identity = entry.get("id")
        if not isinstance(kind, str) or not isinstance(identity, str):
            continue
        key = (kind, identity)
        if key in seen:
            errors.append(
                SchemaError(
                    field_path=f"/generation_inputs/{index}",
                    message="duplicate (kind, id) values are not allowed",
                )
            )
        seen.add(key)
        identities.append(key)

    if identities != sorted(
        identities,
        key=lambda key: (key[0].encode("utf-8"), key[1].encode("utf-8")),
    ):
        errors.append(
            SchemaError(
                field_path="/generation_inputs",
                message="generation_inputs must be in lexicographic order by (kind, id)",
            )
        )


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
