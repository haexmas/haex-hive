"""SC-001 crash-safety sweep across rename-swap boundaries.

Each child is terminated at a real in-flight boundary, then a subsequent
`haex install` cleans any leftover `<root>.next/` / `<root>.prev/` siblings
and either reinstalls from scratch (pre-rename-B crash) or takes the
idempotent no-op path (post-rename-B crash) — the 2026-09-02 detect+retry
model that replaced the earlier 8-state recovery-forward dispatcher.

Uses the `HAEX_HIVE_CRASH_AFTER` test seam in `haex_hive.io.transaction` to
terminate the child process (SIGKILL on POSIX, TerminateProcess-equivalent on
Windows) at each rename-swap boundary rather than racing an external timer
against the write.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from haex_hive.migrate.transform import clone_dir

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("git") is None, reason="git binary required"),
]

_CRASH_CASES = [
    ("pre_swap", True),
    ("rename_a", True),
    ("rename_b", False),
    ("rename_b", True),
]


def _run(
    consumer: Path, state_root: Path, *, crash_after: str | None = None
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
            str(consumer),
            "install",
        ],
        capture_output=True,
        env=env,
    )


@pytest.mark.parametrize(
    "crash_point,preexisting",
    _CRASH_CASES,
    ids=[f"{point}-{'existing' if existing else 'absent'}" for point, existing in _CRASH_CASES],
)
def test_crash_at_boundary_converges_on_retry(
    single_source_constitution_fixture: dict, crash_point: str, preexisting: bool
) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    if preexisting:
        clean = _run(consumer, state_root)
        assert clean.returncode == 0, clean.stderr.decode()
        # Make the next install publish a generation instead of taking the
        # single-source idempotence fast path.
        constitution_path = consumer / ".haex-hive" / "constitution.md"
        constitution_path.write_bytes(constitution_path.read_bytes() + b"\n")

    crashed = _run(consumer, state_root, crash_after=crash_point)
    assert crashed.returncode != 0, "the child process must not exit cleanly when killed"

    live = consumer / ".haex-hive"
    next_dir = consumer / ".haex-hive.next"
    prev_dir = consumer / ".haex-hive.prev"
    if crash_point == "pre_swap":
        assert live.exists()
        assert next_dir.exists()
        assert not prev_dir.exists()
    elif crash_point == "rename_a":
        assert next_dir.exists()
        assert not live.exists()
        assert prev_dir.exists()
    else:
        assert live.exists()
        if preexisting:
            assert prev_dir.exists()
        else:
            assert not prev_dir.exists()
        assert not next_dir.exists()

    if crash_point == "rename_a" and preexisting:
        previous_generation = (prev_dir / "constitution.md").read_bytes()
        clone = clone_dir(state_root, single_source_constitution_fixture["canonical"])
        shutil.rmtree(clone)

        failed_retry = _run(consumer, state_root)

        assert failed_retry.returncode != 0
        assert not live.exists()
        assert not next_dir.exists()
        assert prev_dir.exists()
        assert (prev_dir / "constitution.md").read_bytes() == previous_generation

        shutil.copytree(single_source_constitution_fixture["publisher"], clone)

    recovered = _run(consumer, state_root)
    assert recovered.returncode == 0, recovered.stderr.decode()
    assert not next_dir.exists()
    assert not prev_dir.exists()

    constitution = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    lock_data_1 = json.loads((consumer / ".haex-hive" / "install.lock").read_bytes())
    again = _run(consumer, state_root)
    assert again.returncode == 0, again.stderr.decode()
    assert (consumer / ".haex-hive" / "constitution.md").read_bytes() == constitution
    lock_data_2 = json.loads((consumer / ".haex-hive" / "install.lock").read_bytes())
    assert (
        lock_data_1["visibility_marker"]["generation_id"]
        == lock_data_2["visibility_marker"]["generation_id"]
    )
    lock_data_1["visibility_marker"]["generation_id"] = None
    lock_data_2["visibility_marker"]["generation_id"] = None
    assert lock_data_1 == lock_data_2
