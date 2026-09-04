"""Constitution assembly: single-source straight-copy (US2).

The multi-source LLM-merge path (US3) was retired by ADR 0010: a repository
adopts exactly one non-negotiable prose atom, so `haex install` never needs
to reconcile multiple constitution contributions into one document.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.constitution.safety import (
    validate_no_concealment_instructions,
    validate_no_plaintext_secrets,
)
from haex_hive.install.generation import allocate_generation_id
from haex_hive.io import json_deterministic, transaction
from haex_hive.model.install_lock import (
    AssembledBy,
    ConstitutionLockSection,
    ConstitutionSource,
    GenerationInputIdentity,
    InstallLock,
    VisibilityMarkerRef,
)
from haex_hive.util.errors import HaexError, PostWriteValidationError

TOOL_NAME = "haex"


def _read_existing_lock(repo_root: Path) -> InstallLock | None:
    """Read the existing install.lock if present, returning None on error or absence.

    Best-effort forward-compat preservation; corrupt locks are treated as absent.
    """
    lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.INSTALL_LOCK_NAME
    if not lock_path.exists():
        return None
    try:
        return InstallLock.from_json(lock_path.read_bytes())
    except (OSError, ValueError, HaexError):
        # Best-effort forward-compat preservation only; a corrupt or
        # schema-incompatible existing lock (e.g. a pre-v3 lock read by the
        # v3-only reader) is simply replaced wholesale by the fresh
        # generation below.
        return None


def _publish_constitution(
    sources: tuple[ConstitutionSource, ...],
    body: bytes,
    repo_root: Path,
    *,
    tool_version: str,
    state_root: Path | None = None,
    generation_inputs: tuple[GenerationInputIdentity, ...] = (),
) -> None:
    """Publish the effective constitution and install.lock atomically.

    Preserves unknown top-level lock fields from any existing lock and
    publishes all output files as one rename-swap generation with post-write
    verification of the published outputs.

    Args:
        sources: Constitution sources represented in the generated lock.
        body: Effective constitution content to publish.
        repo_root: Repository root path.
        tool_version: Tool version string for install.lock metadata.

    Raises:
        PostWriteValidationError: If the published files disagree.
    """
    existing_lock = _read_existing_lock(repo_root)
    unknown_top_level = (
        dict(existing_lock.unknown_top_level) if existing_lock is not None else {}
    )

    existing_marker = existing_lock.visibility_marker if existing_lock is not None else None
    generation_id = allocate_generation_id(
        body,
        existing_marker.generation_id if existing_marker is not None else None,
    )
    marker_identity = {
        "haex_hive_version": "3",
        "generation_id": generation_id,
        "participating_roots": [".haex-hive/"],
    }
    lock = InstallLock(
        haex_hive_version="3",
        generated_by=f"{TOOL_NAME} {tool_version}",
        constitution=ConstitutionLockSection(
            sources=sources,
            assembled_by=AssembledBy(tool=TOOL_NAME, version=tool_version),
        ),
        participating_roots=(".haex-hive/",),
        visibility_marker=VisibilityMarkerRef(
            generation_id=generation_id,
        ),
        generation_inputs=tuple(
            sorted(generation_inputs, key=lambda item: (item.kind, item.id))
        )
        or None,
        unknown_top_level=unknown_top_level,
    )
    lock_bytes = lock.to_json_bytes()
    # Validate the complete lock envelope before any staged bytes are published.
    InstallLock.from_json(lock_bytes)
    visibility_bytes = json_deterministic.dumps(marker_identity)

    def post_write_verify() -> None:
        """Verify the published constitution, lock, and marker agree.

        Raises:
            PostWriteValidationError: If digest mismatch detected.
        """
        lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.INSTALL_LOCK_NAME
        published_lock = InstallLock.from_json(lock_path.read_bytes())
        if (
            published_lock.constitution is None
            or published_lock.visibility_marker is None
            or published_lock.visibility_marker.generation_id != generation_id
            or published_lock.participating_roots != (".haex-hive/",)
        ):
            raise PostWriteValidationError(
                message="published install.lock does not match the assembled generation",
            )
        marker = json.loads(
            (repo_root / transaction.HAEX_HIVE_DIR / transaction.VISIBILITY_NAME)
            .read_bytes()
        )
        if (
            marker.get("generation_id") != generation_id
            or marker != marker_identity
        ):
            raise PostWriteValidationError(
                message="visibility.json does not match the published install.lock",
            )

    live_dir = repo_root / transaction.HAEX_HIVE_DIR
    transaction.publish_generation(
        live_dir,
        [
            transaction.StagedFile(transaction.CONSTITUTION_NAME, body),
            transaction.StagedFile(transaction.INSTALL_LOCK_NAME, lock_bytes),
            transaction.StagedFile(transaction.VISIBILITY_NAME, visibility_bytes),
        ],
        post_write_verify=post_write_verify,
        state_root=state_root,
        repo_root=repo_root,
    )


def assemble_single_source(
    contributions: Sequence[ResolvedConstitutionContribution],
    repo_root: Path,
    *,
    tool_version: str,
    state_root: Path | None = None,
) -> None:
    """Publish all constitution files from one molecule without merging sources.

    The v3 constitution category may contain multiple files. They retain the
    resolver's deterministic order and are separated by one newline in the
    generated constitution. The lock records the molecule only once.
    """
    if not contributions:
        raise ValueError("at least one constitution contribution is required")

    source = contributions[0].source
    if any(contribution.source != source for contribution in contributions[1:]):
        raise ValueError("single-source assembly received multiple molecule sources")

    for contribution in contributions:
        validate_no_plaintext_secrets(
            contribution.body, location=f"constitution source {contribution.source.id}"
        )
        # Principle VIII (ADR 0010): retained on the single-source path even
        # though there is no adapter-produced candidate to police anymore.
        validate_no_concealment_instructions(contribution.body)

    _publish_constitution(
        (source,),
        b"\n".join(contribution.body for contribution in contributions),
        repo_root,
        tool_version=tool_version,
        state_root=state_root,
    )
