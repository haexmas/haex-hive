"""T020 — contract tests for the v3 consumer-manifest schema (Spec 013)."""

from __future__ import annotations

import pytest

from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "consumer-manifest.v3.schema.json"


def _minimal() -> dict:
    return {
        "haex_hive_version": "3",
        "identity": "com.example.project",
        "compounds": [],
    }


def test_minimal_shape_validates() -> None:
    validate(_minimal(), SCHEMA_NAME)


def test_unknown_top_level_property_is_rejected() -> None:
    data = _minimal()
    data["stray_key"] = True
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_v2_version_is_rejected() -> None:
    data = _minimal()
    data["haex_hive_version"] = "2"
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_non_40_hex_revision_is_rejected() -> None:
    data = _minimal()
    data["compounds"] = [
        {
            "source": "https://github.com/example/publisher",
            "revision": "deadbeef",
            "molecules": ["com.example.publisher.molecule"],
        }
    ]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_duplicate_molecule_id_within_compound_is_rejected() -> None:
    data = _minimal()
    data["compounds"] = [
        {
            "source": "https://github.com/example/publisher",
            "revision": "0" * 40,
            "molecules": [
                "com.example.publisher.molecule",
                "com.example.publisher.molecule",
            ],
        }
    ]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)
