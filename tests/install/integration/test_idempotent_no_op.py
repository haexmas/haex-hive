"""T022 — `haex install` idempotence (US1 MVP, Spec 008 SC-003).

A second invocation with unchanged effective inputs is a no-op: no file
is rewritten, no generation ID is allocated, and the run reports "no
changes". The trust-git amendment's byte-comparison detection replaces
the earlier snapshot-digest scaffolding.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _run_install(repo_root: Path, state_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HAEX_HIVE_STATE"] = str(state_root)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "haex_hive",
            "--repo-root",
            str(repo_root),
            "install",
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_second_install_is_a_no_op(
    single_source_constitution_fixture: dict,
) -> None:
    consumer: Path = single_source_constitution_fixture["consumer"]
    state_root: Path = single_source_constitution_fixture["state_root"]

    first = _run_install(consumer, state_root)
    assert first.returncode == 0, first.stderr
    assert first.stdout.startswith("installed generation g_")

    live = consumer / ".haex-hive"
    constitution_bytes = (live / "constitution.md").read_bytes()
    lock_bytes = (live / "install.lock").read_bytes()
    marker_bytes = (live / "visibility.json").read_bytes()
    stat_before = {
        p.name: p.stat().st_mtime_ns
        for p in (live / "constitution.md", live / "install.lock", live / "visibility.json")
    }

    second = _run_install(consumer, state_root)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "no changes"

    assert (live / "constitution.md").read_bytes() == constitution_bytes
    assert (live / "install.lock").read_bytes() == lock_bytes
    assert (live / "visibility.json").read_bytes() == marker_bytes

    stat_after = {
        p.name: p.stat().st_mtime_ns
        for p in (live / "constitution.md", live / "install.lock", live / "visibility.json")
    }
    assert stat_after == stat_before, "no-op path must not touch on-disk files"
