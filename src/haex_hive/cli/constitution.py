"""`haex constitution {assemble,show}` handlers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from haex_hive.cli.diagnostics import emit_refuse
from haex_hive.cli.main import INSTALLED_VERSION_STRING
from haex_hive.constitution.assemble import assemble_single_source
from haex_hive.constitution.resolve import resolve_constitution_contributions
from haex_hive.io import transaction
from haex_hive.io.writer_lock import ConstitutionWriterLock
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError, NoSourcesDeclaredError


def _state_root() -> Path:
    if os.environ.get("HAEX_HIVE_STATE"):
        return Path(os.environ["HAEX_HIVE_STATE"])
    return Path.home() / ".local" / "share" / "haex-hive"


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


def run_assemble(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.WRITER_LOCK_NAME

    try:
        with ConstitutionWriterLock(lock_path):
            transaction.recover_if_journaled(repo_root)

            manifest = _load_consumer_manifest(repo_root)
            contributions = resolve_constitution_contributions(manifest, _state_root())

            if not contributions:
                raise NoSourcesDeclaredError(message="no constitution sources declared")

            if len(contributions) > 1:
                raise HaexError(
                    message="multi-source constitution assemble is not available in this release",
                    diagnostic_key="not-implemented",
                    exit_code=exit_codes.USAGE,
                    hint="Multi-source assembly ships in a later phase.",
                )

            assemble_single_source(
                contributions[0], repo_root, tool_version=INSTALLED_VERSION_STRING
            )
            return exit_codes.SUCCESS
    except HaexError:
        raise
    except (OSError, ValueError) as exc:
        raise HaexError(
            message=f"constitution assemble failed: {exc}",
            diagnostic_key="constitution-assemble-failed",
            exit_code=exit_codes.INPUT_REFUSE,
        ) from exc


def run_show(args: argparse.Namespace) -> int:  # noqa: ARG001
    emit_refuse(
        HaexError(
            message="haex constitution show is not available in this release",
            diagnostic_key="not-implemented",
            exit_code=exit_codes.USAGE,
            hint="Constitution show ships in a later phase.",
        )
    )
    return exit_codes.USAGE
