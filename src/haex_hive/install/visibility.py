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
class VisibilityMarker:
    """In-memory shape of `.haex-hive/visibility.json` per Spec 008 §FR-004."""

    generation_id: str
    participating_roots: tuple[str, ...]
    haex_hive_version: str = "3"
    written_at: str | None = None

    def __post_init__(self) -> None:
        """Normalize roots and reject empty or duplicate participating roots."""
        object.__setattr__(self, "participating_roots", tuple(self.participating_roots))
        if not self.participating_roots:
            raise ValueError("participating_roots must be non-empty")
        seen: set[str] = set()
        for root in self.participating_roots:
            if root in seen:
                raise ValueError(f"duplicate participating root: {root!r}")
            seen.add(root)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible visibility marker representation."""
        obj: dict[str, Any] = {
            "haex_hive_version": self.haex_hive_version,
            "generation_id": self.generation_id,
            "participating_roots": list(self.participating_roots),
        }
        if self.written_at is not None:
            obj["written_at"] = self.written_at
        return obj

    def to_json_bytes(self) -> bytes:
        """Deterministic JSON matching `json_deterministic.dumps` conventions."""
        return json_deterministic.dumps(self.to_dict())
