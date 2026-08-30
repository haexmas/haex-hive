"""Shared fixtures for integration tests."""

from __future__ import annotations

import hashlib
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
