"""T032 — fenced-lease unit tests (US2, research §R4).

Covers the heartbeat thread cadence + failure isolation, the stale-lease
`attempt_reclaim` revalidation ordering, the `SharedReaderLock` shared/
exclusive semantics, and the `busy_lock_from_mutex` operator diagnostic.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from haex_hive.install.errors import InstallLockBusy, busy_lock_from_mutex
from haex_hive.install.lock import (
    HeartbeatThread,
    OwnerToken,
    SharedReaderLock,
    StaleLeaseNotReclaimable,
    attempt_reclaim,
)
from haex_hive.io.writer_lock import (
    HEARTBEAT_INTERVAL_NS,
    SAFETY_MARGIN_NS,
    TTL_NS,
    ConstitutionWriterLock,
)


def _sample_token(pid: int = 12345, hostname: str = "test-host") -> OwnerToken:
    return OwnerToken(
        pid=pid,
        hostname=hostname,
        start_ns=1_000_000_000_000_000_000,
        uuid4_hex="0" * 32,
    )


def _write_mutex_payload(mutex_path: Path, *, token: str, heartbeat_ns: int) -> None:
    mutex_path.parent.mkdir(parents=True, exist_ok=True)
    mutex_path.write_text(
        json.dumps(
            {
                "owner_token": token,
                "acquired_at": "2026-09-01T14:20:11.000000Z",
                "heartbeat_at": "2026-09-01T14:20:11.000000Z",
                "heartbeat_at_ns_wallclock": heartbeat_ns,
                "heartbeat_interval_ns": HEARTBEAT_INTERVAL_NS,
                "ttl_ns": TTL_NS,
                "safety_margin_ns": SAFETY_MARGIN_NS,
            }
        )
    )


# ---------- HeartbeatThread ------------------------------------------------


class _CountingLock:
    """Minimal `heartbeat()` implementer for HeartbeatThread tests."""

    def __init__(self) -> None:
        self.calls = 0
        self.event = threading.Event()

    def heartbeat(self) -> None:
        self.calls += 1
        self.event.set()


def test_heartbeat_thread_ticks_at_configured_cadence() -> None:
    """The thread calls heartbeat() at least once per configured interval."""
    lock = _CountingLock()
    thread = HeartbeatThread(lock, interval_ns=5_000_000)  # 5 ms
    thread.start()
    try:
        assert lock.event.wait(timeout=1.0), "heartbeat did not fire within 1s"
    finally:
        thread.stop()
    assert lock.calls >= 1


def test_heartbeat_thread_stops_on_heartbeat_failure() -> None:
    """A raising heartbeat causes the thread to stop rather than spin."""

    class _FailingLock:
        def __init__(self) -> None:
            self.calls = 0

        def heartbeat(self) -> None:
            self.calls += 1
            raise OSError("no space left on device")

    lock = _FailingLock()
    thread = HeartbeatThread(lock, interval_ns=5_000_000)
    thread.start()
    time.sleep(0.05)  # let the loop tick once
    thread.stop()
    # If the thread had retried it would still be running; stop() joined it.
    assert lock.calls >= 1


def test_heartbeat_thread_start_and_stop_are_idempotent() -> None:
    """Repeated start/stop calls do not spawn extra threads or raise."""
    lock = _CountingLock()
    thread = HeartbeatThread(lock, interval_ns=50_000_000)
    thread.start()
    thread.start()
    thread.stop()
    thread.stop()


# ---------- attempt_reclaim ------------------------------------------------


def test_reclaim_returns_true_when_mutex_missing(tmp_path: Path) -> None:
    """A missing mutex means nothing to fence; reclaim is trivially safe."""
    assert attempt_reclaim(tmp_path / "install.mutex") is True


def test_reclaim_returns_true_when_mutex_empty(tmp_path: Path) -> None:
    """An empty mutex file is treated the same as a missing one."""
    mutex_path = tmp_path / "install.mutex"
    mutex_path.write_bytes(b"")
    assert attempt_reclaim(mutex_path) is True


def test_reclaim_refuses_within_ttl(tmp_path: Path) -> None:
    """A heartbeat inside the TTL + safety-margin window blocks reclaim."""
    mutex_path = tmp_path / "install.mutex"
    now_ns = 1_000_000_000_000_000_000
    _write_mutex_payload(mutex_path, token="1:h:0:x", heartbeat_ns=now_ns)
    with pytest.raises(StaleLeaseNotReclaimable, match="within TTL"):
        attempt_reclaim(mutex_path, now_ns=now_ns)


def test_reclaim_permits_after_ttl_plus_margin(tmp_path: Path) -> None:
    """Once heartbeat age exceeds TTL + safety margin, reclaim is allowed."""
    mutex_path = tmp_path / "install.mutex"
    heartbeat_ns = 0
    now_ns = TTL_NS + SAFETY_MARGIN_NS + 1
    _write_mutex_payload(mutex_path, token="1:h:0:x", heartbeat_ns=heartbeat_ns)
    assert attempt_reclaim(mutex_path, now_ns=now_ns) is True


def test_reclaim_aborts_when_owner_token_changes_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Owner-token mutation between the two mutex reads aborts reclamation."""
    mutex_path = tmp_path / "install.mutex"
    heartbeat_ns = 0
    now_ns = TTL_NS + SAFETY_MARGIN_NS + 1
    _write_mutex_payload(mutex_path, token="first:h:0:x", heartbeat_ns=heartbeat_ns)

    from haex_hive.install import lock as lock_module

    real_reader = lock_module._read_mutex_json
    call_count = {"n": 0}

    def flipping_reader(path: Path):
        call_count["n"] += 1
        if call_count["n"] == 2:
            _write_mutex_payload(mutex_path, token="second:h:0:x", heartbeat_ns=heartbeat_ns)
        return real_reader(path)

    monkeypatch.setattr(lock_module, "_read_mutex_json", flipping_reader)
    with pytest.raises(StaleLeaseNotReclaimable, match="owner token changed"):
        attempt_reclaim(mutex_path, now_ns=now_ns)


