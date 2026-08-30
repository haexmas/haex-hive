"""Pending-merge helpers for the `--llm=file` two-phase flow (FR-039, data-model.md §PendingMerge).

`.haex-hive/constitution.merge.pending.json` binds phase two to the exact
phase-one inputs via `pending_id`: a SHA-256 digest over the canonical
`haex-hive-constitution-pending-v1` length-prefixed serialization of every
source's `id`, `revision`, `source`, and raw `body` bytes, in bytewise UTF-8
ID order.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.io import json_deterministic, transaction
from haex_hive.util.errors import PendingMergeInputsMismatchError

PENDING_FILE_NAME = "constitution.merge.pending.json"

_MAGIC = b"haex-hive-constitution-pending-v1\x00"


@dataclass(frozen=True)
class PendingContribution:
    id: str
    revision: str
    source: str
    body_base64: str


@dataclass(frozen=True)
class PendingMerge:
    sources: tuple[PendingContribution, ...]
    task_prompt: str
    pending_id: str


def pending_path(repo_root: Path) -> Path:
    return repo_root / transaction.HAEX_HIVE_DIR / PENDING_FILE_NAME


def _length_prefixed(value: bytes) -> bytes:
    return str(len(value)).encode("ascii") + b"\x00" + value


def derive_pending_id(entries: list[tuple[str, str, str, bytes]]) -> str:
    """entries: (id, revision, source, body) tuples, any order — sorted internally."""
    ordered = sorted(entries, key=lambda e: e[0].encode("utf-8"))
    buf = bytearray(_MAGIC)
    for atom_id, revision, source, body in ordered:
        buf += b"S\x00"
        buf += _length_prefixed(atom_id.encode("utf-8"))
        buf += _length_prefixed(revision.encode("utf-8"))
        buf += _length_prefixed(source.encode("utf-8"))
        buf += _length_prefixed(body)
    digest = hashlib.sha256(bytes(buf)).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


def serialize_pending(
    contributions: list[ResolvedConstitutionContribution], task_prompt: str
) -> bytes:
    entries = [
        (c.source.id, c.source.revision, c.source.source, c.body) for c in contributions
    ]
    pending_id = derive_pending_id(entries)
    ordered = sorted(contributions, key=lambda c: c.source.id.encode("utf-8"))
    obj = {
        "sources": [
            {
                "id": c.source.id,
                "revision": c.source.revision,
                "source": c.source.source,
                "body_base64": base64.b64encode(c.body).decode("ascii"),
            }
            for c in ordered
        ],
        "task_prompt": task_prompt,
        "pending_id": pending_id,
    }
    return json_deterministic.dumps(obj)


def load_pending(repo_root: Path) -> PendingMerge:
    raw = pending_path(repo_root).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    sources = tuple(
        PendingContribution(
            id=s["id"], revision=s["revision"], source=s["source"], body_base64=s["body_base64"]
        )
        for s in data["sources"]
    )
    return PendingMerge(
        sources=sources, task_prompt=data["task_prompt"], pending_id=data["pending_id"]
    )


def verify_pending_matches_current(
    pending: PendingMerge, freshly_resolved: list[ResolvedConstitutionContribution]
) -> None:
    decoded_entries = [
        (s.id, s.revision, s.source, base64.b64decode(s.body_base64)) for s in pending.sources
    ]
    decoded_id = derive_pending_id(decoded_entries)

    fresh_entries = [
        (c.source.id, c.source.revision, c.source.source, c.body) for c in freshly_resolved
    ]
    fresh_id = derive_pending_id(fresh_entries)

    if not (pending.pending_id == decoded_id == fresh_id):
        raise PendingMergeInputsMismatchError(
            message="pending merge inputs do not match the current manifest resolution",
        )
