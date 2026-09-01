"""Plan-build phase (FR-006 plan snapshot).

Provides the sealed `PlanSnapshot` / `CommitSnapshot` value objects, the
ordered `PlanStep` list per data-model.md, and the plan-build entry point
`build_plan` (T024) that reads `.haex-hive.json`, resolves adopted atoms
against publisher clones, and emits an MVP three-step plan for the
constitution-only case.

**MVP scope note**: `build_plan` handles the single-source constitution
case only. Multi-source LLM-merge stays on the existing
`assemble_multi_source` path until T031 folds them together; multi-source
manifests are refused here with a typed error. Delete-orphans (T049),
hook invocation (Spec 009), and overlay pointers (Spec 010) are not
emitted by this MVP plan.
"""

from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from haex_hive.constitution.resolve import (
    ResolvedConstitutionContribution,
    resolve_constitution_contributions,
)
from haex_hive.git import show as git_show
from haex_hive.io.json_deterministic import compact_json
from haex_hive.migrate.transform import clone_dir
from haex_hive.model._immutable import freeze_json, thaw_json
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.model.source_url import CanonicalSourceUrl
from haex_hive.util.errors import (
    HaexError,
    MissingAtomManifestError,
    MissingPublisherManifestError,
    NoSourcesDeclaredError,
)

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
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Copy and recursively freeze payload data at construction time."""
        object.__setattr__(self, "payload", freeze_json(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-serializable representation of this step."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "participating_root": self.participating_root,
            "payload": thaw_json(self.payload),
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
    publisher_manifest_digests: Mapping[str, str]
    atom_manifest_digests: Mapping[str, str]
    steps: tuple[PlanStep, ...]
    plan_snapshot_digest: str

    def __post_init__(self) -> None:
        """Normalize snapshot collections and validate the sealed digest."""
        object.__setattr__(
            self,
            "publisher_manifest_digests",
            freeze_json(dict(self.publisher_manifest_digests)),
        )
        object.__setattr__(
            self,
            "atom_manifest_digests",
            freeze_json(dict(self.atom_manifest_digests)),
        )
        object.__setattr__(self, "steps", tuple(self.steps))
        if self.sealed_at_ns < 0:
            raise ValueError(f"sealed_at_ns must be non-negative: {self.sealed_at_ns}")
        if not self.steps:
            raise ValueError("steps must be non-empty; zero-step plan is a bug")
        step_ids = [step.step_id for step in self.steps]
        if step_ids != list(range(len(self.steps))):
            raise ValueError(
                f"step_id sequence must be 0..N-1 monotonic, got {step_ids}"
            )
        expected_digest = _plan_snapshot_digest(
            haex_hive_json_digest=self.haex_hive_json_digest,
            publisher_manifest_digests=self.publisher_manifest_digests,
            atom_manifest_digests=self.atom_manifest_digests,
            steps=self.steps,
        )
        if self.plan_snapshot_digest != expected_digest:
            raise ValueError(
                "plan_snapshot_digest does not match the sealed plan contents"
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
            publisher_manifest_digests=publisher_manifest_digests,
            atom_manifest_digests=atom_manifest_digests,
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
    publisher_manifest_digests: Mapping[str, str]
    publisher_manifest_bytes: Mapping[str, bytes]
    atom_manifest_digests: Mapping[str, str]
    atom_manifest_bytes: Mapping[str, bytes]

    def __post_init__(self) -> None:
        """Freeze captured inputs and validate each digest against its bytes."""
        object.__setattr__(self, "haex_hive_json_bytes", bytes(self.haex_hive_json_bytes))
        object.__setattr__(
            self,
            "publisher_manifest_digests",
            freeze_json(dict(self.publisher_manifest_digests)),
        )
        object.__setattr__(
            self,
            "publisher_manifest_bytes",
            freeze_json(
                {key: bytes(value) for key, value in self.publisher_manifest_bytes.items()}
            ),
        )
        object.__setattr__(
            self,
            "atom_manifest_digests",
            freeze_json(dict(self.atom_manifest_digests)),
        )
        object.__setattr__(
            self,
            "atom_manifest_bytes",
            freeze_json(
                {key: bytes(value) for key, value in self.atom_manifest_bytes.items()}
            ),
        )
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
        _expect_digest(
            "haex_hive_json",
            self.haex_hive_json_digest,
            self.haex_hive_json_bytes,
        )
        _expect_map_digests(
            "publisher_manifest",
            self.publisher_manifest_digests,
            self.publisher_manifest_bytes,
        )
        _expect_map_digests(
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
    publisher_manifest_digests: Mapping[str, str],
    atom_manifest_digests: Mapping[str, str],
    steps: tuple[PlanStep, ...],
) -> bytes:
    """Canonical UTF-8 JSON preimage for the plan_snapshot_digest."""
    body: dict[str, Any] = {
        "haex_hive_json_digest": haex_hive_json_digest,
        "publisher_manifest_digests": dict(publisher_manifest_digests),
        "atom_manifest_digests": dict(atom_manifest_digests),
        "steps": [step.to_dict() for step in steps],
    }
    return compact_json(body)


def _plan_snapshot_digest(
    *,
    haex_hive_json_digest: str,
    publisher_manifest_digests: Mapping[str, str],
    atom_manifest_digests: Mapping[str, str],
    steps: tuple[PlanStep, ...],
) -> str:
    """Return the SRI digest for the mutation-relevant plan fields."""
    digest = hashlib.sha256(
        _digest_preimage(
            haex_hive_json_digest=haex_hive_json_digest,
            publisher_manifest_digests=publisher_manifest_digests,
            atom_manifest_digests=atom_manifest_digests,
            steps=steps,
        )
    ).digest()
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _content_digest(content: bytes) -> str:
    """Return the base64url-nopad SHA-256 digest used by install snapshots."""
    digest = hashlib.sha256(content).digest()
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _expect_digest(field_name: str, recorded: str, content: bytes) -> None:
    """Raise when one recorded content digest does not match its bytes."""
    actual = _content_digest(content)
    if recorded != actual:
        raise ValueError(
            f"{field_name} digest does not match captured bytes: "
            f"expected {recorded}, got {actual}"
        )


def _expect_map_digests(
    field_name: str,
    digests: Mapping[str, str],
    bytes_map: Mapping[str, bytes],
) -> None:
    """Validate every recorded digest in a keyed byte map."""
    for key, recorded in digests.items():
        _expect_digest(f"{field_name}[{key!r}]", recorded, bytes_map[key])


def _expect_same_keys(
    field_name: str,
    digests: Mapping[str, str],
    bytes_map: Mapping[str, bytes],
) -> None:
    """Require a one-to-one correspondence between digest and byte keys."""
    if set(digests) != set(bytes_map):
        missing = set(digests) - set(bytes_map)
        extra = set(bytes_map) - set(digests)
        raise ValueError(
            f"{field_name} digests and bytes maps disagree; "
            f"missing bytes for {sorted(missing)}, extra bytes for {sorted(extra)}"
        )


HAEX_HIVE_ROOT = ".haex-hive/"


@dataclass(frozen=True)
class PlanBuildResult:
    """Output of `build_plan`: the sealed snapshot plus the resolved contribution.

    The MVP plan carries the single-source constitution body through so the
    pipeline can stage it under `<root>.next/` at commit time without
    re-resolving. `contribution` records the source metadata the caller needs
    to compose the InstallLock v2 record.
    """

    snapshot: PlanSnapshot
    constitution: ResolvedConstitutionContribution


class MultiSourceNotSupportedByBuildPlan(HaexError):
    """Multi-source manifests still flow through the assemble_multi_source path."""

    diagnostic_key: str = "plan-build-multi-source-unsupported"
    exit_code: int = 2  # INPUT_REFUSE — the caller picks the right path
    hint: str = (
        "Multi-source constitutions use `haex constitution assemble` "
        "(single-source install pipeline via T031 not yet landed)."
    )


def build_plan(
    repo_root: Path,
    state_root: Path,
) -> PlanBuildResult:
    """Read `.haex-hive.json`, resolve one constitution atom, seal a plan.

    Emits three MVP steps under the `.haex-hive/` participating root:
    `stage_file` (constitution.md), `seal_install_lock` (install.lock),
    `publish_marker` (visibility.json). Delete-orphans, hook invocation, and
    overlay pointers are intentionally not emitted here (see module docstring).

    Raises:
        NoSourcesDeclaredError: `.haex-hive.json.atoms` is empty.
        MultiSourceNotSupportedByBuildPlan: More than one atom resolves to a
            constitution contribution; use `assemble_multi_source` for that
            path until T031 lands.
    """
    manifest_path = repo_root / ".haex-hive.json"
    haex_hive_json_bytes = manifest_path.read_bytes()
    haex_hive_json_digest = _content_digest(haex_hive_json_bytes)

    manifest = ConsumerManifest.from_json(haex_hive_json_bytes)
    if not manifest.atoms:
        raise NoSourcesDeclaredError(
            message=".haex-hive.json.atoms is empty; nothing to install",
        )

    publisher_manifest_digests: dict[str, str] = {}
    atom_manifest_digests: dict[str, str] = {}
    for atom_entry in manifest.atoms:
        canonical_source = CanonicalSourceUrl.validate(atom_entry.source)
        repo_dir = clone_dir(state_root, canonical_source)
        publisher_bytes = git_show.show_bytes(
            repo_dir,
            atom_entry.revision,
            "manifest.json",
            not_found_error=MissingPublisherManifestError,
        )
        publisher_key = f"{canonical_source}@{atom_entry.revision}"
        publisher_manifest_digests[publisher_key] = _content_digest(publisher_bytes)

        for atom_id in atom_entry.includes:
            atom_manifest_digests[atom_id] = _content_digest(
                _read_atom_manifest_bytes(repo_dir, atom_entry.revision, atom_id, publisher_bytes),
            )

    contributions = resolve_constitution_contributions(manifest, state_root)
    if not contributions:
        raise NoSourcesDeclaredError(
            message="no atom in .haex-hive.json contributes a constitution",
        )
    if len(contributions) > 1:
        raise MultiSourceNotSupportedByBuildPlan(
            message=(
                f"build_plan MVP handles single-source only; "
                f"{len(contributions)} contributions resolved"
            ),
        )

    contribution = contributions[0]
    constitution_body = contribution.body
    body_digest = _content_digest(constitution_body)

    steps = (
        PlanStep(
            step_id=0,
            step_type="stage_file",
            participating_root=HAEX_HIVE_ROOT,
            payload={
                "path": "constitution.md",
                "content_integrity": body_digest,
            },
        ),
        PlanStep(
            step_id=1,
            step_type="seal_install_lock",
            participating_root=HAEX_HIVE_ROOT,
            payload={"path": "install.lock"},
        ),
        PlanStep(
            step_id=2,
            step_type="publish_marker",
            participating_root=HAEX_HIVE_ROOT,
            payload={"path": "visibility.json"},
        ),
    )
    snapshot = PlanSnapshot.seal(
        haex_hive_json_digest=haex_hive_json_digest,
        publisher_manifest_digests=publisher_manifest_digests,
        atom_manifest_digests=atom_manifest_digests,
        steps=steps,
    )
    return PlanBuildResult(snapshot=snapshot, constitution=contribution)


def _read_atom_manifest_bytes(
    repo_dir: Path,
    revision: str,
    atom_id: str,
    publisher_bytes: bytes,
) -> bytes:
    """Fetch an atom's `manifest.json` bytes via the publisher's atoms map."""
    from haex_hive.model.publisher_manifest import PublisherManifest

    try:
        publisher = PublisherManifest.from_json(publisher_bytes)
    except (ValueError, KeyError) as exc:
        raise MissingPublisherManifestError(
            message=f"publisher manifest at {revision[:12]} is invalid: {exc}",
            context={"sha_short": revision[:12]},
        ) from exc
    entry = publisher.atoms.get(atom_id)
    if entry is None:
        raise MissingAtomManifestError(
            message=f"publisher manifest does not declare atom {atom_id!r}",
        )
    return git_show.show_bytes(
        repo_dir,
        revision,
        f"{entry.path}/manifest.json",
        not_found_error=MissingAtomManifestError,
    )
