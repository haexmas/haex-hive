"""T010 — contract test for visibility-marker v1 (Spec 008 marker JSON).

Assertions
- Both MVP shapes validate: `.haex-hive/` alone (fully haex-owned), and
  `.haex-hive/` + `.claude/`.
- Retired root and lock digest fields are not part of the marker contract.
- `additionalProperties: false` at the root and inside `rootDigest` is enforced.
"""

from __future__ import annotations

import pytest

from haex_hive.schema import loader
from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "visibility-marker.v1.schema.json"

_GENERATION_ID = "g_20260831T142011Z_a4c2"


def _haex_only_marker() -> dict:
    """Build a valid marker for a single haex-owned root."""
    return {
        "haex_hive_version": "2",
        "generation_id": _GENERATION_ID,
        "participating_roots": [".haex-hive/"],
    }


def _mixed_overlay_marker() -> dict:
    """Build a valid marker for canonical mixed-root ordering."""
    marker = _haex_only_marker()
    marker["participating_roots"] = [".claude/", ".haex-hive/"]
    return marker


def test_schema_loads() -> None:
    """Ensure the vendored visibility-marker schema is available."""
    schema = loader.load(SCHEMA_NAME)
    assert schema["title"] == "haex-hive Visibility Marker v1 (trust-git amendment)"


def test_haex_only_mvp_validates() -> None:
    """Accept a marker containing only the haex-owned root."""
    validate(_haex_only_marker(), SCHEMA_NAME)


def test_mixed_overlay_validates() -> None:
    """Accept a marker containing a mixed-ownership overlay root."""
    validate(_mixed_overlay_marker(), SCHEMA_NAME)


def test_participating_roots_are_names() -> None:
    """Reject the retired object-shaped participating-root records."""
    marker = _haex_only_marker()
    marker["participating_roots"] = [{"root": ".haex-hive/"}]
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_written_at_is_optional() -> None:
    """Accept the optional diagnostic publication timestamp."""
    marker = _haex_only_marker()
    marker["written_at"] = "2026-08-31T14:20:11.000000Z"
    validate(marker, SCHEMA_NAME)


def test_retired_install_lock_digest_is_rejected() -> None:
    """Reject the retired marker-level lock digest."""
    marker = _haex_only_marker()
    marker["install_lock_content_integrity"] = "sha256-" + "A" * 43
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_retired_participating_root_digest_is_rejected() -> None:
    """Reject the retired per-root digest."""
    marker = _haex_only_marker()
    marker["participating_roots"] = [
        {"root": ".haex-hive/", "content_integrity": "sha256-" + "A" * 43}
    ]
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_bad_generation_id_shape_is_rejected() -> None:
    """Reject generation identifiers outside the contract shape."""
    marker = _haex_only_marker()
    marker["generation_id"] = "not-a-generation-id"
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_participating_roots_must_be_nonempty() -> None:
    """Require at least one participating root."""
    marker = _haex_only_marker()
    marker["participating_roots"] = []
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_unknown_top_level_field_is_rejected() -> None:
    """Reject unrecognized marker-level fields."""
    marker = _haex_only_marker()
    marker["stray_key"] = True
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_unknown_root_field_is_rejected() -> None:
    """Reject unrecognized per-root fields."""
    marker = _haex_only_marker()
    marker["participating_roots"] = [{"root": ".haex-hive/", "stray_key": True}]
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_duplicate_participating_roots_are_rejected() -> None:
    """Reject repeated participating-root identities."""
    marker = _haex_only_marker()
    marker["participating_roots"].append(".haex-hive/")
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)


def test_participating_roots_must_be_lexicographically_sorted() -> None:
    """Reject participating roots in non-canonical order."""
    marker = _mixed_overlay_marker()
    marker["participating_roots"].reverse()
    with pytest.raises(SchemaValidationError):
        validate(marker, SCHEMA_NAME)
