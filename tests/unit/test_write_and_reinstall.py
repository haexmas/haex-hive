"""T061 — unit tests for `install.write_and_reinstall` (Spec 013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from haex_hive.install.manifest_lock import ManifestLockContext
from haex_hive.install.write_and_reinstall import write_and_reinstall
from haex_hive.util.errors import (
    HaexError,
    InstallTransactionFailedError,
    NoSourcesDeclaredError,
)


def _held_lock(tmp_path: Path) -> ManifestLockContext:
    lock = ManifestLockContext(
        tmp_path / ".haex-hive.json.lock", timeout_seconds=1.0
    )
    lock.__enter__()
    return lock


def test_atomic_write_via_tmp_and_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from haex_hive.cli import install as install_cli

    manifest = tmp_path / ".haex-hive.json"
    manifest.write_bytes(b'{"old": true}\n')

    calls: list[str] = []

    def fake_install(args, *, held_manifest_lock=None):
        calls.append(str(args.repo_root))
        return 0

    monkeypatch.setattr(install_cli, "run", fake_install)

    lock = _held_lock(tmp_path)
    try:
        rc = write_and_reinstall(tmp_path, b'{"new": true}\n', lock)
    finally:
        lock.__exit__(None, None, None)

    assert rc == 0
    assert calls == [str(tmp_path)]
    assert manifest.read_bytes() == b'{"new": true}\n'
    assert not (tmp_path / ".haex-hive.json.tmp").exists()


def test_install_failure_rolls_back_manifest_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from haex_hive.cli import install as install_cli

    manifest = tmp_path / ".haex-hive.json"
    manifest.write_bytes(b'{"original": true}\n')

    def failing_install(args, *, held_manifest_lock=None):
        raise NoSourcesDeclaredError(message="no constitution sources declared")

    monkeypatch.setattr(install_cli, "run", failing_install)

    lock = _held_lock(tmp_path)
    try:
        with pytest.raises(InstallTransactionFailedError) as exc_info:
            write_and_reinstall(tmp_path, b'{"never": true}\n', lock)
    finally:
        lock.__exit__(None, None, None)

    assert manifest.read_bytes() == b'{"original": true}\n'
    assert exc_info.value.context["install_key"] == "no-sources-declared"


def test_install_failure_deletes_manifest_when_no_previous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from haex_hive.cli import install as install_cli

    manifest = tmp_path / ".haex-hive.json"
    assert not manifest.exists()

    def failing_install(args, *, held_manifest_lock=None):
        raise HaexError(
            message="boom",
            diagnostic_key="boom",
            exit_code=2,
        )

    monkeypatch.setattr(install_cli, "run", failing_install)

    lock = _held_lock(tmp_path)
    try:
        with pytest.raises(InstallTransactionFailedError):
            write_and_reinstall(tmp_path, b'{"first": true}\n', lock)
    finally:
        lock.__exit__(None, None, None)

    assert not manifest.exists()


def test_install_receives_held_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from haex_hive.cli import install as install_cli

    manifest = tmp_path / ".haex-hive.json"
    manifest.write_bytes(b'{}\n')

    captured: dict[str, ManifestLockContext | None] = {"lock": None}

    def fake_install(args, *, held_manifest_lock=None):
        captured["lock"] = held_manifest_lock
        return 0

    monkeypatch.setattr(install_cli, "run", fake_install)

    lock = _held_lock(tmp_path)
    try:
        write_and_reinstall(tmp_path, b'{}\n', lock)
    finally:
        lock.__exit__(None, None, None)

    assert captured["lock"] is lock
