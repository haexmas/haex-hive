"""Constitution assembly: single-source straight-copy (US2) and multi-source
LLM-merge (US3)."""

from __future__ import annotations

import base64
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
from haex_hive.io.file_hash import d15_one_file_tree_digest
from haex_hive.model.install_lock import (
    AssembledBy,
    ConstitutionLockSection,
    ConstitutionSource,
    InstallLock,
    RootRecord,
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
) -> None:
    """Publish the effective constitution and install.lock atomically.

    Computes content integrity, preserves unknown top-level lock fields from
    any existing lock, and publishes all output files as one rename-swap
    generation with post-write verification of the published outputs.

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
    unknown_top_level = (
        dict(existing_lock.unknown_top_level) if existing_lock is not None else {}
    )

    root_preimage = (
        b"constitution.md:"
        + hashlib.sha256(body).hexdigest().encode("ascii")
        + b"\n"
    )
    root_digest = "sha256-" + base64.urlsafe_b64encode(
        hashlib.sha256(root_preimage).digest()
    ).decode("ascii").rstrip("=")
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
        "participating_roots": [
            {"root": ".haex-hive/", "content_integrity": root_digest}
        ],
    }
    marker_content_integrity = "sha256-" + base64.urlsafe_b64encode(
        hashlib.sha256(json_deterministic.dumps(marker_identity)).digest()
    ).decode("ascii").rstrip("=")

    lock = InstallLock(
        haex_hive_version="2",
        generated_by=f"{TOOL_NAME} {tool_version}",
        constitution=ConstitutionLockSection(
            sources=sources,
            assembled_by=AssembledBy(tool=TOOL_NAME, version=tool_version),
            content_integrity=content_integrity,
        ),
        participating_roots=(
            RootRecord(root=".haex-hive/", content_integrity=root_digest),
        ),
        visibility_marker=VisibilityMarkerRef(
            generation_id=generation_id,
            content_integrity=marker_content_integrity,
        ),
        unknown_top_level=unknown_top_level,
    )
    lock_bytes = lock.to_json_bytes()
    visibility_body = dict(marker_identity)
    visibility_body["install_lock_content_integrity"] = "sha256-" + base64.urlsafe_b64encode(
        hashlib.sha256(lock_bytes).digest()
    ).decode("ascii").rstrip("=")
    visibility_bytes = json_deterministic.dumps(visibility_body)

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
        marker = json.loads(
            (repo_root / transaction.HAEX_HIVE_DIR / transaction.VISIBILITY_NAME)
            .read_bytes()
        )
        if (
            marker.get("generation_id") != generation_id
            or marker.get("participating_roots") != marker_identity["participating_roots"]
            or marker.get("install_lock_content_integrity") != (
                "sha256-"
                + base64.urlsafe_b64encode(
                    hashlib.sha256(lock_path.read_bytes()).digest()
                )
                .decode("ascii")
                .rstrip("=")
            )
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
