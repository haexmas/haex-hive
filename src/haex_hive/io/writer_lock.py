"""Exclusive constitution-writer lock (R6, FR-035).

POSIX: `fcntl.flock(LOCK_EX | LOCK_NB)`.
Windows: `LockFileEx(LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY)`.

On contention, `ConstitutionWriterBusyError` is raised without ever touching
the journal or its targets. POSIX contention indicator is
`OSError.errno == errno.EWOULDBLOCK` (aliased to `EAGAIN` on some platforms);
the Windows indicator is `GetLastError() == ERROR_LOCK_VIOLATION` (33). Any
other error is re-raised untouched.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path
from types import TracebackType

from haex_hive.util.errors import ConstitutionWriterBusyError

_IS_WINDOWS = sys.platform == "win32"

_ERROR_LOCK_VIOLATION = 33


class ConstitutionWriterLock:
    """Non-blocking exclusive-writer lock over a file handle."""

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: int | None = None
        self._handle = None

    def __enter__(self) -> ConstitutionWriterLock:
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

        fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            os.close(fd)
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise ConstitutionWriterBusyError(
                    message="another `haex constitution assemble` is running"
                ) from None
            raise
        self._fd = fd

    def _release_posix(self) -> None:
        import fcntl

        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def _acquire_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = wintypes.HANDLE
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x1
        FILE_SHARE_WRITE = 0x2
        OPEN_ALWAYS = 4
        FILE_ATTRIBUTE_NORMAL = 0x80

        handle = kernel32.CreateFileW(
            ctypes.c_wchar_p(str(self._lock_path)),
            wintypes.DWORD(GENERIC_READ | GENERIC_WRITE),
            wintypes.DWORD(FILE_SHARE_READ | FILE_SHARE_WRITE),
            None,
            wintypes.DWORD(OPEN_ALWAYS),
            wintypes.DWORD(FILE_ATTRIBUTE_NORMAL),
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError()

        LOCKFILE_EXCLUSIVE_LOCK = 0x2
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
        result = kernel32.LockFileEx(
            wintypes.HANDLE(handle),
            wintypes.DWORD(LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY),
            wintypes.DWORD(0),
            wintypes.DWORD(0xFFFFFFFF),
            wintypes.DWORD(0xFFFFFFFF),
            ctypes.byref(overlapped),
        )
        if not result:
            last_error = ctypes.GetLastError()
            kernel32.CloseHandle(wintypes.HANDLE(handle))
            if last_error == _ERROR_LOCK_VIOLATION:
                raise ConstitutionWriterBusyError(
                    message="another `haex constitution assemble` is running"
                )
            raise ctypes.WinError(last_error)
        self._handle = handle

    def _release_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        if self._handle is not None:
            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            self._handle = None
