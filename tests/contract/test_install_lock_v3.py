"""T023 — contract tests for the v3 install-lock schema (Spec 013, 2026-09-03 amendment)."""

from __future__ import annotations

import pytest

from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "install-lock.v3.schema.json"


def _minimal() -> dict:
    return {
        "haex_hive_version": "3",
        "generation_id": "g_20260831T142011Z_a4c2",
        "molecules": [],
    }


def _with_molecules(paths: list[str]) -> dict:
    data = _minimal()
    data["molecules"] = [
        {
            "id": "com.example.publisher.molecule",
            "source": "https://github.com/example/publisher",
            "revision": "0" * 40,
            "paths": paths,
        }
    ]
    return data


def test_molecules_array_with_molecule_entries_validates() -> None:
    validate(_with_molecules([".haex-hive/constitution.md"]), SCHEMA_NAME)


def test_unknown_root_property_is_rejected() -> None:
    """Proves additionalProperties: false at root."""
    data = _minimal()
    data["stray_key"] = True
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_missing_generation_id_is_rejected() -> None:
    data = _minimal()
    del data["generation_id"]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_retired_fields_are_rejected() -> None:
    """generated_by, constitution, participating_roots, generation_inputs are all gone."""
    for retired_field, value in (
        ("generated_by", "haex 3.0.0"),
        ("constitution", {"sources": [], "assembled_by": {}}),
        ("participating_roots", [".haex-hive/"]),
        ("generation_inputs", []),
    ):
        data = _minimal()
        data[retired_field] = value
        with pytest.raises(SchemaValidationError):
            validate(data, SCHEMA_NAME)


def test_non_posix_path_is_rejected() -> None:
    data = _with_molecules(["/absolute/path.md"])
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_path_without_leading_dot_segment_is_rejected() -> None:
    """Every path must start with a dot-segment root; there is no separate root list."""
    data = _with_molecules(["README.md"])
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_duplicate_paths_within_one_molecule_are_rejected() -> None:
    data = _with_molecules([".haex-hive/a.md", ".haex-hive/a.md"])
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_empty_paths_validates() -> None:
    """A molecule that contributed nothing under the tracked roots is still valid."""
    validate(_with_molecules([]), SCHEMA_NAME)


def test_molecule_missing_source_is_rejected() -> None:
    data = _with_molecules([".haex-hive/constitution.md"])
    del data["molecules"][0]["source"]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_invalid_molecule_source_uri_is_rejected() -> None:
    data = _with_molecules([".haex-hive/constitution.md"])
    data["molecules"][0]["source"] = "http://[invalid"
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_molecules_out_of_canonical_order_is_rejected() -> None:
    """molecules[] must be sorted by (id, source, revision, paths); JSON Schema alone
    cannot express this, so it's a semantic check (schema/validator.py)."""
    data = _minimal()
    data["molecules"] = [
        {
            "id": "com.b.molecule",
            "source": "https://example.com/publisher",
            "revision": "0" * 40,
            "paths": [],
        },
        {
            "id": "com.a.molecule",
            "source": "https://example.com/publisher",
            "revision": "0" * 40,
            "paths": [],
        },
    ]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)
