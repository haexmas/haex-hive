"""T060 — unit tests for `ManifestLockContext` (Spec 013)."""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from haex_hive.install.manifest_lock import ManifestLockContext
from haex_hive.util.errors import ManifestLockContendedError


def _hold_lock(lock_path: str, seconds: float, ready_file: str) -> None:
    """Child-process helper: hold the lock for `seconds`, signal via ready_file."""
    lock = ManifestLockContext(Path(lock_path), timeout_seconds=5.0)
    with lock:
        Path(ready_file).write_text("ready")
        time.sleep(seconds)


def test_lock_file_created_if_absent(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive.json.lock"
    assert not lock_path.exists()
    with ManifestLockContext(lock_path, timeout_seconds=1.0):
        assert lock_path.exists()
    assert lock_path.exists()  # NEVER deleted


def test_lock_file_not_renamed_or_deleted_on_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive.json.lock"
    lock_path.write_bytes(b"pre-existing")
    with ManifestLockContext(lock_path, timeout_seconds=1.0):
        pass
    assert lock_path.exists()
    assert lock_path.read_bytes() == b"pre-existing"


def test_bounded_wait_succeeds_when_lock_frees_in_time(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive.json.lock"
    ready = tmp_path / "ready"

    ctx = multiprocessing.get_context("spawn")
    child = ctx.Process(target=_hold_lock, args=(str(lock_path), 0.5, str(ready)))
    child.start()
    try:
        while not ready.exists():
            time.sleep(0.02)
        with ManifestLockContext(lock_path, timeout_seconds=5.0):
            pass
    finally:
        child.join(timeout=5)


def test_contention_after_timeout_refuses(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive.json.lock"
    ready = tmp_path / "ready"

    ctx = multiprocessing.get_context("spawn")
    child = ctx.Process(target=_hold_lock, args=(str(lock_path), 3.0, str(ready)))
    child.start()
    try:
        while not ready.exists():
            time.sleep(0.02)
        with (
            pytest.raises(ManifestLockContendedError) as exc_info,
            ManifestLockContext(lock_path, timeout_seconds=0.2),
        ):
            pass
        assert "lock_path" in exc_info.value.context
    finally:
        child.join(timeout=5)


def test_fail_fast_with_zero_timeout(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive.json.lock"
    ready = tmp_path / "ready"

    ctx = multiprocessing.get_context("spawn")
    child = ctx.Process(target=_hold_lock, args=(str(lock_path), 2.0, str(ready)))
    child.start()
    try:
        while not ready.exists():
            time.sleep(0.02)
        start = time.monotonic()
        with (
            pytest.raises(ManifestLockContendedError),
            ManifestLockContext(lock_path, timeout_seconds=0.0),
        ):
            pass
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"fail-fast took {elapsed}s (expected near-zero)"
    finally:
        child.join(timeout=5)


def test_nested_acquisition_reuses_context(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive.json.lock"
    lock = ManifestLockContext(lock_path, timeout_seconds=1.0)
    with lock:
        # Re-entering the SAME context object must not try to re-acquire.
        with lock:
            with lock:
                assert lock._depth == 3
            assert lock._depth == 2
        assert lock._depth == 1
    assert lock._depth == 0
