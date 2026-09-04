"""T022 — contract tests for the v3 publisher-manifest schema (Spec 013)."""

from __future__ import annotations

import json

import pytest

from haex_hive.model.publisher_manifest import PublisherManifest
from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "publisher-manifest.v3.schema.json"


def _minimal() -> dict:
    return {
        "haex_hive_version": "3",
        "publisher": "com.example.publisher",
        "molecules": {
            "com.example.publisher.molecule": {"path": "molecule", "version": "1.0.0"},
        },
    }


def test_molecules_map_validates() -> None:
    validate(_minimal(), SCHEMA_NAME)


def test_legacy_atoms_key_is_rejected() -> None:
    data = _minimal()
    data["atoms"] = data.pop("molecules")
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_molecule_id_not_prefixed_by_publisher_refuses_at_load_time() -> None:
    """JSON Schema cannot express a cross-property prefix constraint; the model checks it."""
    data = _minimal()
    data["molecules"] = {
        "com.example.other.molecule": {"path": "molecule", "version": "1.0.0"},
    }
    raw = json.dumps(data).encode("utf-8")
    with pytest.raises(ValueError):
        PublisherManifest.from_json(raw)


def test_invalid_path_is_rejected() -> None:
    data = _minimal()
    data["molecules"]["com.example.publisher.molecule"]["path"] = "../escape"
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)
