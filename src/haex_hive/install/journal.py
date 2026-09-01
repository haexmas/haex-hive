"""Durable journal and recovery (FR-002, FR-011, research §R7).

Every install.journal entry is one line of JSON in a `<gen>.jsonl`-shaped file.
The line JSON is canonical (sorted keys, compact separators, UTF-8) and
terminated by a single LF byte. The `tail_hash` chains each entry to the
previous entry's `tail_hash` per data-model.md, so a truncated or tampered
journal is detected at recovery time.

Write discipline (per research §R7):
    append → fsync(fd) → fsync(parent_dir) → return

Chain integrity is a **runtime** check performed by `verify_chain()` — the
schema (contracts/install-journal.v1.schema.json) only validates that a
`tail_hash` is well-formed base64url-nopad. This module's `verify_chain`
recomputes each entry's expected preimage and refuses on any mismatch.

Entry-type-specific payload shapes are defined by the schema; this module
does not restrict payload contents — payload validation runs through the
schema loader before an entry is committed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

_IS_WINDOWS = sys.platform == "win32"

EntryType = Literal[
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
]


@dataclass(frozen=True)
class JournalEntry:
    """One line of `install.journal` per data-model.md §JournalEntry.

    Instances are immutable value objects; `tail_hash` is provided by the
    caller after computing it via `compute_tail_hash(entry_without_hash,
    prev_tail_hash)`. Serialisation to canonical JSON uses `to_canonical_json`.
    """

    entry_id: int
    wrote_at_ns: int
    entry_type: EntryType
    tail_hash: str
    step_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            "entry_id": self.entry_id,
            "wrote_at_ns": self.wrote_at_ns,
            "entry_type": self.entry_type,
            "tail_hash": self.tail_hash,
        }
        if self.step_id is not None or self.entry_type in _LIFECYCLE_ENTRY_TYPES:
            obj["step_id"] = self.step_id
        if self.payload or self.entry_type in _PAYLOAD_ENTRY_TYPES:
            obj["payload"] = self.payload
        return obj


_LIFECYCLE_ENTRY_TYPES: frozenset[str] = frozenset(
    {
        "plan_snapshot_sealed",
        "commit_snapshot_verified",
        "cleanup_started",
        "cleanup_completed",
        "install_aborted",
    }
)

_PAYLOAD_ENTRY_TYPES: frozenset[str] = frozenset(
    {
        "stage_file",
        "delete_orphan",
        "cleanup_started",
        "cleanup_completed",
    }
)


def canonical_json(obj: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 JSON bytes: sorted keys, no insignificant whitespace."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def compute_tail_hash(entry_without_hash: dict[str, Any], prev_tail_hash: str) -> str:
    """Compute the base64url-nopad SRI tail hash for one entry.

    Preimage is `canonical_json(entry).encode("utf-8") + b"\\n" + prev_tail_hash.encode("ascii")`
    per data-model.md §JournalEntry. The first entry uses an empty string as
    `prev_tail_hash`, so its preimage ends with LF.
    """
    if "tail_hash" in entry_without_hash:
        raise ValueError("entry_without_hash must not include 'tail_hash' field")
    preimage = canonical_json(entry_without_hash) + b"\n" + prev_tail_hash.encode("ascii")
    digest = hashlib.sha256(preimage).digest()
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def make_entry(
    *,
    entry_id: int,
    entry_type: EntryType,
    prev_tail_hash: str,
    step_id: int | None = None,
    payload: dict[str, Any] | None = None,
    wrote_at_ns: int | None = None,
) -> JournalEntry:
    """Build a `JournalEntry` with its tail hash already computed.

    `wrote_at_ns` defaults to `time.monotonic_ns()`; pass an explicit value
    for tests that need determinism.
    """
    actual_wrote_at_ns = time.monotonic_ns() if wrote_at_ns is None else wrote_at_ns
    normalized_payload = payload if payload is not None else {}
    body: dict[str, Any] = {
        "entry_id": entry_id,
        "wrote_at_ns": actual_wrote_at_ns,
        "entry_type": entry_type,
    }
    if step_id is not None or entry_type in _LIFECYCLE_ENTRY_TYPES:
        body["step_id"] = step_id
    if normalized_payload or entry_type in _PAYLOAD_ENTRY_TYPES:
        body["payload"] = normalized_payload
    tail_hash = compute_tail_hash(body, prev_tail_hash)
    return JournalEntry(
        entry_id=entry_id,
        wrote_at_ns=actual_wrote_at_ns,
        entry_type=entry_type,
        step_id=step_id,
        payload=normalized_payload,
        tail_hash=tail_hash,
    )


def append_entry(journal_path: Path, entry: JournalEntry) -> None:
    """Append one entry to `journal_path` per the R7 write discipline."""
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(entry.to_dict()) + b"\n"
    with open(journal_path, "ab") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(journal_path.parent)


def read_entries(journal_path: Path) -> list[JournalEntry]:
    """Parse `journal_path` as one JSONL entry per line.

    Chain integrity is NOT verified here — call `verify_chain` on the result.
    A missing file returns an empty list; a trailing empty line is tolerated.
    """
    if not journal_path.exists():
        return []
    entries: list[JournalEntry] = []
    for raw_line in journal_path.read_bytes().splitlines():
        if not raw_line.strip():
            continue
        record = json.loads(raw_line.decode("utf-8"))
        entries.append(
            JournalEntry(
                entry_id=record["entry_id"],
                wrote_at_ns=record["wrote_at_ns"],
                entry_type=record["entry_type"],
                tail_hash=record["tail_hash"],
                step_id=record.get("step_id"),
                payload=record.get("payload", {}),
            )
        )
    return entries


def verify_chain(entries: list[JournalEntry]) -> None:
    """Recompute each entry's expected `tail_hash` and raise on mismatch."""
    prev_tail = ""
    for expected_id, entry in enumerate(entries):
        if entry.entry_id != expected_id:
            raise ValueError(
                f"entry_id at position {expected_id} is {entry.entry_id}; "
                f"chain requires monotonically increasing 0-indexed ids"
            )
        body = {
            k: v for k, v in entry.to_dict().items() if k != "tail_hash"
        }
        recomputed = compute_tail_hash(body, prev_tail)
        if recomputed != entry.tail_hash:
            raise ValueError(
                f"tail_hash mismatch at entry_id {entry.entry_id}: "
                f"expected {recomputed}, got {entry.tail_hash}"
            )
        prev_tail = entry.tail_hash


def _fsync_dir(path: Path) -> None:
    if _IS_WINDOWS:
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
