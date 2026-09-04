"""T023 — contract tests for the v3 install-lock schema (Spec 013)."""

from __future__ import annotations

import pytest

from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "install-lock.v3.schema.json"


def _minimal() -> dict:
    return {
        "haex_hive_version": "3",
        "generated_by": "haex 3.0.0",
    }


def _with_molecules(contributed_paths: list[str]) -> dict:
    data = _minimal()
    data["molecules"] = [
        {
            "id": "com.example.publisher.molecule",
            "source": "https://github.com/example/publisher",
            "revision": "0" * 40,
            "contributed_paths": contributed_paths,
        }
    ]
    data["participating_roots"] = [".haex-hive/"]
    return data


def test_molecules_array_with_molecule_install_records_validates() -> None:
    validate(_with_molecules([".haex-hive/constitution.md"]), SCHEMA_NAME)


def test_unknown_root_property_is_rejected() -> None:
    """Proves additionalProperties: false at root (unlike v2's open root shape)."""
    data = _minimal()
    data["stray_key"] = True
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_non_posix_contributed_path_is_rejected() -> None:
    data = _with_molecules(["/absolute/path.md"])
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_duplicate_contributed_paths_are_rejected() -> None:
    data = _with_molecules([".haex-hive/a.md", ".haex-hive/a.md"])
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_contributed_path_outside_participating_roots_is_rejected() -> None:
    """_check_contributed_paths: JSON Schema alone cannot express this cross-field rule."""
    data = _with_molecules([".claude/orphan.md"])
    assert data["participating_roots"] == [".haex-hive/"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate(data, SCHEMA_NAME)
    assert "participating root" in str(exc_info.value)


def test_contributed_path_matching_second_participating_root_validates() -> None:
    """The path must match *any* configured root, not just the first one."""
    data = _with_molecules([".claude/skill.md"])
    data["participating_roots"] = [".claude/", ".haex-hive/"]
    validate(data, SCHEMA_NAME)


def test_non_empty_contributed_paths_without_participating_roots_is_rejected() -> None:
    data = _with_molecules([".haex-hive/constitution.md"])
    del data["participating_roots"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate(data, SCHEMA_NAME)
    assert "participating_roots" in str(exc_info.value)


def test_empty_contributed_paths_validates_without_participating_roots() -> None:
    """An empty contributed_paths array carries no path to check against any root."""
    data = _with_molecules([])
    del data["participating_roots"]
    validate(data, SCHEMA_NAME)
