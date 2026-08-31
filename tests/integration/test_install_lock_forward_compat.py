"""T052 — install.lock forward-compat (FR-030): unknown top-level fields survive assemble."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _run_haex(repo_root: Path, *args: str, state_root: Path) -> subprocess.CompletedProcess:
    """Run the haex CLI against an isolated repository and state root."""
    env = os.environ.copy()
    env["HAEX_HIVE_STATE"] = str(state_root)
    return subprocess.run(
        [sys.executable, "-m", "haex_hive", "--repo-root", str(repo_root),
         "constitution", "assemble", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_unknown_atoms_field_survives_assemble(single_source_constitution_fixture: dict) -> None:
    """Preserve a future install-lock field during constitution assembly."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    hive_dir = consumer / ".haex-hive"
    hive_dir.mkdir()
    marker_payload = {"id": "com.github.future.spec.atom", "revision": "0" * 40}
    (hive_dir / "install.lock").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "generated_by": "haex 0.0.0",
                "unknown_future_top_level_field": marker_payload,
            }
        )
    )

    proc = _run_haex(consumer, state_root=state_root)
    assert proc.returncode == 0, proc.stderr

    lock_data = json.loads((hive_dir / "install.lock").read_text())
    assert lock_data["unknown_future_top_level_field"] == marker_payload
    expected_atom_id = single_source_constitution_fixture["atom_id"]
    assert lock_data["constitution"]["sources"][0]["id"] == expected_atom_id
    assert lock_data["generated_by"].startswith("haex ")