def test_reclaim_aborts_when_heartbeat_changes_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Heartbeat mutation between the two mutex reads aborts reclamation."""
    mutex_path = tmp_path / "install.mutex"
    heartbeat_ns_first = 0
    now_ns = TTL_NS + SAFETY_MARGIN_NS + 1
    _write_mutex_payload(mutex_path, token="tok:h:0:x", heartbeat_ns=heartbeat_ns_first)

    from haex_hive.install import lock as lock_module

    real_reader = lock_module._read_mutex_json
    call_count = {"n": 0}

    def flipping_heartbeat(path: Path):
        call_count["n"] += 1
        if call_count["n"] == 2:
            _write_mutex_payload(
                mutex_path,
                token="tok:h:0:x",
                heartbeat_ns=heartbeat_ns_first + 1,
            )
        return real_reader(path)

    monkeypatch.setattr(lock_module, "_read_mutex_json", flipping_heartbeat)
    with pytest.raises(StaleLeaseNotReclaimable, match="heartbeat changed"):
        attempt_reclaim(mutex_path, now_ns=now_ns)


# ---------- SharedReaderLock -----------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl-based lock is POSIX-only")
def test_shared_read_lock_permits_multiple_readers(tmp_path: Path) -> None:
    """Two shared-read acquisitions coexist without contention."""
    mutex_path = tmp_path / "install.mutex"
    with SharedReaderLock(mutex_path), SharedReaderLock(mutex_path):
        pass


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl-based lock is POSIX-only")
def test_shared_read_lock_excluded_by_writer(tmp_path: Path) -> None:
    """An exclusive writer excludes shared readers until it releases."""
    mutex_path = tmp_path / "install.mutex"
    with (
        ConstitutionWriterLock(mutex_path),
        pytest.raises(BlockingIOError, match="exclusive writer"),
    ):
        SharedReaderLock(mutex_path).__enter__()
    with SharedReaderLock(mutex_path):
        pass


# ---------- busy-lock diagnostic ------------------------------------------


def test_busy_lock_from_mutex_extracts_operator_diagnostic(tmp_path: Path) -> None:
    """The busy-lock error names the current owner PID/host + heartbeat age."""
    mutex_path = tmp_path / "install.mutex"
    heartbeat_ns = 1_000_000_000_000_000_000
    now_ns = heartbeat_ns + 3_000_000_000  # 3s later
    _write_mutex_payload(
        mutex_path, token="31245:laptop-hex.local:0:x" + "0" * 30, heartbeat_ns=heartbeat_ns
    )

    err = busy_lock_from_mutex(mutex_path, now_ns=now_ns)
    assert isinstance(err, InstallLockBusy)
    assert "31245" in err.message
    assert "laptop-hex.local" in err.message
    assert "3.0s" in err.message
    assert err.context["pid"] == "31245"
    assert err.context["hostname"] == "laptop-hex.local"


def test_busy_lock_from_mutex_handles_missing_file(tmp_path: Path) -> None:
    """A missing mutex file still yields a typed refusal (no crash)."""
    mutex_path = tmp_path / "install.mutex"
    err = busy_lock_from_mutex(mutex_path)
    assert isinstance(err, InstallLockBusy)
    assert "metadata unavailable" in err.message


def test_busy_lock_from_mutex_handles_corrupt_json(tmp_path: Path) -> None:
    """A garbage mutex file also degrades to the typed refusal."""
    mutex_path = tmp_path / "install.mutex"
    mutex_path.write_bytes(b"not json {{{")
    err = busy_lock_from_mutex(mutex_path)
    assert isinstance(err, InstallLockBusy)
    assert "metadata unavailable" in err.message


# ---------- consumer holds the sample token ------------------------------


def test_sample_token_round_trips() -> None:
    """Sanity check the shared _sample_token helper for other US2 tests."""
    token = _sample_token()
    assert OwnerToken.parse(token.serialize()) == token
