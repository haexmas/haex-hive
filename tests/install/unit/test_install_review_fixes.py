"""Regression tests for the PR #32 integrity review findings."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from haex_hive.install.digest import compute_root_digest
from haex_hive.install.journal import (
    append_entry,
    make_entry,
    read_entries,
    read_verified_entries,
    verify_chain,
)
from haex_hive.install.plan import CommitSnapshot, PlanSnapshot, PlanStep
from haex_hive.install.visibility import RootDigest, VisibilityMarker


def _sri(content: bytes) -> str:
    """Return the digest format used by install snapshot fields."""
    digest = hashlib.sha256(content).digest()
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def test_overlay_path_cannot_escape_root(tmp_path: Path) -> None:
    """Reject traversal from a mixed-ownership root into a sibling."""
    root = tmp_path / "claude"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")

    with pytest.raises(ValueError, match="escapes root"):
        compute_root_digest(root, ".claude/", [".claude/../outside.txt"])


def test_journal_rejects_removed_complete_trailing_entries(tmp_path: Path) -> None:
    """Reject a valid JSONL prefix when its durable final state disagrees."""
    journal = tmp_path / "install.journal"
    first = make_entry(
        entry_id=0,
        entry_type="plan_snapshot_sealed",
        prev_tail_hash="",
        wrote_at_ns=1,
    )
    second = make_entry(
        entry_id=1,
        entry_type="commit_snapshot_verified",
        prev_tail_hash=first.tail_hash,
        wrote_at_ns=2,
    )
    append_entry(journal, first)
    append_entry(journal, second)

    lines = journal.read_bytes().splitlines(keepends=True)
    journal.write_bytes(lines[0])

    entries = read_entries(journal)
    verify_chain(entries)
    with pytest.raises(ValueError, match="entry count mismatch"):
        verify_chain(entries, journal_path=journal)
    with pytest.raises(ValueError, match="entry count mismatch"):
        read_verified_entries(journal)


def test_journal_recovers_entry_written_before_sidecar_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discard a journal entry whose sidecar commit was interrupted."""
    journal = tmp_path / "install.journal"
    first = make_entry(
        entry_id=0,
        entry_type="plan_snapshot_sealed",
        prev_tail_hash="",
        wrote_at_ns=1,
    )
    second = make_entry(
        entry_id=1,
        entry_type="commit_snapshot_verified",
        prev_tail_hash=first.tail_hash,
        wrote_at_ns=2,
    )
    append_entry(journal, first)

    def interrupted_sidecar_update(*args: object, **kwargs: object) -> None:
        """Simulate a process stop before the sidecar commit."""
        raise OSError("interrupted sidecar update")

    monkeypatch.setattr(
        "haex_hive.install.journal._write_journal_state",
        interrupted_sidecar_update,
    )
    with pytest.raises(OSError, match="interrupted"):
        append_entry(journal, second)

    monkeypatch.undo()
    assert read_verified_entries(journal) == [first]
    assert len(journal.read_bytes().splitlines(keepends=True)) == 1


def test_journal_payload_is_frozen_and_to_dict_is_detached() -> None:
    """Caller mutations cannot change a hashed journal entry."""
    payload = {"nested": {"items": [1]}}
    entry = make_entry(
        entry_id=0,
        entry_type="stage_file",
        prev_tail_hash="",
        payload=payload,
        wrote_at_ns=1,
    )
    payload["nested"]["items"].append(2)
    serialized = entry.to_dict()
    serialized["payload"]["nested"]["items"].append(3)

    assert entry.to_dict()["payload"] == {"nested": {"items": [1]}}
    verify_chain([entry])


def test_plan_snapshot_validates_digest_and_freezes_nested_state() -> None:
    """Plan fields remain immutable and the recorded digest is authoritative."""
    payload = {"nested": {"values": [1]}}
    step = PlanStep(0, "stage_file", ".haex-hive/", payload)
    publisher_digests = {"publisher": "publisher-digest"}
    atom_digests = {"atom": "atom-digest"}
    plan = PlanSnapshot.seal(
        haex_hive_json_digest="config-digest",
        publisher_manifest_digests=publisher_digests,
        atom_manifest_digests=atom_digests,
        steps=(step,),
        sealed_at_ns=1,
    )
    payload["nested"]["values"].append(2)
    publisher_digests["other"] = "changed"

    assert plan.steps[0].to_dict()["payload"] == {"nested": {"values": [1]}}
    with pytest.raises(TypeError):
        plan.publisher_manifest_digests["other"] = "changed"  # type: ignore[index]
    with pytest.raises(ValueError, match="plan_snapshot_digest"):
        PlanSnapshot(
            sealed_at_ns=1,
            haex_hive_json_digest=plan.haex_hive_json_digest,
            publisher_manifest_digests=plan.publisher_manifest_digests,
            atom_manifest_digests=plan.atom_manifest_digests,
            steps=plan.steps,
            plan_snapshot_digest="sha256-" + "A" * 43,
        )


def test_commit_snapshot_validates_and_freezes_captured_bytes() -> None:
    """A commit snapshot cannot claim bytes that differ from its digests."""
    config = bytearray(b"config")
    publisher = b"publisher"
    atom = b"atom"
    snapshot = CommitSnapshot(
        haex_hive_json_digest=_sri(config),
        haex_hive_json_bytes=config,
        publisher_manifest_digests={"publisher": _sri(publisher)},
        publisher_manifest_bytes={"publisher": publisher},
        atom_manifest_digests={"atom": _sri(atom)},
        atom_manifest_bytes={"atom": atom},
    )
    config[0] = ord("X")

    assert snapshot.haex_hive_json_bytes == b"config"
    with pytest.raises(TypeError):
        snapshot.publisher_manifest_bytes["publisher"] = b"changed"  # type: ignore[index]
    with pytest.raises(ValueError, match="does not match captured bytes"):
        CommitSnapshot(
            haex_hive_json_digest=_sri(b"wrong"),
            haex_hive_json_bytes=b"config",
            publisher_manifest_digests={"publisher": _sri(publisher)},
            publisher_manifest_bytes={"publisher": publisher},
            atom_manifest_digests={"atom": _sri(atom)},
            atom_manifest_bytes={"atom": atom},
        )


def test_visibility_collections_are_normalized_before_storage() -> None:
    """Visibility serialization is stable after caller-owned lists mutate."""
    paths = [".claude/settings.json"]
    roots = [RootDigest(".claude/", "sha256-" + "A" * 43, paths)]
    marker = VisibilityMarker(
        generation_id="g_20260901T120000Z_abcd",
        install_lock_content_integrity="sha256-" + "B" * 43,
        participating_roots=roots,
    )
    paths.append(".claude/other.json")
    roots.append(RootDigest(".codex/", "sha256-" + "C" * 43))

    assert marker.to_dict()["participating_roots"] == [
        {
            "root": ".claude/",
            "content_integrity": "sha256-" + "A" * 43,
            "overlay_paths": [".claude/settings.json"],
        }
    ]
