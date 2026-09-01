"""T067 — SC-008 crash-safety sweep across rename-swap boundaries.

Each child is terminated at a real in-flight boundary, then a subsequent
`haex constitution assemble` resolves the directory-name state and converges
to a fully-successful generation.

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
            "constitution",
            "assemble",
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

    recovered = _run(consumer, state_root)
    assert recovered.returncode == 0, recovered.stderr.decode()
    assert not next_dir.exists()
    assert not prev_dir.exists()

    constitution = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    lock_bytes = (consumer / ".haex-hive" / "install.lock").read_bytes()
    lock_data = json.loads(lock_bytes)
    assert lock_data["constitution"]["content_integrity"].startswith("sha256-")

    again = _run(consumer, state_root)
    assert again.returncode == 0, again.stderr.decode()
    assert (consumer / ".haex-hive" / "constitution.md").read_bytes() == constitution
    assert (consumer / ".haex-hive" / "install.lock").read_bytes() == lock_bytes
