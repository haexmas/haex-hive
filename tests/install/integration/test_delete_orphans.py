"""T046 — dropping an atom republishes with the reduced atom set (US4).

Under the constitution-only MVP, "atom files" means the merged
constitution body. Dropping one of two constitution-contributing atoms
transitions the install from the multi-source `--accept-merged` path to
the single-source fast path; the resulting `.haex-hive/constitution.md`
is byte-for-byte the remaining atom's contribution and `install.lock`'s
`constitution.sources[]` shrinks to a single entry. Under R1 rename-swap
the whole `.haex-hive/` is replaced atomically, so any file that a
removed atom would have contributed is absent from the new generation by
construction.
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


def _run_haex(
    repo_root: Path,
    *args: str,
    state_root: Path,
) -> subprocess.CompletedProcess:
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
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_dropping_atom_republishes_with_reduced_atom_set(
    multi_source_constitution_fixture: dict, tmp_path: Path
) -> None:
    consumer: Path = multi_source_constitution_fixture["consumer"]
    state_root: Path = multi_source_constitution_fixture["state_root"]
    atom_id_a = multi_source_constitution_fixture["atom_id_a"]
    atom_id_b = multi_source_constitution_fixture["atom_id_b"]

    pending = _run_haex(consumer, "--llm=file", state_root=state_root)
    assert pending.returncode == 5, pending.stderr

    merged = b"# Merged Constitution\n\nBe kind.\nBe bold.\n"
    candidate_path = tmp_path / "merged.md"
    candidate_path.write_bytes(merged)

    first = _run_haex(
        consumer, "--accept-merged", str(candidate_path), state_root=state_root
    )
    assert first.returncode == 0, first.stderr

    live = consumer / ".haex-hive"
    lock_before = json.loads((live / "install.lock").read_text())
    assert sorted(s["id"] for s in lock_before["constitution"]["sources"]) == sorted(
        [atom_id_a, atom_id_b]
    )
    assert (live / "constitution.md").read_bytes() == merged
    generation_id_before = lock_before["visibility_marker"]["generation_id"]

    manifest_path = consumer / ".haex-hive.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["atoms"][0]["includes"] = [atom_id_a]
    manifest_path.write_text(json.dumps(manifest, indent=2))

    second = _run_haex(consumer, state_root=state_root)
    assert second.returncode == 0, second.stderr
    assert second.stdout.startswith("installed generation g_")

    assert (live / "constitution.md").read_bytes() == b"# Constitution A\n\nBe kind.\n"

    lock_after = json.loads((live / "install.lock").read_text())
    assert [s["id"] for s in lock_after["constitution"]["sources"]] == [atom_id_a]
    assert lock_after["visibility_marker"]["generation_id"] != generation_id_before

    marker = json.loads((live / "visibility.json").read_text())
    assert marker["generation_id"] == lock_after["visibility_marker"]["generation_id"]
    assert marker["participating_roots"] == [".haex-hive/"]


def test_second_delete_orphans_is_a_noop(
    multi_source_constitution_fixture: dict, tmp_path: Path
) -> None:
    """After a drop+reinstall converges, a third install is idempotent."""
    consumer: Path = multi_source_constitution_fixture["consumer"]
    state_root: Path = multi_source_constitution_fixture["state_root"]
    atom_id_a = multi_source_constitution_fixture["atom_id_a"]

    pending = _run_haex(consumer, "--llm=file", state_root=state_root)
    assert pending.returncode == 5, pending.stderr
    merged = b"# Merged Constitution\n\nBe kind.\nBe bold.\n"
    candidate_path = tmp_path / "merged.md"
    candidate_path.write_bytes(merged)
    accept = _run_haex(
        consumer, "--accept-merged", str(candidate_path), state_root=state_root
    )
    assert accept.returncode == 0, accept.stderr

    manifest_path = consumer / ".haex-hive.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["atoms"][0]["includes"] = [atom_id_a]
    manifest_path.write_text(json.dumps(manifest, indent=2))

    drop = _run_haex(consumer, state_root=state_root)
    assert drop.returncode == 0, drop.stderr
    lock_after_drop = (consumer / ".haex-hive" / "install.lock").read_bytes()

    idempotent = _run_haex(consumer, state_root=state_root)
    assert idempotent.returncode == 0, idempotent.stderr
    assert idempotent.stdout.strip() == "no changes"
    assert (consumer / ".haex-hive" / "install.lock").read_bytes() == lock_after_drop
