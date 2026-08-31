"""T058 — FR-039 pending-merge canonical serialization and pending_id binding."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from haex_hive.constitution.pending import (
    derive_pending_id,
    load_pending,
    pending_path,
    serialize_pending,
    verify_pending_matches_current,
)
from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.model.install_lock import ConstitutionSource
from haex_hive.util.errors import PendingMergeInputsMismatchError


def _contribution(
    atom_id: str, revision: str, source: str, body: bytes
) -> ResolvedConstitutionContribution:
    """Build a resolved constitution contribution for pending-state tests."""
    return ResolvedConstitutionContribution(
        source=ConstitutionSource(id=atom_id, revision=revision, source=source), body=body
    )


def test_pending_id_matches_decoded_pending_json() -> None:
    """Bind serialized pending inputs to their decoded pending ID."""
    contributions = [
        _contribution("com.b.b", "1" * 40, "https://github.com/b/b", b"body-b"),
        _contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"body-a"),
    ]
    pending_bytes = serialize_pending(contributions, "merge these")
    data = json.loads(pending_bytes.decode("utf-8"))

    decoded_entries = [
        (s["id"], s["revision"], s["source"], base64.b64decode(s["body_base64"]))
        for s in data["sources"]
    ]
    assert derive_pending_id(decoded_entries) == data["pending_id"]


def test_pending_id_matches_freshly_resolved_contributions() -> None:
    """Bind pending inputs to the freshly resolved contributions."""
    contributions = [
        _contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"body-a"),
        _contribution("com.b.b", "1" * 40, "https://github.com/b/b", b"body-b"),
    ]
    pending_bytes = serialize_pending(contributions, "merge these")
    data = json.loads(pending_bytes.decode("utf-8"))

    fresh_entries = [
        (c.source.id, c.source.revision, c.source.source, c.body) for c in contributions
    ]
    assert derive_pending_id(fresh_entries) == data["pending_id"]


def test_sources_sorted_by_bytewise_utf8_id() -> None:
    """Serialize pending sources in bytewise UTF-8 ID order."""
    contributions = [
        _contribution("com.z.z", "1" * 40, "https://github.com/z/z", b"z"),
        _contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"a"),
    ]
    data = json.loads(serialize_pending(contributions, "prompt").decode("utf-8"))
    assert [s["id"] for s in data["sources"]] == ["com.a.a", "com.z.z"]


def test_body_base64_is_padded_standard_encoding() -> None:
    """Keep opaque pending bodies in standard padded Base64."""
    contributions = [_contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"\xff\xfe\x00")]
    data = json.loads(serialize_pending(contributions, "prompt").decode("utf-8"))
    assert data["sources"][0]["body_base64"] == base64.b64encode(b"\xff\xfe\x00").decode("ascii")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda entries: [(e[0] + "x", e[1], e[2], e[3]) for e in entries],  # id drift
        lambda entries: [(e[0], "f" * 40, e[2], e[3]) for e in entries],  # revision drift
        lambda entries: [(e[0], e[1], e[2] + "/x", e[3]) for e in entries],  # source drift
        lambda entries: [(e[0], e[1], e[2], e[3] + b"!") for e in entries],  # body drift
    ],
)
def test_any_field_drift_changes_pending_id(mutate) -> None:
    """Change the pending ID when any bound source field changes."""
    original = [("com.a.a", "0" * 40, "https://github.com/a/a", b"body")]
    mutated = mutate(original)
    assert derive_pending_id(original) != derive_pending_id(mutated[:1])


def test_load_pending_round_trips(tmp_path: Path) -> None:
    """Load a serialized pending merge without changing its fields."""
    contributions = [_contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"body")]
    pending_bytes = serialize_pending(contributions, "merge prompt")
    path = pending_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(pending_bytes)

    pending = load_pending(tmp_path)
    assert pending.task_prompt == "merge prompt"
    assert pending.sources[0].id == "com.a.a"


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        json.dumps({"sources": [], "task_prompt": "prompt", "pending_id": "id"}).encode(),
        json.dumps(
            {
                "sources": [{"id": "com.a.a"}],
                "task_prompt": "prompt",
                "pending_id": "id",
            }
        ).encode(),
        json.dumps(
            {
                "sources": [
                    {
                        "id": "com.a.a",
                        "revision": "0" * 40,
                        "source": "https://example.com/a",
                        "body_base64": 42,
                    }
                ],
                "task_prompt": "prompt",
                "pending_id": "id",
            }
        ).encode(),
    ],
)
def test_load_pending_rejects_malformed_state(tmp_path: Path, payload: bytes) -> None:
    """Reject malformed pending merge state."""
    path = pending_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)

    with pytest.raises(PendingMergeInputsMismatchError):
        load_pending(tmp_path)


def test_verify_pending_matches_current_accepts_identical_state(tmp_path: Path) -> None:
    """Accept pending state when current resolution is identical."""
    contributions = [_contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"body")]
    pending_bytes = serialize_pending(contributions, "merge prompt")
    path = pending_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(pending_bytes)

    pending = load_pending(tmp_path)
    verify_pending_matches_current(pending, contributions)  # no raise


def test_verify_pending_matches_current_rejects_drift(tmp_path: Path) -> None:
    """Reject pending state after contribution content drifts."""
    contributions = [_contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"body")]
    pending_bytes = serialize_pending(contributions, "merge prompt")
    path = pending_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(pending_bytes)

    pending = load_pending(tmp_path)
    drifted = [_contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"different body")]
    with pytest.raises(PendingMergeInputsMismatchError):
        verify_pending_matches_current(pending, drifted)


def test_verify_pending_matches_current_rejects_invalid_base64(tmp_path: Path) -> None:
    """Reject pending state containing invalid source body Base64."""
    contributions = [_contribution("com.a.a", "0" * 40, "https://github.com/a/a", b"body")]
    data = json.loads(serialize_pending(contributions, "merge prompt").decode("utf-8"))
    data["sources"][0]["body_base64"] = "not-base64!"
    path = pending_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data))

    pending = load_pending(tmp_path)
    with pytest.raises(PendingMergeInputsMismatchError):
        verify_pending_matches_current(pending, contributions)
