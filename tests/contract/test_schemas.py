"""Contract tests for the four JSON Schemas.

For every schema, every fixture under `tests/fixtures/schemas/<schema>/valid/`
MUST validate. Every fixture under `.../invalid/` MUST raise
`SchemaValidationError` and the first error MUST carry a JSON Pointer path
(the leading `/`) so SC-006's "names the field path" guarantee holds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haex_hive.schema.validator import SchemaValidationError, validate

_SCHEMA_MAP = {
    "haex_hive": "haex-hive.v2.schema.json",
    "publisher_manifest": "publisher-manifest.v2.schema.json",
    "atom_manifest": "atom-manifest.v2.schema.json",
    "install_lock": "install-lock.v2.schema.json",
}

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "schemas"


def _collect(schema_dir: str, subdir: str) -> list[Path]:
    directory = _FIXTURES / schema_dir / subdir
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"))


@pytest.mark.parametrize(
    "schema_dir,schema_name,path",
    [
        (schema_dir, schema_name, path)
        for schema_dir, schema_name in _SCHEMA_MAP.items()
        for path in _collect(schema_dir, "valid")
    ],
    ids=lambda x: str(x) if isinstance(x, Path) else str(x),
)
def test_valid_fixtures(schema_dir: str, schema_name: str, path: Path) -> None:
    data = json.loads(path.read_text())
    validate(data, schema_name)


@pytest.mark.parametrize(
    "schema_dir,schema_name,path",
    [
        (schema_dir, schema_name, path)
        for schema_dir, schema_name in _SCHEMA_MAP.items()
        for path in _collect(schema_dir, "invalid")
    ],
    ids=lambda x: str(x) if isinstance(x, Path) else str(x),
)
def test_invalid_fixtures(schema_dir: str, schema_name: str, path: Path) -> None:
    data = json.loads(path.read_text())
    with pytest.raises(SchemaValidationError) as exc_info:
        validate(data, schema_name)
    assert exc_info.value.errors, "invalid fixture must produce at least one error"
    first = exc_info.value.errors[0]
    assert first.field_path.startswith("/"), (
        f"first error should carry a JSON Pointer path, got {first.field_path!r}"
    )
