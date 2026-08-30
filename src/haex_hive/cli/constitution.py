"""`haex constitution {assemble,show}` handlers (stubs; wired later)."""

from __future__ import annotations

import argparse

from haex_hive.cli.diagnostics import emit_refuse
from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError


def _not_wired(command: str) -> int:
    emit_refuse(
        HaexError(
            message=f"haex constitution {command} is not available in this release",
            diagnostic_key="not-implemented",
            exit_code=exit_codes.USAGE,
            hint="Constitution assembly ships in a later phase.",
        )
    )
    return exit_codes.USAGE


def run_assemble(args: argparse.Namespace) -> int:  # noqa: ARG001
    return _not_wired("assemble")


def run_show(args: argparse.Namespace) -> int:  # noqa: ARG001
    return _not_wired("show")
