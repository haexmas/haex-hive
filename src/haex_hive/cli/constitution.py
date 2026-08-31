"""`haex constitution {assemble,show}` handlers."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from pathlib import Path

from haex_hive.cli.main import INSTALLED_VERSION_STRING
from haex_hive.constitution.assemble import assemble_multi_source, assemble_single_source
from haex_hive.constitution.resolve import resolve_constitution_contributions
from haex_hive.constitution.show import show as render_constitution
from haex_hive.io import transaction
from haex_hive.io.state import default_state_root, transaction_paths
from haex_hive.io.writer_lock import ConstitutionWriterLock
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError, NoSourcesDeclaredError


def _state_root() -> Path:
    """Return the haex-hive state directory path from env or default location."""
    return default_state_root()


def _load_consumer_manifest(repo_root: Path) -> ConsumerManifest:
    """Load and parse the v2 consumer manifest from .haex-hive.json.

    Raises:
        HaexError: If .haex-hive.json is missing or invalid.
    """
    manifest_path = repo_root / ".haex-hive.json"
    if not manifest_path.exists():
        raise HaexError(
            message=".haex-hive.json not found",
            context={"path": str(manifest_path)},
            diagnostic_key="haex-hive-json-missing",
            exit_code=exit_codes.INCOMPLETE_TRANSACTION,
            hint="Run `haex migrate` to produce a v2 file, then retry.",
        )
    raw = manifest_path.read_bytes()
    try:
        return ConsumerManifest.from_json(raw)
    except (ValueError, KeyError) as exc:
        raise HaexError(
            message=f".haex-hive.json is not a valid v2 manifest: {exc}",
            diagnostic_key="haex-hive-json-invalid",
            exit_code=exit_codes.INCOMPLETE_TRANSACTION,
            hint="Run `haex migrate` to produce a valid v2 file.",
        ) from exc


def run_assemble(args: argparse.Namespace) -> int:
    """Execute the `haex constitution assemble` command.

    Resolves constitution contributions from the consumer manifest and assembles
    a single-source constitution under writer lock with durable-journal protocol.

    Returns:
        exit_codes.SUCCESS on successful assembly.

    Raises:
        HaexError: On manifest errors, no sources declared, or assembly failure.
    """
    repo_root = Path(args.repo_root).resolve()
    state_root = _state_root()

    try:
        paths = transaction_paths(repo_root, state_root)
        legacy_lock_was_present = paths.legacy_mutex.exists()
        with ExitStack() as stack:
            # Acquire the legacy lock first so old Spec-007 writers and new
            # shared-state writers cannot publish concurrently during migration.
            # A newly-created compatibility file is removed after the operation.
            stack.enter_context(ConstitutionWriterLock(paths.legacy_mutex))
            if not legacy_lock_was_present:
                # Register cleanup only after acquiring the compatibility lock;
                # a contending legacy writer must never have its lock pathname
                # unlinked from our exception cleanup.
                stack.callback(paths.legacy_mutex.unlink, missing_ok=True)
            stack.enter_context(ConstitutionWriterLock(paths.mutex))
            transaction.recover_if_journaled(repo_root, state_root=state_root)

            manifest = _load_consumer_manifest(repo_root)
            contributions = resolve_constitution_contributions(manifest, state_root)

            if args.accept_merged is not None:
                return assemble_multi_source(
                    contributions,
                    repo_root,
                    llm_method=args.llm,
                    accept_merged_path=args.accept_merged,
                    tool_version=INSTALLED_VERSION_STRING,
                    state_root=state_root,
                )

            if not contributions:
                raise NoSourcesDeclaredError(message="no constitution sources declared")

            if len(contributions) == 1:
                assemble_single_source(
                    contributions[0],
                    repo_root,
                    tool_version=INSTALLED_VERSION_STRING,
                    state_root=state_root,
                )
                return exit_codes.SUCCESS

            return assemble_multi_source(
                contributions,
                repo_root,
                llm_method=args.llm,
                accept_merged_path=None,
                tool_version=INSTALLED_VERSION_STRING,
                state_root=state_root,
            )
    except HaexError:
        raise
    except (OSError, ValueError) as exc:
        raise HaexError(
            message=f"constitution assemble failed: {exc}",
            diagnostic_key="constitution-assemble-failed",
            exit_code=exit_codes.INPUT_REFUSE,
        ) from exc


def run_show(args: argparse.Namespace) -> int:
    """Execute the `haex constitution show` command.

    Verifies the on-disk constitution against install.lock's content_integrity
    before printing the (optionally prefaced) byte-for-byte body.

    Returns:
        exit_codes.SUCCESS on successful, verified output.

    Raises:
        HaexError: On a missing/incomplete transaction, missing constitution or
            install.lock, corrupt install.lock, or an integrity mismatch.
    """
    repo_root = Path(args.repo_root).resolve()
    try:
        render_constitution(
            repo_root,
            no_preface=args.no_preface,
            state_root=_state_root(),
        )
        return exit_codes.SUCCESS
    except HaexError:
        raise
    except (OSError, ValueError) as exc:
        raise HaexError(
            message=f"constitution show failed: {exc}",
            diagnostic_key="constitution-show-failed",
            exit_code=exit_codes.INPUT_REFUSE,
        ) from exc
