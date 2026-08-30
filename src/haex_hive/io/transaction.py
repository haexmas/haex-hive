"""Durable-journal pair publication for the constitution + install-lock (FR-035).

Journal is at `<repo_root>/.haex-hive/constitution-transaction.json`. Recovery
protocol: if a live journal exists, restore each target from its recorded
backup (or remove the target if the recorded prior state was `absent`), then
remove the journal. `publish_pair` writes both targets atomically, invokes an
optional `post_write_verify` callback while the journal is still on disk, and
only removes the journal after that callback returns cleanly.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, cast

_IS_WINDOWS = sys.platform == "win32"

JOURNAL_NAME = "constitution-transaction.json"
CONSTITUTION_NAME = "constitution.md"
INSTALL_LOCK_NAME = "install.lock"
HAEX_HIVE_DIR = ".haex-hive"


@dataclass(frozen=True)
class _TargetEntry:
    logical: str  # "constitution" | "install_lock"
    target: Path
    staged: Path
    prior_state: str  # "existed" | "absent"
    backup: Path | None


def _fsync_dir(path: Path) -> None:
    if _IS_WINDOWS:
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_file(path: Path) -> None:
    if _IS_WINDOWS:
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_and_fsync(target: Path, data: bytes) -> None:
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _stage_file(logical: str, dir_: Path, data: bytes) -> Path:
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"{logical}.staged.",
        suffix=".tmp",
        dir=str(dir_),
    )
    tmp = Path(tmp_path)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return tmp


def _backup_existing(logical: str, target: Path) -> Path:
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"{logical}.backup.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    os.close(fd)
    backup = Path(tmp_path)
    with open(target, "rb") as src, open(backup, "wb") as dst:
        while True:
            chunk = src.read(65536)
            if not chunk:
                break
            dst.write(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    return backup


def _remove_if_exists(path: Path) -> None:
    with suppress(FileNotFoundError):
        path.unlink()


def _journal_path(repo_root: Path) -> Path:
    return repo_root / HAEX_HIVE_DIR / JOURNAL_NAME


def is_journaled(repo_root: Path) -> bool:
    return _journal_path(repo_root).exists()


def _read_journal(journal: Path) -> dict[str, Any]:
    with open(journal, "rb") as fh:
        return cast(dict[str, Any], json.loads(fh.read().decode("utf-8")))


def _write_journal(journal: Path, entries: list[_TargetEntry]) -> None:
    journal.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "targets": [
            {
                "logical": e.logical,
                "target": str(e.target.relative_to(journal.parent.parent)),
                "staged": str(e.staged.relative_to(journal.parent.parent)),
                "prior_state": e.prior_state,
                "backup": (
                    str(e.backup.relative_to(journal.parent.parent))
                    if e.backup is not None
                    else None
                ),
            }
            for e in entries
        ]
    }
    fd, tmp_path = tempfile.mkstemp(
        prefix=JOURNAL_NAME + ".",
        suffix=".tmp",
        dir=str(journal.parent),
    )
    tmp = Path(tmp_path)
    with os.fdopen(fd, "wb") as fh:
        fh.write(json.dumps(payload, sort_keys=True, indent=2).encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp), str(journal))
    _fsync_dir(journal.parent)


def recover_if_journaled(repo_root: Path) -> bool:
    """Restore both targets from their recorded backup state, then remove the journal.

    Returns True if recovery ran, False if no journal was present.
    """
    journal = _journal_path(repo_root)
    if not journal.exists():
        return False
    payload = _read_journal(journal)
    raw_entries = payload.get("targets")
    if not isinstance(raw_entries, list):
        raise ValueError("transaction journal targets must be a list")

    hive_dir = (repo_root / HAEX_HIVE_DIR).resolve()
    fixed_targets = {
        "constitution": hive_dir / CONSTITUTION_NAME,
        "install_lock": hive_dir / INSTALL_LOCK_NAME,
    }
    validated_entries: list[tuple[Path, str, Path | None, Path]] = []
    seen_logical: set[str] = set()
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise ValueError("transaction journal target entry must be an object")
        logical = entry.get("logical")
        if logical not in fixed_targets or logical in seen_logical:
            raise ValueError("transaction journal contains an invalid logical target")
        seen_logical.add(logical)

        target = _validate_journal_path(repo_root, entry.get("target"), hive_dir)
        if target != fixed_targets[logical]:
            raise ValueError("transaction journal target does not match its logical target")
        staged = _validate_journal_path(repo_root, entry.get("staged"), hive_dir)
        raw_backup = entry.get("backup")
        backup = (
            _validate_journal_path(repo_root, raw_backup, hive_dir)
            if raw_backup is not None
            else None
        )
        prior = entry.get("prior_state")
        if prior not in {"existed", "absent"}:
            raise ValueError("transaction journal contains an invalid prior state")
        if prior == "existed" and backup is None:
            raise ValueError("existing transaction target is missing its backup")
        validated_entries.append((target, prior, backup, staged))

    if seen_logical != set(fixed_targets):
        raise ValueError("transaction journal must contain both logical targets")

    for target, prior, backup, staged in validated_entries:
        if prior == "existed" and backup:
            if backup.exists():
                os.replace(str(backup), str(target))
            _fsync_dir(target.parent)
        elif prior == "absent":
            _remove_if_exists(target)
        _remove_if_exists(staged)
        if backup:
            _remove_if_exists(backup)
    _remove_if_exists(journal)
    _fsync_dir(journal.parent)
    return True


def _validate_journal_path(repo_root: Path, raw_path: object, hive_dir: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("transaction journal path must be a non-empty string")
    path = Path(raw_path)
    windows_path = PureWindowsPath(raw_path)
    if path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ValueError("transaction journal paths must be relative")
    if ".." in path.parts or ".." in windows_path.parts:
        raise ValueError("transaction journal paths must not contain traversal")
    resolved = (repo_root / path).resolve()
    try:
        resolved.relative_to(hive_dir)
    except ValueError:
        raise ValueError("transaction journal path escapes .haex-hive") from None
    return resolved


def publish_pair(
    repo_root: Path,
    constitution_body: bytes,
    install_lock_bytes: bytes,
    *,
    post_write_verify: Callable[[], None] | None = None,
) -> None:
    """Atomically publish both targets under the durable journal protocol."""

    hive_dir = repo_root / HAEX_HIVE_DIR
    hive_dir.mkdir(parents=True, exist_ok=True)

    constitution_target = hive_dir / CONSTITUTION_NAME
    install_lock_target = hive_dir / INSTALL_LOCK_NAME

    entries: list[_TargetEntry] = []
    try:
        for logical, target, data in (
            ("constitution", constitution_target, constitution_body),
            ("install_lock", install_lock_target, install_lock_bytes),
        ):
            existed = target.exists()
            backup = _backup_existing(logical, target) if existed else None
            staged = _stage_file(logical, hive_dir, data)
            entries.append(
                _TargetEntry(
                    logical=logical,
                    target=target,
                    staged=staged,
                    prior_state="existed" if existed else "absent",
                    backup=backup,
                )
            )
        _fsync_dir(hive_dir)

        journal = _journal_path(repo_root)
        _write_journal(journal, entries)

        for entry in entries:
            os.replace(str(entry.staged), str(entry.target))
        _fsync_dir(hive_dir)

        if post_write_verify is not None:
            try:
                post_write_verify()
            except BaseException:
                _rollback_entries(repo_root, entries)
                _remove_if_exists(journal)
                _fsync_dir(hive_dir)
                raise

        for entry in entries:
            if entry.backup is not None:
                _remove_if_exists(entry.backup)
        _remove_if_exists(journal)
        _fsync_dir(hive_dir)
    except BaseException:
        for entry in entries:
            _remove_if_exists(entry.staged)
        raise


def _rollback_entries(repo_root: Path, entries: list[_TargetEntry]) -> None:
    for entry in entries:
        if entry.prior_state == "existed" and entry.backup is not None and entry.backup.exists():
            os.replace(str(entry.backup), str(entry.target))
        elif entry.prior_state == "absent":
            _remove_if_exists(entry.target)
        _remove_if_exists(entry.staged)
