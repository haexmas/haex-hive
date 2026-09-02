"""`haex install` handler (Spec 008, US1 MVP).

Resolves `.haex-hive.json`'s adopted atoms and publishes a new generation
via the rename-swap primitive. Idempotent: a re-invocation with an
unchanged effective input set is a no-op and reports "no changes" without
allocating a new generation ID or touching disk.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from haex_hive.cli.main import INSTALLED_VERSION_STRING
from haex_hive.constitution.assemble import assemble_multi_source, assemble_single_source
from haex_hive.constitution.resolve import resolve_constitution_contributions
from haex_hive.install import inflight
from haex_hive.install.lock import OwnerToken
from haex_hive.io import transaction
from haex_hive.io.state import default_state_root, transaction_paths
from haex_hive.io.writer_lock import ConstitutionWriterLock
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.model.install_lock import InstallLock
from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError, NoSourcesDeclaredError


def _load_consumer_manifest(repo_root: Path) -> ConsumerManifest:
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


def _live_generation_id(repo_root: Path) -> str | None:
    lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.INSTALL_LOCK_NAME
    if not lock_path.exists():
        return None
    try:
        lock = InstallLock.from_json(lock_path.read_bytes())
    except (OSError, ValueError):
        return None
    if lock.visibility_marker is None:
        return None
    return lock.visibility_marker.generation_id


def _is_no_op_single_source(
    repo_root: Path, body: bytes, source_id: str, source_revision: str
) -> bool:
    """True when on-disk publication already matches the single-source candidate.

    Compares the constitution body byte-for-byte and the recorded source
    identity/revision. Fields under transaction metadata (generation_id,
    written_at) are ignored — those change on every publication and are the
    whole reason for having a no-op path.
    """
    live_root = repo_root / transaction.HAEX_HIVE_DIR
    constitution_path = live_root / transaction.CONSTITUTION_NAME
    lock_path = live_root / transaction.INSTALL_LOCK_NAME
    if not (constitution_path.exists() and lock_path.exists()):
        return False
    if constitution_path.read_bytes() != body:
        return False
    try:
        lock = InstallLock.from_json(lock_path.read_bytes())
    except (OSError, ValueError):
        return False
    if lock.constitution is None or len(lock.constitution.sources) != 1:
        return False
    recorded = lock.constitution.sources[0]
    if recorded.id != source_id or recorded.revision != source_revision:
        return False
    return lock.participating_roots == (".haex-hive/",)


def run(args: argparse.Namespace) -> int:
    """`haex install` — US1 MVP: publish resolved atoms as a new generation."""
    repo_root = Path(args.repo_root).resolve()
    state_root = default_state_root()

    try:
        paths = transaction_paths(repo_root, state_root)
        with ConstitutionWriterLock(paths.mutex, OwnerToken.emit()):
            inflight.resolve(repo_root / transaction.HAEX_HIVE_DIR)

            manifest = _load_consumer_manifest(repo_root)
            contributions = resolve_constitution_contributions(manifest, state_root)
            if not contributions:
                raise NoSourcesDeclaredError(message="no constitution sources declared")

            if len(contributions) == 1:
                contribution = contributions[0]
                if _is_no_op_single_source(
                    repo_root,
                    contribution.body,
                    contribution.source.id,
                    contribution.source.revision,
                ):
                    sys.stdout.write("no changes\n")
                    return exit_codes.SUCCESS

                assemble_single_source(
                    contribution,
                    repo_root,
                    tool_version=INSTALLED_VERSION_STRING,
                    state_root=state_root,
                )
                new_generation_id = _live_generation_id(repo_root)
                sys.stdout.write(
                    f"installed generation {new_generation_id}\n"
                )
                return exit_codes.SUCCESS

            return assemble_multi_source(
                contributions,
                repo_root,
                llm_method=getattr(args, "llm", None),
                accept_merged_path=getattr(args, "accept_merged", None),
                tool_version=INSTALLED_VERSION_STRING,
                state_root=state_root,
            )
    except HaexError:
        raise
    except (OSError, ValueError) as exc:
        raise HaexError(
            message=f"install failed: {exc}",
            diagnostic_key="install-failed",
            exit_code=exit_codes.INPUT_REFUSE,
        ) from exc
