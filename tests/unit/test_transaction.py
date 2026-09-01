"""FR-035 durable-journal recovery + concurrent-writer refusal."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from haex_hive.io import transaction, writer_lock
from haex_hive.io.state import transaction_paths
from haex_hive.util.errors import (
    ConstitutionWriterBusyError,
    PostWriteValidationError,
)


def _hive(repo_root: Path) -> Path:
    return repo_root / transaction.HAEX_HIVE_DIR


def _init_project(repo_root: Path) -> Path:
    state_root = repo_root / "state"
    (repo_root / ".haex-hive.json").write_text(
        json.dumps({"identity": "com.example.consumer"})
    )
    return state_root


def _paths(repo_root: Path, state_root: Path) -> tuple[Path, Path, Path]:
    hive = _hive(repo_root)
    return hive / "constitution.md", hive / "install.lock", transaction_paths(
        repo_root, state_root
    ).journal


def test_publish_creates_targets_when_absent(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    transaction.publish_pair(tmp_path, b"body\n", b"{}\n", state_root=state_root)
    constitution, lock, journal = _paths(tmp_path, state_root)
    assert constitution.read_bytes() == b"body\n"
    assert lock.read_bytes() == b"{}\n"
    assert not journal.exists()


def test_publish_with_state_root_uses_shared_paths(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)

    transaction.publish_pair(tmp_path, b"body\n", b"{}\n", state_root=state_root)

    paths = transaction_paths(tmp_path, state_root)
    assert paths.journal == (
        state_root
        / "locks"
        / paths.repo_key
        / "checkouts"
        / paths.checkout_key
        / "install.journal"
    )
    assert "com.example.consumer" in paths.identity_record.read_text()
    assert paths.mutex.name == "install.mutex"


def test_publish_cleans_backups_when_identity_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".haex-hive.json").write_text(
        json.dumps({"identity": "com.example.consumer"})
    )
    hive = _hive(tmp_path)
    hive.mkdir()
    constitution = hive / transaction.CONSTITUTION_NAME
    lock = hive / transaction.INSTALL_LOCK_NAME
    constitution.write_bytes(b"old body")
    lock.write_bytes(b"old lock")

    def fail_identity_write(paths: object) -> None:
        raise OSError("identity record unavailable")

    monkeypatch.setattr(transaction, "write_identity_record", fail_identity_write)

    with pytest.raises(OSError, match="identity record unavailable"):
        transaction.publish_pair(
            tmp_path,
            b"new body",
            b"new lock",
            state_root=tmp_path / "state",
        )

    assert constitution.read_bytes() == b"old body"
    assert lock.read_bytes() == b"old lock"
    assert not list(hive.glob("*.backup.*.tmp"))


def test_publish_replaces_existing_and_removes_journal(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    transaction.publish_pair(tmp_path, b"old body", b"{}", state_root=state_root)
    transaction.publish_pair(
        tmp_path, b"new body", b"{\"generated_by\": \"haex 2.0.0\"}", state_root=state_root
    )
    constitution, lock, journal = _paths(tmp_path, state_root)
    assert constitution.read_bytes() == b"new body"
    assert lock.read_bytes() == b"{\"generated_by\": \"haex 2.0.0\"}"
    assert not journal.exists()


def test_post_write_verify_rollback_restores_previous(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    transaction.publish_pair(tmp_path, b"good", b"{}", state_root=state_root)

    def failing_verify() -> None:
        raise PostWriteValidationError(message="mismatch")

    with pytest.raises(PostWriteValidationError):
        transaction.publish_pair(
            tmp_path,
            b"bad",
            b"{\"bad\": true}",
            post_write_verify=failing_verify,
            state_root=state_root,
        )

    constitution, lock, journal = _paths(tmp_path, state_root)
    assert constitution.read_bytes() == b"good"
    assert lock.read_bytes() == b"{}"
    assert not journal.exists()


def test_post_write_verify_rollback_removes_previously_absent(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    def failing_verify() -> None:
        raise PostWriteValidationError(message="mismatch")

    with pytest.raises(PostWriteValidationError):
        transaction.publish_pair(
            tmp_path, b"new", b"{}", post_write_verify=failing_verify, state_root=state_root
        )

    constitution, lock, journal = _paths(tmp_path, state_root)
    assert not constitution.exists()
    assert not lock.exists()
    assert not journal.exists()


def test_recover_after_journal_present_restores_backups(tmp_path: Path) -> None:
    """Simulate crash after journal write + target replacement."""
    state_root = _init_project(tmp_path)
    hive = _hive(tmp_path)
    hive.mkdir(parents=True)
    constitution, lock, journal = _paths(tmp_path, state_root)

    constitution.write_bytes(b"original constitution")
    lock.write_bytes(b"original lock")

    backup_c = hive / "constitution.backup.tmp"
    backup_l = hive / "install_lock.backup.tmp"
    shutil.copy2(constitution, backup_c)
    shutil.copy2(lock, backup_l)

    constitution.write_bytes(b"HALF-WRITTEN")
    lock.write_bytes(b"HALF-WRITTEN")
    journal.parent.mkdir(parents=True)

    journal.write_text(
        json.dumps(
            {
                "repo_key": transaction_paths(tmp_path, state_root).repo_key,
                "checkout_key": transaction_paths(tmp_path, state_root).checkout_key,
                "targets": [
                    {
                        "logical": "constitution",
                        "target": f"{transaction.HAEX_HIVE_DIR}/constitution.md",
                        "staged": f"{transaction.HAEX_HIVE_DIR}/constitution.staged.tmp",
                        "prior_state": "existed",
                        "backup": f"{transaction.HAEX_HIVE_DIR}/constitution.backup.tmp",
                    },
                    {
                        "logical": "install_lock",
                        "target": f"{transaction.HAEX_HIVE_DIR}/install.lock",
                        "staged": f"{transaction.HAEX_HIVE_DIR}/install_lock.staged.tmp",
                        "prior_state": "existed",
                        "backup": f"{transaction.HAEX_HIVE_DIR}/install_lock.backup.tmp",
                    },
                ]
            }
        )
    )

    recovered = transaction.recover_if_journaled(tmp_path, state_root=state_root)
    assert recovered
    assert constitution.read_bytes() == b"original constitution"
    assert lock.read_bytes() == b"original lock"
    assert not journal.exists()


def test_recover_absent_prior_removes_targets(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    hive = _hive(tmp_path)
    hive.mkdir(parents=True)
    constitution, lock, journal = _paths(tmp_path, state_root)

    constitution.write_bytes(b"HALF-WRITTEN")
    lock.write_bytes(b"HALF-WRITTEN")
    journal.parent.mkdir(parents=True)

    journal.write_text(
        json.dumps(
            {
                "repo_key": transaction_paths(tmp_path, state_root).repo_key,
                "checkout_key": transaction_paths(tmp_path, state_root).checkout_key,
                "targets": [
                    {
                        "logical": "constitution",
                        "target": f"{transaction.HAEX_HIVE_DIR}/constitution.md",
                        "staged": f"{transaction.HAEX_HIVE_DIR}/constitution.staged.tmp",
                        "prior_state": "absent",
                        "backup": None,
                    },
                    {
                        "logical": "install_lock",
                        "target": f"{transaction.HAEX_HIVE_DIR}/install.lock",
                        "staged": f"{transaction.HAEX_HIVE_DIR}/install_lock.staged.tmp",
                        "prior_state": "absent",
                        "backup": None,
                    },
                ]
            }
        )
    )

    assert transaction.recover_if_journaled(tmp_path, state_root=state_root)
    assert not constitution.exists()
    assert not lock.exists()
    assert not journal.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl-based lock is POSIX-only")
def test_concurrent_writer_refused(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    lock_path = transaction_paths(tmp_path, state_root).mutex
    lock = writer_lock.ConstitutionWriterLock(lock_path)
    with lock:
        second = writer_lock.ConstitutionWriterLock(lock_path)
        with pytest.raises(ConstitutionWriterBusyError), second:
            pass
