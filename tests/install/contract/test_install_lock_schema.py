"""T008 — contract test for install-lock v2 (Spec 008 shape).

Assertions
- The three MVP shapes validate: minimal Spec-007-shape (constitution only), a
  Spec-008 full shape with atoms + participating_roots + visibility_marker +
  ownership, and the in-tree valid fixtures used by `tests/contract/`.
- Negative cases prove the schema tightens where Spec 008 needs it: atoms items
  without `source` are rejected, and any SRI digest in the old standard-base64
  (padded) shape is rejected.
"""

from __future__ import annotations

import pytest

from haex_hive.schema import loader
from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "install-lock.v2.schema.json"

_ZERO_DIGEST = "sha256-" + "A" * 43  # base64url-nopad SHA-256 of 32 zero bytes
_GENERATION_ID = "g_20260831T142011Z_a4c2"


def _spec_007_shape() -> dict:
    """Build the minimal Spec 007-compatible install lock shape."""
    return {
        "haex_hive_version": "2",
        "generated_by": "haex 2.0.0",
        "constitution": {
            "sources": [
                {
                    "id": "com.example.publisher.constitution",
                    "revision": "0" * 40,
                    "source": "https://github.com/example/publisher",
                }
            ],
            "assembled_by": {"tool": "haex", "version": "2.0.0"},
            "content_integrity": _ZERO_DIGEST,
        },
    }


def _spec_008_shape() -> dict:
    """Build a complete valid Spec 008 install lock shape."""
    base = _spec_007_shape()
    base["atoms"] = [
        {
            "id": "com.example.publisher.constitution",
            "source": "https://github.com/example/publisher",
            "revision": "0" * 40,
            "content_integrity": _ZERO_DIGEST,
            "contributed_paths": [
                ".haex-hive/atoms/com.example.publisher.constitution/manifest.json"
            ],
        }
    ]
    base["participating_roots"] = [
        {"root": ".haex-hive/", "content_integrity": _ZERO_DIGEST}
    ]
    base["visibility_marker"] = {
        "generation_id": _GENERATION_ID,
        "content_integrity": _ZERO_DIGEST,
    }
    base["ownership"] = {
        "version": 1,
        "paths": [
            {
                "path": ".haex-hive/atoms/com.example.publisher.constitution/manifest.json",
                "owner": {
                    "kind": "atom",
                    "resource": "com.example.publisher.constitution",
                    "source": "https://github.com/example/publisher",
                    "revision": "0" * 40,
                },
                "generation_id": _GENERATION_ID,
                "content_integrity": _ZERO_DIGEST,
                "previous": None,
            }
        ],
    }
    return base


def test_schema_loads() -> None:
    """Ensure the vendored install-lock schema is available."""
    schema = loader.load(SCHEMA_NAME)
    assert schema["title"].startswith("haex-hive Install Lockfile v2")


def test_minimal_spec_007_shape_validates() -> None:
    """Keep the pre-Spec-008 install lock shape valid."""
    validate(_spec_007_shape(), SCHEMA_NAME)


def test_full_spec_008_shape_validates() -> None:
    """Accept the complete Spec 008 install lock shape."""
    validate(_spec_008_shape(), SCHEMA_NAME)


def test_atom_missing_source_is_rejected() -> None:
    """Require a publisher source on every installed atom record."""
    data = _spec_008_shape()
    del data["atoms"][0]["source"]
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_padded_base64_digest_is_rejected() -> None:
    """Reject legacy padded digest values in new lock records."""
    data = _spec_007_shape()
    data["constitution"]["content_integrity"] = "sha256-" + "A" * 43 + "="
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_pathownership_previous_can_be_object() -> None:
    """Accept the populated previous ownership state variant."""
    data = _spec_008_shape()
    data["ownership"]["paths"][0]["previous"] = {
        "generation_id": "g_20260830T101010Z_dead",
        "existed": True,
        "content_integrity": _ZERO_DIGEST,
    }
    validate(data, SCHEMA_NAME)


def test_duplicate_participating_roots_are_rejected() -> None:
    """Reject repeated participating-root identities."""
    data = _spec_008_shape()
    data["participating_roots"].append(
        {"root": ".haex-hive/", "content_integrity": "sha256-" + "B" * 43}
    )
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_duplicate_ownership_paths_are_rejected() -> None:
    """Reject repeated ownership path identities."""
    data = _spec_008_shape()
    duplicate = dict(data["ownership"]["paths"][0])
    duplicate["content_integrity"] = "sha256-" + "B" * 43
    data["ownership"]["paths"].append(duplicate)
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)


def test_invalid_atom_source_uri_is_rejected() -> None:
    """Reject malformed atom source URIs."""
    data = _spec_008_shape()
    data["atoms"][0]["source"] = "http://[invalid"
    with pytest.raises(SchemaValidationError):
        validate(data, SCHEMA_NAME)
