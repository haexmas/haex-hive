"""Exclusive advisory lock and fenced-lease owner token (FR-001, FR-010).

Provides the `OwnerToken` value object per Spec 008 research §R4 plus the
fenced-lease `HeartbeatThread` (T034), the stale-lease `attempt_reclaim`
protocol (T034), and the `SharedReaderLock` shared-read primitive (T035).

The `ConstitutionWriterLock` low-level exclusive lock + `install.mutex`
metadata layer lives in `haex_hive.io.writer_lock`; this module composes
those primitives with the R4 heartbeat cadence and reclaim ordering.
"""

from __future__ import annotations

import errno
import json
import os
import re
import socket
import sys
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

_HOSTNAME_RE = re.compile(r"[A-Za-z0-9.-]+")
_HOSTNAME_SHAPE_RE = re.compile(r"\A[A-Za-z0-9.-]{1,64}\Z")
_UUID4_HEX_RE = re.compile(r"\A[0-9a-f]{32}\Z")
_MAX_TOKEN_BYTES = 128


@dataclass(frozen=True)
class OwnerToken:
    """Runtime shape of the fenced-lease owner token.

    Serialised form is `<pid>:<hostname>:<start_ns>:<uuid4_hex>`, ASCII-safe,
    at most 128 bytes. Hostnames outside `[A-Za-z0-9.-]{1,64}` are refused;
    call `OwnerToken.emit(...)` to construct one from raw system values and
    have the sanitisation applied consistently.
    """

    pid: int
    hostname: str
    start_ns: int
    uuid4_hex: str

    def __post_init__(self) -> None:
        if self.pid < 1 or self.pid > 0xFFFFFFFF:
            raise ValueError(f"pid out of range: {self.pid}")
        if not _HOSTNAME_SHAPE_RE.match(self.hostname):
            raise ValueError(f"hostname does not match [A-Za-z0-9.-]{{1,64}}: {self.hostname!r}")
        if self.start_ns < 0:
            raise ValueError(f"start_ns must be non-negative: {self.start_ns}")
        if not _UUID4_HEX_RE.match(self.uuid4_hex):
            raise ValueError(f"uuid4_hex must be 32 lowercase hex chars: {self.uuid4_hex!r}")

    def serialize(self) -> str:
        token = f"{self.pid}:{self.hostname}:{self.start_ns}:{self.uuid4_hex}"
        if len(token.encode("utf-8")) > _MAX_TOKEN_BYTES:
            raise ValueError(f"serialised token exceeds {_MAX_TOKEN_BYTES} bytes: {len(token)}")
        return token

    @classmethod
    def parse(cls, raw: str) -> OwnerToken:
        if len(raw.encode("utf-8")) > _MAX_TOKEN_BYTES:
            raise ValueError(f"token exceeds {_MAX_TOKEN_BYTES} bytes")
        parts = raw.split(":")
        if len(parts) != 4:
            raise ValueError(f"expected 4 colon-separated fields, got {len(parts)}")
        pid_str, hostname, start_ns_str, uuid4_hex = parts
        try:
            pid = int(pid_str)
            start_ns = int(start_ns_str)
        except ValueError as exc:
            raise ValueError(f"pid and start_ns must be decimal integers: {exc}") from None
        return cls(pid=pid, hostname=hostname, start_ns=start_ns, uuid4_hex=uuid4_hex)

    @classmethod
    def emit(
        cls,
        *,
        pid: int | None = None,
        hostname: str | None = None,
        start_ns: int | None = None,
    ) -> OwnerToken:
        """Build a fresh token from live system values or explicit overrides.

        Overrides exist for tests; production callers pass nothing and pick up
        `os.getpid()`, `socket.gethostname()`, `time.monotonic_ns()`, and a
        fresh UUID4. Hostnames are sanitised per contract: non-matching chars
        are dropped, the result truncated to 64 chars, and an empty result
        falls back to the literal `"unknown"`.
        """
        actual_pid = os.getpid() if pid is None else pid
        raw_hostname = socket.gethostname() if hostname is None else hostname
        actual_start_ns = time.monotonic_ns() if start_ns is None else start_ns
        sanitised = "".join(_HOSTNAME_RE.findall(raw_hostname))[:64] or "unknown"
        return cls(
            pid=actual_pid,
            hostname=sanitised,
            start_ns=actual_start_ns,
            uuid4_hex=uuid.uuid4().hex,
        )


class HeartbeatThread:
    """Background thread that refreshes an `install.mutex` lease.

    Consumes the `heartbeat()` primitive on any object implementing it
    (`haex_hive.io.writer_lock.ConstitutionWriterLock` today). The thread
    runs as a daemon so it terminates automatically if the main process
    exits without calling `stop()`. On heartbeat failure (disk full,
    fsync error) the thread stops rather than retrying — the lease will
    then expire naturally and can be reclaimed by the next install.

    `start()` and `stop()` are idempotent. `stop()` blocks up to
    `join_timeout_s` for the thread to exit; if the timeout is
    exceeded, the thread is left running as a daemon.
    """

    def __init__(
        self,
        lock: Any,
        *,
        interval_ns: int = 5_000_000_000,
        join_timeout_s: float = 2.0,
    ) -> None:
        self._lock = lock
        self._interval_s = interval_ns / 1_000_000_000
        self._join_timeout_s = join_timeout_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=self._join_timeout_s)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._interval_s):
            try:
                self._lock.heartbeat()
            except BaseException:
                self._stop_event.set()
                return


_HEARTBEAT_INTERVAL_NS = 5_000_000_000
_TTL_NS = 60_000_000_000
_SAFETY_MARGIN_NS = 5_000_000_000


