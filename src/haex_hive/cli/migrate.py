"""`haex migrate` handler."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path

from haex_hive.cli.diagnostics import emit_refuse
from haex_hive.constitution.safety import validate_no_plaintext_secrets
from haex_hive.migrate import detect, sidecar, transform
from haex_hive.schema import validator as schema_validator
from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError, UsageError


def _state_root() -> Path:
    if os.environ.get("HAEX_HIVE_STATE"):
        return Path(os.environ["HAEX_HIVE_STATE"])
    return Path.home() / ".local" / "share" / "haex-hive"


def run(args: argparse.Namespace) -> int:
    if args.dry_run and args.check:
        emit_refuse(UsageError(message="--dry-run and --check are mutually exclusive"))
        return exit_codes.USAGE

    repo_root = Path(args.repo_root).resolve()
    v1_path = repo_root / ".haex-hive.json"
    write_mode = not (args.dry_run or args.check)

    if write_mode:
        sidecar.invalidate_stale_sidecar(repo_root)

    if not v1_path.exists():
        emit_refuse(
            HaexError(
                message=f".haex-hive.json not found in {repo_root}",
                context={"path": str(v1_path)},
                diagnostic_key="haex-hive-json-missing",
                exit_code=exit_codes.SYSTEM_REFUSE,
                hint="Run this command inside a repo containing .haex-hive.json.",
            )
        )
        return exit_codes.SYSTEM_REFUSE

    try:
        raw = v1_path.read_bytes()
        version = detect.detect_version(raw)
    except HaexError as exc:
        emit_refuse(exc)
        return exc.exit_code

    if version == 2:
        sys.stderr.write("already migrated to v2 (haex_hive_version: 2)\n")
        return exit_codes.SUCCESS

    try:
        v2_bytes = transform.migrate_v1_to_v2(raw, repo_root, _state_root())
    except HaexError as exc:
        if write_mode:
            sidecar.invalidate_stale_sidecar(repo_root)
        emit_refuse(exc)
        return exc.exit_code

    try:
        schema_validator.validate(json.loads(v2_bytes.decode("utf-8")), "haex-hive.v2.schema.json")
    except Exception as exc:
        if write_mode:
            sidecar.invalidate_stale_sidecar(repo_root)
        emit_refuse(
            HaexError(
                message=f"post-migration schema validation failed: {exc}",
                diagnostic_key="post-migration-schema-invalid",
                exit_code=exit_codes.VALIDATION_REFUSE,
                hint="Report as a bug in the migration table.",
            )
        )
        return exit_codes.VALIDATION_REFUSE

    diff = _unified_diff(raw, v2_bytes, str(v1_path.relative_to(repo_root)))
    if write_mode:
        sidecar.publish_sidecar(repo_root, v2_bytes)
    sys.stdout.write(diff)
    return exit_codes.SUCCESS


def _unified_diff(before: bytes, after: bytes, name: str) -> str:
    before_lines = before.decode("utf-8").splitlines(keepends=True)
    after_lines = after.decode("utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=name,
        tofile=name + ".migrated",
        lineterm="",
    )
    return "".join(line if line.endswith("\n") else line + "\n" for line in diff)
