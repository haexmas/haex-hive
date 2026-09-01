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
import tempfile
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from haex_hive.model._immutable import freeze_json, thaw_json

_IS_WINDOWS = sys.platform == "win32"
_JOURNAL_STATE_SUFFIX = ".meta"

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
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Copy and recursively freeze the payload supplied by the caller."""
        object.__setattr__(self, "payload", freeze_json(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        """Return a detached, JSON-serializable representation of the entry."""
        obj: dict[str, Any] = {
            "entry_id": self.entry_id,
            "wrote_at_ns": self.wrote_at_ns,
            "entry_type": self.entry_type,
            "tail_hash": self.tail_hash,
        }
        if self.step_id is not None or self.entry_type in _LIFECYCLE_ENTRY_TYPES:
            obj["step_id"] = self.step_id
        if self.payload or self.entry_type in _PAYLOAD_ENTRY_TYPES:
            obj["payload"] = thaw_json(self.payload)
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
    payload: Mapping[str, Any] | None = None,
    wrote_at_ns: int | None = None,
) -> JournalEntry:
    """Build a `JournalEntry` with its tail hash already computed.

    `wrote_at_ns` defaults to `time.monotonic_ns()`; pass an explicit value
    for tests that need determinism.
    """
    actual_wrote_at_ns = time.monotonic_ns() if wrote_at_ns is None else wrote_at_ns
    normalized_payload = freeze_json(dict(payload)) if payload is not None else freeze_json({})
    body: dict[str, Any] = {
        "entry_id": entry_id,
        "wrote_at_ns": actual_wrote_at_ns,
        "entry_type": entry_type,
    }
    if step_id is not None or entry_type in _LIFECYCLE_ENTRY_TYPES:
        body["step_id"] = step_id
    if normalized_payload or entry_type in _PAYLOAD_ENTRY_TYPES:
        body["payload"] = thaw_json(normalized_payload)
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
    """Append one entry and durably record the expected journal tail."""
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(entry.to_dict()) + b"\n"
    with open(journal_path, "ab") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(journal_path.parent)
    _write_journal_state(
        journal_path,
        entry_count=entry.entry_id + 1,
        tail_hash=entry.tail_hash,
    )


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


def verify_chain(
    entries: list[JournalEntry],
    *,
    journal_path: Path | None = None,
    expected_entry_count: int | None = None,
    expected_tail_hash: str | None = None,
) -> None:
    """Verify the chain and optionally compare durable final-state metadata.

    Passing `journal_path` makes this suitable for recovery: a valid prefix is
    rejected when complete trailing records were removed from the JSONL file.
    """
    if journal_path is not None:
        expected_entry_count, expected_tail_hash = _read_journal_state(journal_path)

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

    if expected_entry_count is not None and len(entries) != expected_entry_count:
        raise ValueError(
            f"journal entry count mismatch: expected {expected_entry_count}, "
            f"got {len(entries)}"
        )
    if expected_tail_hash is not None:
        actual_tail_hash = entries[-1].tail_hash if entries else ""
        if actual_tail_hash != expected_tail_hash:
            raise ValueError(
                f"journal tail hash mismatch: expected {expected_tail_hash}, "
                f"got {actual_tail_hash}"
            )


def read_verified_entries(journal_path: Path) -> list[JournalEntry]:
    """Recover, read, and verify a journal against its committed final state.

    The JSONL file is written before its metadata sidecar. If the process is
    interrupted in that interval, entries beyond the sidecar's committed
    count are uncommitted and are truncated. A sidecar that claims entries
    missing from the journal is treated as an integrity failure.
    """
    state_path = _journal_state_path(journal_path)
    if not journal_path.exists():
        if state_path.exists():
            raise ValueError("journal is missing but journal state metadata exists")
        return []

    if not state_path.exists():
        _truncate_journal(journal_path, 0)
        return []
    expected_count, expected_tail_hash = _read_journal_state(journal_path)

    entries, entry_end_offsets = _read_recovery_entries(journal_path)
    if len(entries) < expected_count:
        raise ValueError(
            f"journal entry count mismatch: expected at least {expected_count}, "
            f"got {len(entries)}"
        )

    committed_entries = entries[:expected_count]
    verify_chain(committed_entries)
    actual_tail_hash = committed_entries[-1].tail_hash if committed_entries else ""
    if actual_tail_hash != expected_tail_hash:
        raise ValueError(
            f"journal tail hash mismatch: expected {expected_tail_hash}, "
            f"got {actual_tail_hash}"
        )

    committed_end = entry_end_offsets[expected_count - 1] if expected_count else 0
    if len(entries) > expected_count or journal_path.stat().st_size != committed_end:
        _truncate_journal(journal_path, committed_end)
    return committed_entries


def _journal_state_path(journal_path: Path) -> Path:
    """Return the sidecar path containing the durable journal final state."""
    return journal_path.with_name(journal_path.name + _JOURNAL_STATE_SUFFIX)


def _write_journal_state(
    journal_path: Path,
    *,
    entry_count: int,
    tail_hash: str,
) -> None:
    """Atomically write and fsync the expected journal count and tail hash."""
    state_path = _journal_state_path(journal_path)
    fd, tmp_path = tempfile.mkstemp(
        prefix=state_path.name + ".",
        dir=str(state_path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(
                canonical_json({"entry_count": entry_count, "tail_hash": tail_hash})
            )
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, state_path)
        _fsync_dir(state_path.parent)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise


def _read_journal_state(journal_path: Path) -> tuple[int, str]:
    """Read and validate the durable expected count and final tail hash."""
    state_path = _journal_state_path(journal_path)
    try:
        record = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"journal state metadata is missing: {state_path}") from exc
    if (
        not isinstance(record, dict)
        or not isinstance(record.get("entry_count"), int)
        or isinstance(record["entry_count"], bool)
        or record["entry_count"] < 0
        or not isinstance(record.get("tail_hash"), str)
    ):
        raise ValueError(f"journal state metadata is invalid: {state_path}")
    return record["entry_count"], record["tail_hash"]


def _read_recovery_entries(journal_path: Path) -> tuple[list[JournalEntry], list[int]]:
    """Read complete JSONL records and stop at an interrupted final record."""
    raw_bytes = journal_path.read_bytes()
    entries: list[JournalEntry] = []
    entry_end_offsets: list[int] = []
    offset = 0
    for raw_line in raw_bytes.splitlines(keepends=True):
        end_offset = offset + len(raw_line)
        if not raw_line.strip():
            offset = end_offset
            continue
        if not raw_line.endswith(b"\n"):
            break
        try:
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
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            if end_offset == len(raw_bytes):
                break
            raise ValueError(f"invalid journal record before final line: {exc}") from exc
        entry_end_offsets.append(end_offset)
        offset = end_offset
    return entries, entry_end_offsets


def _truncate_journal(journal_path: Path, size: int) -> None:
    """Truncate an uncommitted journal suffix and durably persist the result."""
    with open(journal_path, "r+b") as fh:
        fh.truncate(size)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(journal_path.parent)


def _fsync_dir(path: Path) -> None:
    if _IS_WINDOWS:
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
