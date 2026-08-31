"""`haex` CLI root: argparse dispatch + version gate."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
from collections.abc import Sequence
from pathlib import Path

from haex_hive.cli.diagnostics import emit_refuse
from haex_hive.model.version_constraint import VersionConstraint
from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError, VersionBelowMinError

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def _installed_version() -> tuple[int, int, int]:
    """Return the installed package version as a numeric tuple."""
    try:
        version = importlib.metadata.version("haex-hive")
    except importlib.metadata.PackageNotFoundError:
        return (2, 0, 0)
    match = _VERSION_RE.match(version)
    if not match:
        return (2, 0, 0)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


INSTALLED_VERSION = _installed_version()
INSTALLED_VERSION_STRING = ".".join(str(n) for n in INSTALLED_VERSION)


def _check_min_version(repo_root: Path) -> None:
    """Refuse execution when the repository requires a newer haex version."""
    manifest_path = repo_root / ".haex-hive.json"
    if not manifest_path.exists():
        return
    try:
        raw = manifest_path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    min_version_raw = data.get("haex_hive_min_version")
    if not min_version_raw:
        return
    try:
        constraint = VersionConstraint.parse(min_version_raw)
    except ValueError as exc:
        raise VersionBelowMinError(
            message=f"invalid haex_hive_min_version: {exc}",
        ) from None
    if not constraint.satisfied_by(INSTALLED_VERSION):
        installed = ".".join(str(n) for n in INSTALLED_VERSION)
        raise VersionBelowMinError(
            message=f"installed haex {installed} does not satisfy {min_version_raw!r}",
            context={"installed": installed, "required": min_version_raw},
        )


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level command-line parser."""
    parser = argparse.ArgumentParser(prog="haex")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate = subparsers.add_parser("migrate", help="rewrite v1 `.haex-hive.json` into v2")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--check", action="store_true")

    constitution = subparsers.add_parser("constitution", help="constitution commands")
    constitution_sub = constitution.add_subparsers(dest="constitution_command", required=True)

    assemble = constitution_sub.add_parser(
        "assemble", help="produce constitution.md + install.lock"
    )
    assemble.add_argument("--llm", choices=["stdio", "file", "none"])
    assemble.add_argument("--accept-merged", type=Path)

    show = constitution_sub.add_parser("show", help="print effective constitution")
    show.add_argument("--no-preface", action="store_true")

    subparsers.add_parser(
        "install",
        help="resolve `.haex-hive.json` atoms and publish a new generation (Spec 008)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, dispatch a command, and render typed refusals."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _check_min_version(args.repo_root)
    except HaexError as exc:
        emit_refuse(exc)
        return exc.exit_code

    try:
        if args.command == "migrate":
            from haex_hive.cli import migrate as migrate_cli

            return migrate_cli.run(args)
        if args.command == "constitution":
            from haex_hive.cli import constitution as constitution_cli

            if args.constitution_command == "assemble":
                return constitution_cli.run_assemble(args)
            if args.constitution_command == "show":
                return constitution_cli.run_show(args)
        if args.command == "install":
            from haex_hive.cli import install as install_cli

            return install_cli.run(args)
    except HaexError as exc:
        emit_refuse(exc)
        return exc.exit_code

    parser.error(f"unknown command: {args.command}")
    return exit_codes.USAGE
