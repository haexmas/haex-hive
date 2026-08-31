"""T009 — contract test for install-journal v1 (Spec 008 JSONL entries).

Assertions
- Every value in the `entry_type` enum accepts a minimal well-formed entry.
- Chain integrity is a runtime check: a `tail_hash` that is well-formed but
  chained wrong still passes schema validation.
- `additionalProperties: false` at the root is enforced.
"""

from __future__ import annotations

import pytest

from haex_hive.schema import loader
from haex_hive.schema.validator import SchemaValidationError, validate

SCHEMA_NAME = "install-journal.v1.schema.json"

_ZERO_TAIL = "sha256-" + "A" * 43

_ENTRY_TYPES = (
    "plan_snapshot_sealed",
    "commit_snapshot_verified",
    "stage_file",
    "delete_orphan",
    "hook_step_started",
    "hook_step_ended",
    "overlay_pointer_swapped",
    "install_lock_sealed",
    "commit_marker_published",
    "cleanup_started",
    "cleanup_completed",
    "install_aborted",
)


def _entry(entry_type: str, **overrides: object) -> dict:
    """Build the smallest valid journal entry for the requested entry type."""
    base = {
        "entry_id": 0,
        "wrote_at_ns": 0,
        "entry_type": entry_type,
        "tail_hash": _ZERO_TAIL,
    }
    if entry_type in {"stage_file", "delete_orphan"}:
        base["payload"] = {
            "path": ".haex-hive/constitution.md",
            "prior_existed": False,
            "prior_digest": None,
            "pre_image": "rollback/constitution.md",
        }
    base.update(overrides)
    return base


def test_schema_loads() -> None:
    """Ensure the vendored journal schema is available."""
    schema = loader.load(SCHEMA_NAME)
    assert schema["title"] == "haex-hive Install Journal Entry v1"


@pytest.mark.parametrize("entry_type", _ENTRY_TYPES)
def test_each_entry_type_validates(entry_type: str) -> None:
    """Accept every enumerated journal entry type."""
    validate(_entry(entry_type), SCHEMA_NAME)


def test_step_id_null_is_accepted() -> None:
    """Accept lifecycle entries without a plan step."""
    validate(_entry("cleanup_started", step_id=None), SCHEMA_NAME)


def test_step_id_integer_is_accepted() -> None:
    """Accept mutation entries associated with a plan step."""
    validate(_entry("stage_file", step_id=3), SCHEMA_NAME)


def test_tampered_tail_hash_still_schema_valid() -> None:
    """Leave journal chain integrity to the runtime checker."""
    entry_a = _entry("plan_snapshot_sealed", entry_id=0)
    entry_b = _entry("commit_snapshot_verified", entry_id=1, tail_hash="sha256-" + "B" * 43)
    validate(entry_a, SCHEMA_NAME)
    validate(entry_b, SCHEMA_NAME)


def test_unknown_entry_type_is_rejected() -> None:
    """Reject entry types outside the versioned contract."""
    with pytest.raises(SchemaValidationError):
        validate(_entry("bogus_entry_type"), SCHEMA_NAME)


def test_padded_tail_hash_is_rejected() -> None:
    """Reject legacy padded tail hashes in new journal entries."""
    with pytest.raises(SchemaValidationError):
        validate(_entry("stage_file", tail_hash="sha256-" + "A" * 43 + "="), SCHEMA_NAME)


def test_missing_required_field_is_rejected() -> None:
    """Reject entries missing their structural required fields."""
    entry = _entry("stage_file")
    del entry["entry_id"]
    with pytest.raises(SchemaValidationError):
        validate(entry, SCHEMA_NAME)


def test_unknown_top_level_field_is_rejected() -> None:
    """Reject unrecognized top-level journal fields."""
    with pytest.raises(SchemaValidationError):
        validate(_entry("stage_file", stray_key=True), SCHEMA_NAME)


@pytest.mark.parametrize("entry_type", ["stage_file", "delete_orphan"])
def test_mutation_entry_requires_payload(entry_type: str) -> None:
    """Require recovery metadata on every mutation entry."""
    entry = _entry(entry_type)
    del entry["payload"]
    with pytest.raises(SchemaValidationError):
        validate(entry, SCHEMA_NAME)


@pytest.mark.parametrize("field", ["path", "prior_existed", "prior_digest", "pre_image"])
def test_mutation_payload_requires_recovery_field(field: str) -> None:
    """Require each field needed to restore a mutation pre-image."""
    entry = _entry("stage_file")
    del entry["payload"][field]
    with pytest.raises(SchemaValidationError):
        validate(entry, SCHEMA_NAME)
