"""T050 — end-to-end `haex constitution assemble` (single-source, US2)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _run_haex(repo_root: Path, *args: str, state_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HAEX_HIVE_STATE"] = str(state_root)
    return subprocess.run(
        [sys.executable, "-m", "haex_hive", "--repo-root", str(repo_root),
         "constitution", "assemble", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_successful_straight_copy(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    proc = _run_haex(consumer, state_root=state_root)
    assert proc.returncode == 0, proc.stderr

    constitution = consumer / ".haex-hive" / "constitution.md"
    lock = consumer / ".haex-hive" / "install.lock"
    marker = consumer / ".haex-hive" / "visibility.json"
    assert constitution.read_bytes() == b"# Example Constitution\n\nBe kind.\n"

    lock_data = json.loads(lock.read_text())
    assert lock_data["haex_hive_version"] == "2"
    assert lock_data["constitution"]["sources"] == [
        {
            "id": single_source_constitution_fixture["atom_id"],
            "revision": single_source_constitution_fixture["commit_sha"],
            "source": single_source_constitution_fixture["canonical"],
        }
    ]
    assert lock_data["constitution"]["content_integrity"].startswith("sha256-")
    marker_data = json.loads(marker.read_text())
    assert marker_data["install_lock_content_integrity"].startswith("sha256-")
    assert marker_data["participating_roots"][0]["root"] == ".haex-hive/"
    assert lock_data["visibility_marker"]["generation_id"] == marker_data["generation_id"]
    assert not (consumer / ".haex-hive" / "constitution-transaction.lock").exists()


def test_legacy_journal_is_left_for_operator_cleanup(
    single_source_constitution_fixture: dict,
) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]
    legacy_journal = consumer / ".haex-hive" / "constitution-transaction.json"
    legacy_journal.parent.mkdir(parents=True)
    legacy_journal.write_text("stale legacy journal")

    proc = _run_haex(consumer, state_root=state_root)

    assert proc.returncode == 0, proc.stderr
    assert legacy_journal.read_text() == "stale legacy journal"


def test_determinism_across_two_runs(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    first = _run_haex(consumer, state_root=state_root)
    assert first.returncode == 0, first.stderr
    constitution_bytes_1 = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    lock_bytes_1 = (consumer / ".haex-hive" / "install.lock").read_bytes()

    second = _run_haex(consumer, state_root=state_root)
    assert second.returncode == 0, second.stderr
    constitution_bytes_2 = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    lock_bytes_2 = (consumer / ".haex-hive" / "install.lock").read_bytes()

    assert constitution_bytes_1 == constitution_bytes_2
    assert lock_bytes_1 == lock_bytes_2


def test_unavailable_pinned_sha_refuses_untouched(single_source_constitution_fixture: dict) -> None:
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    manifest_path = consumer / ".haex-hive.json"
    data = json.loads(manifest_path.read_text())
    data["atoms"][0]["revision"] = "deadbeef" * 5
    manifest_path.write_text(json.dumps(data))

    proc = _run_haex(consumer, state_root=state_root)
    assert proc.returncode == 3
    assert "key=pinned-revision-not-found" in proc.stderr
    assert not (consumer / ".haex-hive" / "constitution.md").exists()
    assert not (consumer / ".haex-hive" / "install.lock").exists()


def test_contribution_file_absent_refuses(tmp_path: Path, git_binary: str) -> None:
    def _git(repo: Path, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        )
        return proc.stdout.strip()

    canonical = "https://github.com/example/broken-publisher"
    publisher = tmp_path / "publisher"
    publisher.mkdir()
    _git(publisher, "init", "-q")
    _git(publisher, "config", "user.email", "haex-test@example.com")
    _git(publisher, "config", "user.name", "haex-test")
    _git(publisher, "config", "commit.gpgsign", "false")
    _git(publisher, "remote", "add", "origin", canonical)

    atom_id = "com.github.example.broken-publisher.constitution"
    (publisher / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "publisher": "com.github.example.broken-publisher",
                "atoms": {atom_id: {"path": "c", "version": "1.0.0"}},
            }
        )
    )
    (publisher / "c").mkdir()
    (publisher / "c" / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "id": atom_id,
                "version": "1.0.0",
                "contributes": {"constitution": "missing.md"},
            }
        )
    )
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "declare missing contribution")
    sha = _git(publisher, "rev-parse", "HEAD")

    state_root = tmp_path / "state"
    from haex_hive.migrate.transform import clone_dir

    clone_target = clone_dir(state_root, canonical)
    clone_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(publisher, clone_target)

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / ".haex-hive.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "identity": "com.github.example.consumer",
                "atoms": [{"source": canonical, "revision": sha, "includes": [atom_id]}],
            }
        )
    )

    proc = _run_haex(consumer, state_root=state_root)
    assert proc.returncode == 3
    assert "key=contribution-file-not-found" in proc.stderr
    assert not (consumer / ".haex-hive" / "constitution.md").exists()


def test_no_sources_declared_refuses(tmp_path: Path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / ".haex-hive.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "identity": "com.github.example.consumer",
                "atoms": [],
            }
        )
    )
    proc = _run_haex(consumer, state_root=tmp_path / "state")
    assert proc.returncode == 2
    assert "key=no-sources-declared" in proc.stderr
