"""T021 — contract tests for the v3 molecule-manifest schema (Spec 013)."""

from __future__ import annotations

import json

import pytest

from haex_hive.model.molecule_manifest import MoleculeManifest
from haex_hive.schema.validator import SchemaValidationError, validate
from haex_hive.util.errors import MoleculeAtomsCategoryOverlapError

SCHEMA_NAME = "molecule-manifest.v3.schema.json"


def _minimal() -> dict:
    return {
        "haex_hive_version": "3",
        "id": "com.example.publisher.molecule",
        "version": "1.0.0",
        "priority": 100,
        "atoms": {"constitution": ["constitution.md"]},
    }


def test_atoms_category_map_shape_validates() -> None:
    validate(_minimal(), SCHEMA_NAME)


def test_empty_category_array_is_rejected() -> None:
    data = _minimal()
    data["atoms"] = {"constitution": []}
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_missing_priority_is_rejected() -> None:
    data = _minimal()
    del data["priority"]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_cross_category_path_overlap_refuses_at_load_time() -> None:
    """JSON Schema's uniqueItems only catches intra-array duplicates (data-model.md)."""
    data = _minimal()
    data["atoms"] = {
        "constitution": ["shared.md"],
        "skills": ["shared.md"],
    }
    raw = json.dumps(data).encode("utf-8")
    with pytest.raises(MoleculeAtomsCategoryOverlapError):
        MoleculeManifest.from_json(raw)
