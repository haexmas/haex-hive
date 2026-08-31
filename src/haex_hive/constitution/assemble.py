"""Constitution assembly: single-source straight-copy (US2) and multi-source
LLM-merge (US3)."""

from __future__ import annotations

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
from haex_hive.io import transaction
from haex_hive.io.file_hash import d15_one_file_tree_digest
from haex_hive.model.install_lock import (
    AssembledBy,
    ConstitutionLockSection,
    ConstitutionSource,
    InstallLock,
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
) -> None:
    """Publish the effective constitution and install.lock atomically.

    Computes content integrity, preserves unknown top-level lock fields from
    any existing lock, and publishes both files under the durable-journal
    protocol with post-write verification of both outputs.

    Args:
        sources: Constitution sources represented in the generated lock.
        body: Effective constitution content to publish.
        repo_root: Repository root path.
        tool_version: Tool version string for install.lock metadata.

    Raises:
        PostWriteValidationError: If the on-disk digest does not match the lock.
    """
    content_integrity = d15_one_file_tree_digest(body)

    existing_lock = _read_existing_lock(repo_root)
    unknown_top_level = existing_lock.unknown_top_level if existing_lock is not None else {}

    lock = InstallLock(
        haex_hive_version="2",
        generated_by=f"{TOOL_NAME} {tool_version}",
        constitution=ConstitutionLockSection(
            sources=sources,
            assembled_by=AssembledBy(tool=TOOL_NAME, version=tool_version),
            content_integrity=content_integrity,
        ),
        unknown_top_level=unknown_top_level,
    )
    lock_bytes = lock.to_json_bytes()

    def post_write_verify() -> None:
        """Verify the published constitution and install.lock agree on integrity.

        Raises:
            PostWriteValidationError: If digest mismatch detected.
        """
        constitution_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.CONSTITUTION_NAME
        lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.INSTALL_LOCK_NAME
        on_disk = constitution_path.read_bytes()
        actual = d15_one_file_tree_digest(on_disk)
        published_lock = InstallLock.from_json(lock_path.read_bytes())
        if (
            actual != content_integrity
            or published_lock.constitution is None
            or actual != published_lock.constitution.content_integrity
        ):
            raise PostWriteValidationError(
                message="on-disk constitution.md does not match recorded content_integrity",
            )

    if state_root is None:
        transaction.publish_pair(
            repo_root,
            body,
            lock_bytes,
            post_write_verify=post_write_verify,
        )
    else:
        transaction.publish_pair(
            repo_root,
            body,
            lock_bytes,
            post_write_verify=post_write_verify,
            state_root=state_root,
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
    )
    return exit_codes.SUCCESS
