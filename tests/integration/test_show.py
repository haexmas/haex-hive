"""T063 — end-to-end `haex constitution show` (US4)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _run_haex(
    repo_root: Path,
    *args: str,
    state_root: Path,
    stdin_bytes: bytes | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HAEX_HIVE_STATE"] = str(state_root)
    return subprocess.run(
        [sys.executable, "-m", "haex_hive", "--repo-root", str(repo_root), *args],
        input=stdin_bytes if stdin_bytes is not None else b"",
        capture_output=True,
        env=env,
    )


def _assemble(consumer: Path, state_root: Path) -> None:
    proc = _run_haex(consumer, "install", state_root=state_root)
    assert proc.returncode == 0, proc.stderr.decode()


def _show(consumer: Path, *args: str, state_root: Path) -> subprocess.CompletedProcess:
    return _run_haex(consumer, "constitution", "show", *args, state_root=state_root)


def test_preface_and_body_byte_identity(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 0, proc.stderr.decode()

    atom_id = single_source_constitution_fixture["atom_id"]
    commit_sha = single_source_constitution_fixture["commit_sha"]
    canonical = single_source_constitution_fixture["canonical"]
    body = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    expected = (
        f"# Assembled from\n- {atom_id} @ {commit_sha[:7]} ({canonical})\n\n---\n\n"
    ).encode() + body
    assert proc.stdout == expected


def test_no_preface_prints_only_body(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    proc = _show(consumer, "--no-preface", state_root=state_root)
    assert proc.returncode == 0, proc.stderr.decode()

    body = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    assert proc.stdout == body


def test_missing_constitution_refuses(tmp_path: Path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()

    proc = _show(consumer, state_root=tmp_path / "state")
    assert proc.returncode == 2
    assert b"key=constitution-not-assembled" in proc.stderr


def test_missing_lock_refuses(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)
    (consumer / ".haex-hive" / "install.lock").unlink()

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 3
    assert b"key=install-lock-missing" in proc.stderr


def test_install_lock_schema_invalid_refuses(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    lock_path = consumer / ".haex-hive" / "install.lock"
    data = json.loads(lock_path.read_text())
    del data["constitution"]["sources"]
    lock_path.write_text(json.dumps(data))

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 4
    assert b"key=install-lock-schema-invalid" in proc.stderr


def test_install_lock_sources_not_canonical_refuses(
    single_source_constitution_fixture: dict,
) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    lock_path = consumer / ".haex-hive" / "install.lock"
    data = json.loads(lock_path.read_text())
    source = data["constitution"]["sources"][0]
    data["constitution"]["sources"] = [
        {**source, "id": "com.z.example.constitution"},
        {**source, "id": "com.a.example.constitution"},
    ]
    lock_path.write_text(json.dumps(data))

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 4
    assert b"key=install-lock-sources-not-canonical" in proc.stderr


def test_body_is_rendered_from_a_valid_lock(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    constitution_path = consumer / ".haex-hive" / "constitution.md"
    constitution_path.write_bytes(constitution_path.read_bytes() + b"tampered\n")

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 0, proc.stderr.decode()
    assert proc.stdout.endswith(b"tampered\n")


@pytest.mark.parametrize("sibling", ["next", "prev"])
def test_show_ignores_stale_siblings(
    single_source_constitution_fixture: dict, sibling: str
) -> None:
    """`haex constitution show` is read-only; stale siblings do not affect it."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    (consumer / f".haex-hive.{sibling}").mkdir()

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 0, proc.stderr.decode()


def test_show_refuses_when_live_absent(
    single_source_constitution_fixture: dict,
) -> None:
    """A missing `.haex-hive/` produces the standard not-assembled refusal."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    _assemble(consumer, state_root)

    shutil.rmtree(consumer / ".haex-hive")
    (consumer / ".haex-hive.prev").mkdir()

    proc = _show(consumer, state_root=state_root)
    assert proc.returncode == 2, proc.stderr.decode()
    assert b"key=constitution-not-assembled" in proc.stderr
