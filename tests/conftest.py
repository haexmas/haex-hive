"""Shared fixtures for integration tests."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_SELF_ATOM_ID = "com.github.haexmas.haex-hive.constitution"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "haex-test@example.com")
    _git(root, "config", "user.name", "haex-test")
    _git(root, "config", "commit.gpgsign", "false")


@pytest.fixture
def git_binary() -> str:
    binary = shutil.which("git")
    if binary is None:
        pytest.skip("git binary required")
    return binary


@pytest.fixture
def self_migration_fixture(tmp_path: Path, git_binary: str) -> dict:
    """Build the FR-023 A/B/C fixture: publisher repo with root+atom manifests."""

    publisher = tmp_path / "publisher"
    publisher.mkdir()
    _init_repo(publisher)

    _git(publisher, "remote", "add", "origin", "https://github.com/haexmas/haex-hive")

    (publisher / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "publisher": "com.github.haexmas.haex-hive",
                "atoms": {
                    _SELF_ATOM_ID: {
                        "path": ".specify/memory",
                        "version": "1.3.0",
                    }
                },
            },
            sort_keys=True,
        )
    )
    (publisher / ".specify" / "memory").mkdir(parents=True)
    (publisher / ".specify" / "memory" / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "id": _SELF_ATOM_ID,
                "version": "1.3.0",
                "priority": 10,
                "contributes": {"constitution": "constitution.md"},
            },
            sort_keys=True,
        )
    )
    (publisher / ".specify" / "memory" / "constitution.md").write_text(
        "# haex-hive constitution\n\nPrinciple I ...\n"
    )
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "commit A")
    commit_a = _git(publisher, "rev-parse", "HEAD")

    state_root = tmp_path / "state"
    from haex_hive.migrate.transform import clone_dir

    canonical = "https://github.com/haexmas/haex-hive"
    clone_target = clone_dir(state_root, canonical)
    clone_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(publisher, clone_target)

    return {
        "publisher": publisher,
        "state_root": state_root,
        "commit_a": commit_a,
        "canonical": canonical,
    }


@pytest.fixture
def single_source_constitution_fixture(tmp_path: Path, git_binary: str) -> dict:
    """Publisher repo with exactly one constitution molecule, plus a v3 consumer repo."""

    atom_id = "com.github.example.publisher.constitution"
    canonical = "https://github.com/example/publisher"

    publisher = tmp_path / "publisher"
    publisher.mkdir()
    _init_repo(publisher)
    _git(publisher, "remote", "add", "origin", canonical)

    (publisher / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "3",
                "publisher": "com.github.example.publisher",
                "molecules": {
                    atom_id: {"path": "constitution", "version": "1.0.0"},
                },
            },
            sort_keys=True,
        )
    )
    (publisher / "constitution").mkdir()
    (publisher / "constitution" / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "3",
                "id": atom_id,
                "version": "1.0.0",
                "priority": 100,
                "atoms": {"constitution": ["constitution.md"]},
            },
            sort_keys=True,
        )
    )
    (publisher / "constitution" / "constitution.md").write_bytes(
        b"# Example Constitution\n\nBe kind.\n"
    )
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "publish constitution atom")
    commit_sha = _git(publisher, "rev-parse", "HEAD")

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
                "haex_hive_version": "3",
                "identity": "com.github.example.consumer",
                "compounds": [
                    {
                        "source": canonical,
                        "revision": commit_sha,
                        "molecules": [atom_id],
                    }
                ],
            },
            indent=2,
        )
    )

    return {
        "publisher": publisher,
        "consumer": consumer,
        "state_root": state_root,
        "commit_sha": commit_sha,
        "canonical": canonical,
        "atom_id": atom_id,
    }


@pytest.fixture
def multi_source_constitution_fixture(tmp_path: Path, git_binary: str) -> dict:
    """Publisher repo with two constitution molecules, plus a v3 consumer repo referencing both."""

    canonical = "https://github.com/example/multi-publisher"
    atom_id_a = "com.github.example.multi-publisher.atom-a"
    atom_id_b = "com.github.example.multi-publisher.atom-b"

    publisher = tmp_path / "publisher"
    publisher.mkdir()
    _init_repo(publisher)
    _git(publisher, "remote", "add", "origin", canonical)

    (publisher / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "3",
                "publisher": "com.github.example.multi-publisher",
                "molecules": {
                    atom_id_a: {"path": "atom-a", "version": "1.0.0"},
                    atom_id_b: {"path": "atom-b", "version": "1.0.0"},
                },
            },
            sort_keys=True,
        )
    )
    for path, atom_id, body in (
        ("atom-a", atom_id_a, b"# Constitution A\n\nBe kind.\n"),
        ("atom-b", atom_id_b, b"# Constitution B\n\nBe bold.\n"),
    ):
        atom_dir = publisher / path
        atom_dir.mkdir()
        (atom_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "haex_hive_version": "3",
                    "id": atom_id,
                    "version": "1.0.0",
                    "priority": 100,
                    "atoms": {"constitution": ["constitution.md"]},
                },
                sort_keys=True,
            )
        )
        (atom_dir / "constitution.md").write_bytes(body)
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "publish two constitution atoms")
    commit_sha = _git(publisher, "rev-parse", "HEAD")

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
                "haex_hive_version": "3",
                "identity": "com.github.example.consumer",
                "compounds": [
                    {
                        "source": canonical,
                        "revision": commit_sha,
                        "molecules": [atom_id_a, atom_id_b],
                    }
                ],
            },
            indent=2,
        )
    )

    return {
        "publisher": publisher,
        "consumer": consumer,
        "state_root": state_root,
        "commit_sha": commit_sha,
        "canonical": canonical,
        "atom_id_a": atom_id_a,
        "atom_id_b": atom_id_b,
    }
