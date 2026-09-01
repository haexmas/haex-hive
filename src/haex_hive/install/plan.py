"""Plan-build phase (FR-006 plan snapshot).

Provides the sealed `PlanSnapshot` / `CommitSnapshot` value objects and the
ordered `PlanStep` list per data-model.md. The plan-build entry point
(reading `.haex-hive.json`, resolving atoms, emitting the step list) lands
in T024 on top of these types.
"""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from haex_hive.install.journal import canonical_json

StepType = Literal[
    "stage_file",
    "delete_orphan",
    "overlay_pointer",
    "hook_invoke",
    "seal_install_lock",
    "publish_marker",
]


@dataclass(frozen=True)
class PlanStep:
    """One participant in the transaction plan (see data-model.md §PlanStep)."""

    step_id: int
    step_type: StepType
    participating_root: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "participating_root": self.participating_root,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class PlanSnapshot:
    """Sealed capture of every input the transaction depends on.

    `sealed_at_ns` is informational and NOT part of `plan_snapshot_digest`;
    every other field is. Use `PlanSnapshot.seal(...)` to construct — it
    computes `plan_snapshot_digest` for you from a canonical serialisation
    of the remaining fields.
    """

    sealed_at_ns: int
    haex_hive_json_digest: str
    publisher_manifest_digests: dict[str, str]
    atom_manifest_digests: dict[str, str]
    steps: tuple[PlanStep, ...]
    plan_snapshot_digest: str

    def __post_init__(self) -> None:
        if self.sealed_at_ns < 0:
            raise ValueError(f"sealed_at_ns must be non-negative: {self.sealed_at_ns}")
        if not self.steps:
            raise ValueError("steps must be non-empty; zero-step plan is a bug")
        step_ids = [step.step_id for step in self.steps]
        if step_ids != list(range(len(self.steps))):
            raise ValueError(
                f"step_id sequence must be 0..N-1 monotonic, got {step_ids}"
            )

    @classmethod
    def seal(
        cls,
        *,
        haex_hive_json_digest: str,
        publisher_manifest_digests: dict[str, str],
        atom_manifest_digests: dict[str, str],
        steps: tuple[PlanStep, ...],
        sealed_at_ns: int | None = None,
    ) -> PlanSnapshot:
        """Build a sealed snapshot and derive `plan_snapshot_digest`.

        Every field except the informational `sealed_at_ns` participates in
        the canonical preimage.
        """
        actual_sealed_at_ns = time.monotonic_ns() if sealed_at_ns is None else sealed_at_ns
        preimage = _digest_preimage(
            haex_hive_json_digest=haex_hive_json_digest,
            publisher_manifest_digests=publisher_manifest_digests,
            atom_manifest_digests=atom_manifest_digests,
            steps=steps,
        )
        digest = hashlib.sha256(preimage).digest()
        plan_snapshot_digest = (
            "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        )
        return cls(
            sealed_at_ns=actual_sealed_at_ns,
            haex_hive_json_digest=haex_hive_json_digest,
            publisher_manifest_digests=dict(publisher_manifest_digests),
            atom_manifest_digests=dict(atom_manifest_digests),
            steps=steps,
            plan_snapshot_digest=plan_snapshot_digest,
        )


@dataclass(frozen=True)
class CommitSnapshot:
    """Fresh re-read of the same inputs while the exclusive install lock is held.

    Records both the current digests and the captured bytes for each keyed
    input. On a successful `matches()` check against the `PlanSnapshot`, the
    captured bytes are the immutable transaction-owned input snapshot the
    resolver hydrates from.
    """

    haex_hive_json_digest: str
    haex_hive_json_bytes: bytes
    publisher_manifest_digests: dict[str, str]
    publisher_manifest_bytes: dict[str, bytes]
    atom_manifest_digests: dict[str, str]
    atom_manifest_bytes: dict[str, bytes]

    def __post_init__(self) -> None:
        _expect_same_keys(
            "publisher_manifest",
            self.publisher_manifest_digests,
            self.publisher_manifest_bytes,
        )
        _expect_same_keys(
            "atom_manifest",
            self.atom_manifest_digests,
            self.atom_manifest_bytes,
        )

    def matches(self, plan: PlanSnapshot) -> bool:
        """Return True when digests equal the corresponding PlanSnapshot digests."""
        return (
            self.haex_hive_json_digest == plan.haex_hive_json_digest
            and self.publisher_manifest_digests == plan.publisher_manifest_digests
            and self.atom_manifest_digests == plan.atom_manifest_digests
        )


def _digest_preimage(
    *,
    haex_hive_json_digest: str,
    publisher_manifest_digests: dict[str, str],
    atom_manifest_digests: dict[str, str],
    steps: tuple[PlanStep, ...],
) -> bytes:
    """Canonical UTF-8 JSON preimage for the plan_snapshot_digest."""
    body: dict[str, Any] = {
        "haex_hive_json_digest": haex_hive_json_digest,
        "publisher_manifest_digests": dict(publisher_manifest_digests),
        "atom_manifest_digests": dict(atom_manifest_digests),
        "steps": [step.to_dict() for step in steps],
    }
    return canonical_json(body)


def _expect_same_keys(
    field_name: str,
    digests: dict[str, str],
    bytes_map: dict[str, bytes],
) -> None:
    if set(digests) != set(bytes_map):
        missing = set(digests) - set(bytes_map)
        extra = set(bytes_map) - set(digests)
        raise ValueError(
            f"{field_name} digests and bytes maps disagree; "
            f"missing bytes for {sorted(missing)}, extra bytes for {sorted(extra)}"
        )
