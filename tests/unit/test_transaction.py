"""FR-035 rename-swap publication + concurrent-writer refusal (R1/R7 amendment)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from haex_hive.install import inflight
from haex_hive.install.lock import OwnerToken
from haex_hive.io import transaction, writer_lock
from haex_hive.io.state import transaction_paths
from haex_hive.util.errors import (
    ConstitutionWriterBusyError,
    HaexError,
    PostWriteValidationError,
)


def _init_project(repo_root: Path) -> Path:
    """Prepare a project fixture with an identity and return its state root."""
    state_root = repo_root / "state"
    (repo_root / ".haex-hive.json").write_text(
        json.dumps({"identity": "com.example.consumer"})
    )
    return state_root


def _staged(
    constitution: bytes, install_lock: bytes, visibility: bytes
) -> list[transaction.StagedFile]:
    return [
        transaction.StagedFile(transaction.CONSTITUTION_NAME, constitution),
        transaction.StagedFile(transaction.INSTALL_LOCK_NAME, install_lock),
        transaction.StagedFile(transaction.VISIBILITY_NAME, visibility),
    ]


def test_publish_creates_live_on_first_generation(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    live = tmp_path / transaction.HAEX_HIVE_DIR

    transaction.publish_generation(
        live,
        _staged(b"body\n", b"{}\n", b"{}\n"),
        state_root=state_root,
        repo_root=tmp_path,
    )

    assert (live / transaction.CONSTITUTION_NAME).read_bytes() == b"body\n"
    assert (live / transaction.INSTALL_LOCK_NAME).read_bytes() == b"{}\n"
    assert (live / transaction.VISIBILITY_NAME).read_bytes() == b"{}\n"
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.next").exists()
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").exists()


def test_publish_replaces_previous_generation_via_rename_swap(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    live = tmp_path / transaction.HAEX_HIVE_DIR

    transaction.publish_generation(
        live,
        _staged(b"old\n", b"{}\n", b"{}\n"),
        state_root=state_root,
        repo_root=tmp_path,
    )
    transaction.publish_generation(
        live,
        _staged(b"new\n", b'{"generated_by": "haex 2.0.0"}\n', b"{}\n"),
        state_root=state_root,
        repo_root=tmp_path,
    )

    assert (live / transaction.CONSTITUTION_NAME).read_bytes() == b"new\n"
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.next").exists()
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").exists()


def test_publish_writes_identity_record_under_state_root(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    live = tmp_path / transaction.HAEX_HIVE_DIR

    transaction.publish_generation(
        live,
        _staged(b"body\n", b"{}\n", b"{}\n"),
        state_root=state_root,
        repo_root=tmp_path,
    )

    paths = transaction_paths(tmp_path, state_root)
    assert paths.identity_record.exists()
    record = json.loads(paths.identity_record.read_text())
    assert record["identity"] == "com.example.consumer"


def test_post_write_verify_rollback_restores_previous(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    live = tmp_path / transaction.HAEX_HIVE_DIR

    transaction.publish_generation(
        live,
        _staged(b"good\n", b"{}\n", b"{}\n"),
        state_root=state_root,
        repo_root=tmp_path,
    )

    def failing_verify() -> None:
        raise PostWriteValidationError(message="mismatch")

    with pytest.raises(PostWriteValidationError):
        transaction.publish_generation(
            live,
            _staged(b"bad\n", b'{"bad": true}\n', b"{}\n"),
            post_write_verify=failing_verify,
            state_root=state_root,
            repo_root=tmp_path,
        )

    assert (live / transaction.CONSTITUTION_NAME).read_bytes() == b"good\n"
    assert (live / transaction.INSTALL_LOCK_NAME).read_bytes() == b"{}\n"
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.next").exists()
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").exists()


def test_rename_b_failure_restores_previous_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = _init_project(tmp_path)
    live = tmp_path / transaction.HAEX_HIVE_DIR
    transaction.publish_generation(
        live,
        _staged(b"old\n", b"{}\n", b"{}\n"),
        state_root=state_root,
        repo_root=tmp_path,
    )

    real_rename = transaction.os.rename

    def fail_rename_b(source: str, destination: str) -> None:
        if Path(source) == tmp_path / f"{transaction.HAEX_HIVE_DIR}.next":
            raise OSError("rename B failed")
        real_rename(source, destination)

    monkeypatch.setattr(transaction.os, "rename", fail_rename_b)
    with pytest.raises(OSError, match="rename B failed"):
        transaction.publish_generation(
            live,
            _staged(b"new\n", b"{}\n", b"{}\n"),
            state_root=state_root,
            repo_root=tmp_path,
        )

    assert (live / transaction.CONSTITUTION_NAME).read_bytes() == b"old\n"
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.next").exists()
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").exists()


def test_post_write_verify_rollback_removes_first_generation(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    live = tmp_path / transaction.HAEX_HIVE_DIR

    def failing_verify() -> None:
        raise PostWriteValidationError(message="mismatch")

    with pytest.raises(PostWriteValidationError):
        transaction.publish_generation(
            live,
            _staged(b"new\n", b"{}\n", b"{}\n"),
            post_write_verify=failing_verify,
            state_root=state_root,
            repo_root=tmp_path,
        )

    assert not live.exists()
    assert not (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").exists()


def test_inflight_resolve_completes_forward_after_mid_swap_crash(tmp_path: Path) -> None:
    live = tmp_path / transaction.HAEX_HIVE_DIR
    next_dir = tmp_path / f"{transaction.HAEX_HIVE_DIR}.next"
    prev_dir = tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev"

    next_dir.mkdir()
    (next_dir / "constitution.md").write_bytes(b"new gen\n")
    prev_dir.mkdir()
    (prev_dir / "constitution.md").write_bytes(b"prev gen\n")

    state = inflight.resolve(live)

    assert state is inflight.InflightState.MID_SWAP
    assert live.exists()
    assert (live / "constitution.md").read_bytes() == b"new gen\n"
    assert not next_dir.exists()
    assert not prev_dir.exists()


def test_inflight_resolve_cleans_up_post_swap(tmp_path: Path) -> None:
    live = tmp_path / transaction.HAEX_HIVE_DIR
    prev_dir = tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev"

    live.mkdir()
    (live / "constitution.md").write_bytes(b"live\n")
    prev_dir.mkdir()
    (prev_dir / "constitution.md").write_bytes(b"prev\n")

    state = inflight.resolve(live)

    assert state is inflight.InflightState.POST_SWAP
    assert (live / "constitution.md").read_bytes() == b"live\n"
    assert not prev_dir.exists()


def test_inflight_resolve_deletes_stale_next_pre_swap(tmp_path: Path) -> None:
    live = tmp_path / transaction.HAEX_HIVE_DIR
    next_dir = tmp_path / f"{transaction.HAEX_HIVE_DIR}.next"

    live.mkdir()
    (live / "constitution.md").write_bytes(b"live\n")
    next_dir.mkdir()
    (next_dir / "constitution.md").write_bytes(b"aborted\n")

    state = inflight.resolve(live)

    assert state is inflight.InflightState.PRE_SWAP
    assert live.exists()
    assert not next_dir.exists()


def test_inflight_resolve_is_noop_on_steady_state(tmp_path: Path) -> None:
    live = tmp_path / transaction.HAEX_HIVE_DIR
    live.mkdir()
    (live / "constitution.md").write_bytes(b"live\n")

    assert inflight.resolve(live) is inflight.InflightState.STEADY
    assert live.exists()


def test_inflight_resolve_is_noop_on_uninitialized_state(tmp_path: Path) -> None:
    live = tmp_path / transaction.HAEX_HIVE_DIR

    assert inflight.resolve(live) is inflight.InflightState.UNINITIALIZED
    assert not live.exists()


@pytest.mark.parametrize(
    "row_name,make_state",
    [
        (
            "orphan_prev",
            lambda tmp_path, live: (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").mkdir(),
        ),
        (
            "orphan_next",
            lambda tmp_path, live: (tmp_path / f"{transaction.HAEX_HIVE_DIR}.next").mkdir(),
        ),
        (
            "illegal_all",
            lambda tmp_path, live: [
                live.mkdir(),
                (tmp_path / f"{transaction.HAEX_HIVE_DIR}.next").mkdir(),
                (tmp_path / f"{transaction.HAEX_HIVE_DIR}.prev").mkdir(),
            ],
        ),
    ],
)
def test_inflight_resolve_raises_on_integrity_failures(
    tmp_path: Path,
    row_name: str,
    make_state,
) -> None:
    del row_name
    live = tmp_path / transaction.HAEX_HIVE_DIR
    make_state(tmp_path, live)

    with pytest.raises(inflight.InflightIntegrityError) as raised:
        inflight.resolve(live)
    assert isinstance(raised.value, HaexError)
    assert raised.value.diagnostic_key == "constitution-transaction-incomplete"
    assert raised.value.exit_code == 7


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl-based lock is POSIX-only")
def test_concurrent_writer_refused(tmp_path: Path) -> None:
    state_root = _init_project(tmp_path)
    lock_path = transaction_paths(tmp_path, state_root).mutex
    lock = writer_lock.ConstitutionWriterLock(lock_path)
    with lock:
        second = writer_lock.ConstitutionWriterLock(lock_path)
        with pytest.raises(ConstitutionWriterBusyError):
            second.__enter__()


def _sample_token() -> OwnerToken:
    return OwnerToken(
        pid=12345,
        hostname="test-host",
        start_ns=1_000_000_000_000_000_000,
        uuid4_hex="0" * 32,
    )


def test_writer_lock_writes_mutex_metadata_when_owner_token_supplied(
    tmp_path: Path,
) -> None:
    """Acquiring with an OwnerToken populates install.mutex per data-model.md."""
    lock_path = tmp_path / "install.mutex"
    token = _sample_token()

    with writer_lock.ConstitutionWriterLock(lock_path, token):
        record = json.loads(lock_path.read_bytes())

    assert record["owner_token"] == token.serialize()
    assert record["heartbeat_interval_ns"] == writer_lock.HEARTBEAT_INTERVAL_NS
    assert record["ttl_ns"] == writer_lock.TTL_NS
    assert record["safety_margin_ns"] == writer_lock.SAFETY_MARGIN_NS
    assert record["acquired_at"] == record["heartbeat_at"]
    assert isinstance(record["heartbeat_at_ns_wallclock"], int)


def test_writer_lock_heartbeat_updates_in_place_without_changing_inode(
    tmp_path: Path,
) -> None:
    """heartbeat() rewrites the mutex file through the locked handle; inode stable."""
    lock_path = tmp_path / "install.mutex"
    with writer_lock.ConstitutionWriterLock(lock_path, _sample_token()) as lock:
        inode_before = lock_path.stat().st_ino
        initial = json.loads(lock_path.read_bytes())
        # Ensure the wall clock advances beyond nanosecond granularity.
        import time as _time
        _time.sleep(0.001)
        lock.heartbeat()
        after = json.loads(lock_path.read_bytes())
        inode_after = lock_path.stat().st_ino

    assert inode_before == inode_after
    assert after["heartbeat_at_ns_wallclock"] > initial["heartbeat_at_ns_wallclock"]
    assert after["acquired_at"] == initial["acquired_at"]
    assert after["owner_token"] == initial["owner_token"]


def test_writer_lock_heartbeat_without_token_raises(tmp_path: Path) -> None:
    """heartbeat() is only available when a token was supplied at acquisition."""
    lock_path = tmp_path / "install.mutex"
    with (
        writer_lock.ConstitutionWriterLock(lock_path) as lock,
        pytest.raises(RuntimeError, match="heartbeat requires an OwnerToken"),
    ):
        lock.heartbeat()


def test_writer_lock_pre_spec_008_callers_still_work(tmp_path: Path) -> None:
    """No OwnerToken → the mutex file stays empty, backward-compatible behaviour."""
    lock_path = tmp_path / "install.mutex"
    with writer_lock.ConstitutionWriterLock(lock_path):
        assert lock_path.read_bytes() == b""
