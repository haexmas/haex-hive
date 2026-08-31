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


def _paths(repo_root: Path) -> tuple[Path, Path, Path]:
    hive = _hive(repo_root)
    return hive / "constitution.md", hive / "install.lock", hive / transaction.JOURNAL_NAME


def test_publish_creates_targets_when_absent(tmp_path: Path) -> None:
    transaction.publish_pair(tmp_path, b"body\n", b"{}\n")
    constitution, lock, journal = _paths(tmp_path)
    assert constitution.read_bytes() == b"body\n"
    assert lock.read_bytes() == b"{}\n"
    assert not journal.exists()


def test_publish_with_state_root_uses_shared_paths(tmp_path: Path) -> None:
    (tmp_path / ".haex-hive.json").write_text(
        json.dumps({"identity": "com.example.consumer"})
    )
    state_root = tmp_path / "state"

    transaction.publish_pair(tmp_path, b"body\n", b"{}\n", state_root=state_root)

    paths = transaction_paths(tmp_path, state_root)
    assert paths.journal == state_root / "locks" / paths.repo_key / "install.journal"
    assert "com.example.consumer" in paths.identity_record.read_text()
    assert paths.mutex.name == "install.mutex"
    assert not paths.legacy_journal.exists()


def test_publish_replaces_existing_and_removes_journal(tmp_path: Path) -> None:
    transaction.publish_pair(tmp_path, b"old body", b"{}")
    transaction.publish_pair(tmp_path, b"new body", b"{\"generated_by\": \"haex 2.0.0\"}")
    constitution, lock, journal = _paths(tmp_path)
    assert constitution.read_bytes() == b"new body"
    assert lock.read_bytes() == b"{\"generated_by\": \"haex 2.0.0\"}"
    assert not journal.exists()


def test_post_write_verify_rollback_restores_previous(tmp_path: Path) -> None:
    transaction.publish_pair(tmp_path, b"good", b"{}")

    def failing_verify() -> None:
        raise PostWriteValidationError(message="mismatch")

    with pytest.raises(PostWriteValidationError):
        transaction.publish_pair(
            tmp_path, b"bad", b"{\"bad\": true}", post_write_verify=failing_verify
        )

    constitution, lock, journal = _paths(tmp_path)
    assert constitution.read_bytes() == b"good"
    assert lock.read_bytes() == b"{}"
    assert not journal.exists()


def test_post_write_verify_rollback_removes_previously_absent(tmp_path: Path) -> None:
    def failing_verify() -> None:
        raise PostWriteValidationError(message="mismatch")

    with pytest.raises(PostWriteValidationError):
        transaction.publish_pair(tmp_path, b"new", b"{}", post_write_verify=failing_verify)

    constitution, lock, journal = _paths(tmp_path)
    assert not constitution.exists()
    assert not lock.exists()
    assert not journal.exists()


def test_recover_after_journal_present_restores_backups(tmp_path: Path) -> None:
    """Simulate crash after journal write + target replacement."""
    hive = _hive(tmp_path)
    hive.mkdir(parents=True)
    constitution, lock, journal = _paths(tmp_path)

    constitution.write_bytes(b"original constitution")
    lock.write_bytes(b"original lock")

    backup_c = hive / "constitution.backup.tmp"
    backup_l = hive / "install_lock.backup.tmp"
    shutil.copy2(constitution, backup_c)
    shutil.copy2(lock, backup_l)

    constitution.write_bytes(b"HALF-WRITTEN")
    lock.write_bytes(b"HALF-WRITTEN")

    journal.write_text(
        json.dumps(
            {
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

    recovered = transaction.recover_if_journaled(tmp_path)
    assert recovered
    assert constitution.read_bytes() == b"original constitution"
    assert lock.read_bytes() == b"original lock"
    assert not journal.exists()


def test_recover_absent_prior_removes_targets(tmp_path: Path) -> None:
    hive = _hive(tmp_path)
    hive.mkdir(parents=True)
    constitution, lock, journal = _paths(tmp_path)

    constitution.write_bytes(b"HALF-WRITTEN")
    lock.write_bytes(b"HALF-WRITTEN")

    journal.write_text(
        json.dumps(
            {
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

    assert transaction.recover_if_journaled(tmp_path)
    assert not constitution.exists()
    assert not lock.exists()
    assert not journal.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl-based lock is POSIX-only")
def test_concurrent_writer_refused(tmp_path: Path) -> None:
    lock_path = tmp_path / ".haex-hive" / "constitution-transaction.lock"
    lock = writer_lock.ConstitutionWriterLock(lock_path)
    with lock:
        second = writer_lock.ConstitutionWriterLock(lock_path)
        with pytest.raises(ConstitutionWriterBusyError), second:
            pass
