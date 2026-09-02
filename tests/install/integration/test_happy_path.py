"""T021 — `haex install` happy path (US1 MVP, Spec 008).

A single-source constitution atom lands under `.haex-hive/` as three files
(constitution.md, install.lock, visibility.json) published atomically by
the rename-swap primitive. The lock records the atom's `(id, source,
revision, contributed_paths)` and the marker's `generation_id` matches the
lock's cross-reference.
"""

from __future__ import annotations

import json
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


def test_happy_path_single_source_publishes_all_three_files(
    single_source_constitution_fixture: dict,
) -> None:
    consumer: Path = single_source_constitution_fixture["consumer"]
    state_root: Path = single_source_constitution_fixture["state_root"]
    atom_id = single_source_constitution_fixture["atom_id"]
    commit_sha = single_source_constitution_fixture["commit_sha"]
    canonical = single_source_constitution_fixture["canonical"]

    proc = _run_install(consumer, state_root)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("installed generation g_")

    live = consumer / ".haex-hive"
    constitution = live / "constitution.md"
    lock_path = live / "install.lock"
    marker_path = live / "visibility.json"

    assert constitution.read_bytes() == b"# Example Constitution\n\nBe kind.\n"

    lock = json.loads(lock_path.read_text())
    assert lock["haex_hive_version"] == "2"
    assert lock["constitution"]["sources"] == [
        {"id": atom_id, "revision": commit_sha, "source": canonical}
    ]
    assert "content_integrity" not in lock["constitution"]
    assert lock["participating_roots"] == [".haex-hive/"]

    marker = json.loads(marker_path.read_text())
    assert marker["haex_hive_version"] == "2"
    assert marker["participating_roots"] == [".haex-hive/"]
    assert marker["generation_id"] == lock["visibility_marker"]["generation_id"]
    assert proc.stdout.strip().endswith(marker["generation_id"])
