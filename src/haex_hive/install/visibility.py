"""Visibility marker computation and publication (FR-004, FR-005).

`.haex-hive/visibility.json` is the sole publication event of a completed
install transaction (FR-004). The on-disk shape is defined in
[contracts/visibility-marker.v1.schema.json](../../../specs/008-install-transaction/contracts/visibility-marker.v1.schema.json);
this module holds the in-memory dataclasses and their deterministic
serialiser. Publication (the final `os.replace` into `visibility.json`) is
performed by T030 on top of these types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from haex_hive.io import json_deterministic


@dataclass(frozen=True)
class RootDigest:
    """One participating output root, as recorded in `visibility.json`.

    `root` is a repo-relative directory with a trailing slash
    (e.g. `.haex-hive/`, `.claude/`). `content_integrity` is a
    base64url-nopad SRI SHA-256 digest per Spec 008 research §R5.
    `overlay_paths` is present for mixed-ownership roots — an exhaustive
    allowlist of repo-relative POSIX paths under `root` — and `None` for
    haex-owned roots (the whole tree is owned).
    """

    root: str
    content_integrity: str
    overlay_paths: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            "root": self.root,
            "content_integrity": self.content_integrity,
        }
        if self.overlay_paths is not None:
            obj["overlay_paths"] = list(self.overlay_paths)
        return obj


@dataclass(frozen=True)
class VisibilityMarker:
    """In-memory shape of `.haex-hive/visibility.json` per Spec 008 §FR-004."""

    generation_id: str
    install_lock_content_integrity: str
    participating_roots: tuple[RootDigest, ...]
    haex_hive_version: str = "2"
    written_at: str | None = None

    def __post_init__(self) -> None:
        if not self.participating_roots:
            raise ValueError("participating_roots must be non-empty")
        seen: set[str] = set()
        for entry in self.participating_roots:
            if entry.root in seen:
                raise ValueError(f"duplicate participating root: {entry.root!r}")
            seen.add(entry.root)

    def to_dict(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            "haex_hive_version": self.haex_hive_version,
            "generation_id": self.generation_id,
            "install_lock_content_integrity": self.install_lock_content_integrity,
            "participating_roots": [entry.to_dict() for entry in self.participating_roots],
        }
        if self.written_at is not None:
            obj["written_at"] = self.written_at
        return obj

    def to_json_bytes(self) -> bytes:
        """Deterministic JSON matching `json_deterministic.dumps` conventions."""
        return json_deterministic.dumps(self.to_dict())
