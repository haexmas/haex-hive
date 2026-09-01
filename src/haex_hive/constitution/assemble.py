"""Constitution assembly: single-source straight-copy (US2) and multi-source
LLM-merge (US3)."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from contextlib import suppress
from pathlib import Path

from haex_hive.constitution.llm import (
    FileMergeLLM,
    MergeLLM,
    NoneMergeLLM,
    PendingMergeWritten,
    StdioMergeLLM,
    generation_input_identities,
)
from haex_hive.constitution.pending import (
    load_pending,
    pending_path,
    verify_pending_matches_current,
)
from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.constitution.safety import (
    validate_no_concealment_instructions,
    validate_no_plaintext_secrets,
)
from haex_hive.io import json_deterministic, transaction
from haex_hive.model.install_lock import (
    AssembledBy,
    ConstitutionLockSection,
    ConstitutionSource,
    GenerationInputIdentity,
    InstallLock,
    VisibilityMarkerRef,
)
from haex_hive.util import exit_codes
from haex_hive.util.errors import MergeNotConfirmedError, PostWriteValidationError, UsageError

TOOL_NAME = "haex"

DEFAULT_TASK_PROMPT = (
    "Merge the following constitution contributions into a single coherent "
    "constitution. Preserve every non-conflicting principle; where two sources "
    "conflict, resolve explicitly and note the resolution."
)


def _read_existing_lock(repo_root: Path) -> InstallLock | None:
    """Read the existing install.lock if present, returning None on error or absence.

    Best-effort forward-compat preservation; corrupt locks are treated as absent.
    """
    lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.INSTALL_LOCK_NAME
    if not lock_path.exists():
        return None
    try:
        return InstallLock.from_json(lock_path.read_bytes())
    except (OSError, ValueError):
        # Best-effort forward-compat preservation only; a corrupt existing lock
        # is simply replaced wholesale by the fresh generation below.
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
    if existing_marker is not None:
        generation_id = existing_marker.generation_id
    else:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        suffix = hashlib.sha256(body).hexdigest()[:4]
        generation_id = f"g_{timestamp}_{suffix}"
    marker_identity = {
        "haex_hive_version": "2",
        "generation_id": generation_id,
        "participating_roots": [".haex-hive/"],
    }
    lock = InstallLock(
        haex_hive_version="2",
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
    contribution: ResolvedConstitutionContribution,
    repo_root: Path,
    *,
    tool_version: str,
    state_root: Path | None = None,
) -> None:
    validate_no_plaintext_secrets(
        contribution.body, location=f"constitution source {contribution.source.id}"
    )
    _publish_constitution(
        (contribution.source,),
        contribution.body,
        repo_root,
        tool_version=tool_version,
        state_root=state_root,
    )


def _select_adapter(llm_method: str | None, repo_root: Path) -> MergeLLM:
    method = llm_method or os.environ.get("HAEX_LLM")
    if not method:
        method = "stdio" if sys.stdin.isatty() else "none"
    if method == "stdio":
        return StdioMergeLLM()
    if method == "file":
        return FileMergeLLM(repo_root)
    if method == "none":
        return NoneMergeLLM()
    raise UsageError(message=f"unknown --llm method {method!r}")


def assemble_multi_source(
    contributions: list[ResolvedConstitutionContribution],
    repo_root: Path,
    *,
    llm_method: str | None,
    accept_merged_path: Path | None,
    tool_version: str,
    task_prompt: str = DEFAULT_TASK_PROMPT,
    state_root: Path | None = None,
) -> int:
    if accept_merged_path is not None and llm_method is not None:
        raise UsageError(message="--accept-merged and --llm are mutually exclusive")

    ordered_contributions = sorted(
        contributions, key=lambda c: c.source.id.encode("utf-8")
    )
    sorted_sources = tuple(c.source for c in ordered_contributions)

    if accept_merged_path is not None:
        candidate = accept_merged_path.read_bytes()
        validate_no_plaintext_secrets(candidate, location="accepted merge candidate")

        pending = load_pending(repo_root)
        verify_pending_matches_current(pending, contributions)

        validate_no_concealment_instructions(candidate)

        _publish_constitution(
            sorted_sources,
            candidate,
            repo_root,
            tool_version=tool_version,
            state_root=state_root,
            generation_inputs=generation_input_identities("file", pending.task_prompt),
        )
        with suppress(FileNotFoundError):
            pending_path(repo_root).unlink()
        return exit_codes.SUCCESS

    for c in contributions:
        validate_no_plaintext_secrets(c.body, location=f"constitution source {c.source.id}")

    adapter = _select_adapter(llm_method, repo_root)

    try:
        result = adapter.merge(ordered_contributions, task_prompt)
    except PendingMergeWritten:
        return exit_codes.SYSTEM_REFUSE

    if not result.confirmed:
        raise MergeNotConfirmedError(message="merge candidate was not confirmed")

    validate_no_concealment_instructions(result.candidate)

    _publish_constitution(
        sorted_sources,
        result.candidate,
        repo_root,
        tool_version=tool_version,
        state_root=state_root,
        generation_inputs=result.generation_inputs,
    )
    return exit_codes.SUCCESS