class StaleLeaseNotReclaimable(RuntimeError):
    """Raised when the stale-lease revalidation refuses to reclaim."""


def attempt_reclaim(
    mutex_path: Path,
    *,
    ttl_ns: int = _TTL_NS,
    safety_margin_ns: int = _SAFETY_MARGIN_NS,
    now_ns: int | None = None,
) -> bool:
    """Decide whether an on-disk `install.mutex` payload is stale-reclaimable.

    Read the mutex file, require the wall-clock heartbeat to be older than
    `ttl_ns + safety_margin_ns`, re-read under the same handle, and require
    the token and heartbeat to be unchanged between the two reads. Returns
    `True` when reclamation is authorised. Raises `StaleLeaseNotReclaimable`
    on any revalidation failure so callers can distinguish "safe to reclaim"
    from "keep waiting".

    Callers MUST already hold the exclusive OS lock on `mutex_path` before
    calling this; the revalidation only guards against payload mutation
    between the two reads, not against a live owner still holding the OS
    lock. If the initial non-blocking OS-lock acquisition already succeeded,
    the previous owner has released or died and reclaim is safe by that
    signal alone — the revalidation is defence-in-depth per FR-010.
    """
    check_ns = time.time_ns() if now_ns is None else now_ns
    first = _read_mutex_json(mutex_path)
    if first is None:
        return True
    heartbeat_ns_first = _extract_heartbeat_ns(first)
    if heartbeat_ns_first is None:
        return True
    if check_ns - heartbeat_ns_first <= ttl_ns + safety_margin_ns:
        raise StaleLeaseNotReclaimable("lease is still within TTL + safety margin")
    second = _read_mutex_json(mutex_path)
    if second is None:
        raise StaleLeaseNotReclaimable("lease disappeared between reads")
    if first.get("owner_token") != second.get("owner_token"):
        raise StaleLeaseNotReclaimable("owner token changed between reads")
    if _extract_heartbeat_ns(second) != heartbeat_ns_first:
        raise StaleLeaseNotReclaimable("heartbeat changed between reads")
    return True


def _read_mutex_json(mutex_path: Path) -> dict[str, Any] | None:
    try:
        raw = mutex_path.read_bytes()
    except OSError:
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _extract_heartbeat_ns(record: dict[str, Any]) -> int | None:
    value = record.get("heartbeat_at_ns_wallclock")
    return value if isinstance(value, int) else None


_IS_WINDOWS = sys.platform == "win32"
_ERROR_LOCK_VIOLATION = 33
_WINDOWS_LOCK_OFFSET = 0x7FFF_FFFF
_WINDOWS_LOCK_LENGTH = 1


class SharedReaderLock:
    """Non-blocking shared-read lock over the same `install.mutex` path.

    Multiple readers coexist under this lock; an exclusive writer is
    excluded until every reader has released. Raises `BlockingIOError`
    when a writer already holds the exclusive lock; the caller decides
    whether to wait or refuse.

    Windows uses `LockFileEx` **without** `LOCKFILE_EXCLUSIVE_LOCK`,
    scoped to the same sentinel byte the exclusive lock uses so multi-
    reader/single-writer semantics land consistently across platforms.
    """

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: int | None = None
        self._handle = None

    def __enter__(self) -> SharedReaderLock:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        if _IS_WINDOWS:
            self._acquire_windows()
        else:
            self._acquire_posix()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if _IS_WINDOWS:
            self._release_windows()
        else:
            self._release_posix()

    def _acquire_posix(self) -> None:
        import fcntl

        fd = os.open(str(self._lock_path), os.O_RDONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise BlockingIOError("install.mutex is held by an exclusive writer") from None
            raise
        self._fd = fd

    def _release_posix(self) -> None:
        import fcntl

        if self._fd is None:
            return
        with suppress(OSError):
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

    def _acquire_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = wintypes.HANDLE
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x1
        FILE_SHARE_WRITE = 0x2
        OPEN_ALWAYS = 4
        FILE_ATTRIBUTE_NORMAL = 0x80

        handle = kernel32.CreateFileW(
            ctypes.c_wchar_p(str(self._lock_path)),
            wintypes.DWORD(GENERIC_READ),
            wintypes.DWORD(FILE_SHARE_READ | FILE_SHARE_WRITE),
            None,
            wintypes.DWORD(OPEN_ALWAYS),
            wintypes.DWORD(FILE_ATTRIBUTE_NORMAL),
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError()

        LOCKFILE_FAIL_IMMEDIATELY = 0x1

        class OVERLAPPED(ctypes.Structure):
            _fields_ = [
                ("Internal", ctypes.c_void_p),
                ("InternalHigh", ctypes.c_void_p),
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE),
            ]

        overlapped = OVERLAPPED()
        overlapped.Offset = _WINDOWS_LOCK_OFFSET
        overlapped.OffsetHigh = 0
        result = kernel32.LockFileEx(
            wintypes.HANDLE(handle),
            wintypes.DWORD(LOCKFILE_FAIL_IMMEDIATELY),
            wintypes.DWORD(0),
            wintypes.DWORD(_WINDOWS_LOCK_LENGTH),
            wintypes.DWORD(0),
            ctypes.byref(overlapped),
        )
        if not result:
            last_error = ctypes.GetLastError()
            kernel32.CloseHandle(wintypes.HANDLE(handle))
            if last_error == _ERROR_LOCK_VIOLATION:
                raise BlockingIOError("install.mutex is held by an exclusive writer")
            raise ctypes.WinError(last_error)
        self._handle = handle

    def _release_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        if self._handle is None:
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.CloseHandle(wintypes.HANDLE(self._handle))
        self._handle = None
