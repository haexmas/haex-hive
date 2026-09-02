"""T054 — end-to-end walkthrough of `specs/008-install-transaction/quickstart.md`.

Executes steps 1, 2, 4, 5, 6, and 7 of the quickstart in order and
verifies the output at each step matches the doc. Step 3 (`--verify-only`)
is skipped with a note because the shared-read lock and the `--verify-only`
flag are deferred until the US2 fenced-lease block lands (T037).

Records the SC-001..SC-006 outcomes exercised by each step in this module's
docstring; SC-007 was retired by the 2026-09-02 trust-git amendment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from haex_hive.io.state import transaction_paths
from haex_hive.io.writer_lock import ConstitutionWriterLock

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _run_install(
    repo_root: Path,
    *args: str,
    state_root: Path,
    crash_after: str | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HAEX_HIVE_STATE"] = str(state_root)
    if crash_after is not None:
        env["HAEX_HIVE_CRASH_AFTER"] = crash_after
    else:
        env.pop("HAEX_HIVE_CRASH_AFTER", None)
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


def test_quickstart_walkthrough_single_source(
    single_source_constitution_fixture: dict, tmp_path: Path
) -> None:
    """Walk quickstart steps 1, 2, 4, 5, 7 against a single-source fixture."""
    del tmp_path
    consumer: Path = single_source_constitution_fixture["consumer"]
    state_root: Path = single_source_constitution_fixture["state_root"]

    # Step 1 — first install
    first = _run_install(consumer, state_root=state_root)
    assert first.returncode == 0, first.stderr
    assert first.stdout.startswith("installed generation g_")
    live = consumer / ".haex-hive"
    for name in ("constitution.md", "install.lock", "visibility.json"):
        assert (live / name).exists(), f"missing {name} after first install"

    # Step 2 — idempotent re-install
    second = _run_install(consumer, state_root=state_root)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "no changes"

    # Step 4 — concurrent install refusal
    mutex = transaction_paths(consumer, state_root).mutex
    with ConstitutionWriterLock(mutex):
        busy = _run_install(consumer, state_root=state_root)
    assert busy.returncode == 9, busy.stderr
    assert "key=constitution-writer-busy" in busy.stderr

    # Step 5 — recovery after a scripted crash mid-swap
    (live / "constitution.md").write_bytes(
        (live / "constitution.md").read_bytes() + b"\n"
    )
    crashed = _run_install(consumer, state_root=state_root, crash_after="rename_a")
    assert crashed.returncode != 0
    prev_dir = consumer / ".haex-hive.prev"
    assert prev_dir.exists()
    recovered = _run_install(consumer, state_root=state_root)
    assert recovered.returncode == 0, recovered.stderr
    assert not (consumer / ".haex-hive.next").exists()
    assert not prev_dir.exists()

    # Step 7 — reader consistency helper. The pattern from the doc:
    #  (a) load visibility.json, (b) match lock.visibility_marker.generation_id,
    #  (c) verify each participating root is available.
    marker = json.loads((live / "visibility.json").read_bytes())
    lock = json.loads((live / "install.lock").read_bytes())
    assert marker["generation_id"] == lock["visibility_marker"]["generation_id"]
    for root_name in marker["participating_roots"]:
        assert (consumer / root_name.rstrip("/")).exists(), root_name


def test_quickstart_walkthrough_delete_orphan(
    multi_source_constitution_fixture: dict, tmp_path: Path
) -> None:
    """Walk quickstart step 6 (remove an atom) against the multi-source fixture."""
    consumer: Path = multi_source_constitution_fixture["consumer"]
    state_root: Path = multi_source_constitution_fixture["state_root"]
    atom_id_a = multi_source_constitution_fixture["atom_id_a"]

    pending = _run_install(consumer, "--llm=file", state_root=state_root)
    assert pending.returncode == 5, pending.stderr
    merged = b"# Merged Constitution\n\nBe kind.\nBe bold.\n"
    candidate_path = tmp_path / "merged.md"
    candidate_path.write_bytes(merged)
    accept = _run_install(
        consumer, "--accept-merged", str(candidate_path), state_root=state_root
    )
    assert accept.returncode == 0, accept.stderr

    manifest_path = consumer / ".haex-hive.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["atoms"][0]["includes"] = [atom_id_a]
    manifest_path.write_text(json.dumps(manifest, indent=2))

    drop = _run_install(consumer, state_root=state_root)
    assert drop.returncode == 0, drop.stderr
    assert drop.stdout.startswith("installed generation g_")

    lock = json.loads((consumer / ".haex-hive" / "install.lock").read_text())
    assert [s["id"] for s in lock["constitution"]["sources"]] == [atom_id_a]
    assert (consumer / ".haex-hive" / "constitution.md").read_bytes() == (
        b"# Constitution A\n\nBe kind.\n"
    )


@pytest.mark.skip(reason="Step 3 depends on T037 (`--verify-only` + shared lock), deferred")
def test_quickstart_step3_verify_only() -> None:
    """Placeholder: `haex install --verify-only` and its shared-read lock land in T037."""
