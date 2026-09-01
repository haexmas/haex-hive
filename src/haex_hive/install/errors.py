"""Install-specific `HaexError` subclasses.

Each carries a canonical `diagnostic_key` and the exit code from
[haex-install.cli.md](../../../specs/008-install-transaction/contracts/haex-install.cli.md).
The base `HaexError` type and the shared exit-code enum live in
`haex_hive.util.errors` and `haex_hive.util.exit_codes`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError


@dataclass
class HaexInstallError(HaexError):
    """Base class for every diagnostic emitted by `haex install` itself.

    Subclasses set `diagnostic_key` and `exit_code` per the CLI contract.
    """


@dataclass
class InstallLockBusy(HaexInstallError):
    diagnostic_key: str = "install-lock-busy"
    exit_code: int = exit_codes.INSTALL_LOCK_BUSY
    hint: str = "Wait for the current owner to release or re-run once it has exited."


@dataclass
class IncompleteTransaction(HaexInstallError):
    diagnostic_key: str = "install-transaction-incomplete"
    exit_code: int = exit_codes.INCOMPLETE_TRANSACTION
    hint: str = "Run `haex verify --recover` to complete or roll back the interrupted install."


@dataclass
class CommitSnapshotMismatch(HaexInstallError):
    diagnostic_key: str = "install-commit-snapshot-mismatch"
    exit_code: int = exit_codes.VALIDATION_REFUSE
    hint: str = "An input file mutated during the install. Re-run once the writer is done."


@dataclass
class OverlayUnsupported(HaexInstallError):
    diagnostic_key: str = "install-overlay-unsupported"
    exit_code: int = exit_codes.SYSTEM_REFUSE
    hint: str = "The current platform lacks the required overlay primitive for this path."


@dataclass
class SealMismatch(HaexInstallError):
    diagnostic_key: str = "install-seal-mismatch"
    exit_code: int = exit_codes.POST_WRITE_VALIDATION
    hint: str = "A sealed output does not match its recorded digest; re-run the install."


def busy_lock_from_mutex(mutex_path: Path, *, now_ns: int | None = None) -> InstallLockBusy:
    """Build an `InstallLockBusy` from the on-disk `install.mutex` payload.

    The mutex file may be missing, empty, or corrupt if the previous holder
    crashed before writing metadata or between rewrites; each of these cases
    lands a well-typed refusal with a `context` dict the diagnostic emitter
    can render deterministically.
    """
    actual_now_ns = time.time_ns() if now_ns is None else now_ns
    payload = _read_mutex_payload(mutex_path)
    if payload is None:
        return InstallLockBusy(
            message="another haex install owns the lock (mutex metadata unavailable)",
            context={"mutex_path": str(mutex_path)},
        )

    token = payload.get("owner_token", "")
    parts = token.split(":", 3) if isinstance(token, str) else []
    pid = parts[0] if len(parts) >= 1 else "?"
    hostname = parts[1] if len(parts) >= 2 else "?"
    acquired_at = payload.get("acquired_at", "?")
    heartbeat_at_ns = payload.get("heartbeat_at_ns_wallclock")
    ttl_ns = payload.get("ttl_ns", 60_000_000_000)
    if isinstance(heartbeat_at_ns, int):
        age_s = (actual_now_ns - heartbeat_at_ns) / 1_000_000_000
        heartbeat_desc = f"heartbeat {age_s:.1f}s ago"
    else:
        heartbeat_desc = "heartbeat unknown"
    ttl_s = int(ttl_ns) / 1_000_000_000 if isinstance(ttl_ns, int) else 60
    return InstallLockBusy(
        message=(
            f"lock owned by pid {pid}@{hostname} since {acquired_at} "
            f"({heartbeat_desc}, ttl {ttl_s:.0f}s)"
        ),
        context={
            "pid": pid,
            "hostname": hostname,
            "acquired_at": str(acquired_at),
            "mutex_path": str(mutex_path),
        },
    )


def _read_mutex_payload(mutex_path: Path) -> dict[str, Any] | None:
    """Best-effort read of `install.mutex`; returns None on any parse failure."""
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
