"""Tests for tracked-branch detection (T004, FR-007)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import _tracked_branches as tb  # noqa: E402
import pytest


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")


def _seed_origin_head(repo: Path, branch: str) -> None:
    """Simulate a clone-style ``origin/HEAD`` pointer without a real remote."""
    remotes = repo / ".git" / "refs" / "remotes" / "origin"
    remotes.mkdir(parents=True, exist_ok=True)
    (remotes / branch).write_text(_git(repo, "rev-parse", "HEAD") + "\n")
    (remotes / "HEAD").write_text(f"ref: refs/remotes/origin/{branch}\n")


@pytest.fixture
def repo_with_default(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_origin_head(repo, "main")
    return repo


def test_default_branch_only(repo_with_default: Path) -> None:
    branches = tb.tracked_branches(repo_with_default)
    assert branches == {"main"}
    assert tb.is_tracked("main", repo_with_default)
    assert not tb.is_tracked("feature/x", repo_with_default)


def test_config_merges_with_default(repo_with_default: Path) -> None:
    (repo_with_default / ".haex-hive.json").write_text(
        json.dumps({"tracked_branches": ["release/2026", "staging"]})
    )
    branches = tb.tracked_branches(repo_with_default)
    assert branches == {"main", "release/2026", "staging"}
    assert tb.is_tracked("release/2026", repo_with_default)
    assert tb.is_tracked("staging", repo_with_default)


def test_non_tracked_branch_returns_false(repo_with_default: Path) -> None:
    assert not tb.is_tracked("some-feature", repo_with_default)


def test_missing_haex_hive_json_is_graceful(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _seed_origin_head(repo, "main")
    assert not (repo / ".haex-hive.json").exists()
    branches = tb.tracked_branches(repo)
    assert branches == {"main"}


def test_empty_branch_never_tracked(repo_with_default: Path) -> None:
    assert not tb.is_tracked("", repo_with_default)


def test_malformed_config_treated_as_empty(repo_with_default: Path) -> None:
    (repo_with_default / ".haex-hive.json").write_text("{ not valid json")
    branches = tb.tracked_branches(repo_with_default)
    assert branches == {"main"}


def test_tracked_branches_field_not_a_list_is_ignored(repo_with_default: Path) -> None:
    (repo_with_default / ".haex-hive.json").write_text(
        json.dumps({"tracked_branches": "main"})
    )
    assert tb.tracked_branches(repo_with_default) == {"main"}


def test_no_origin_head_falls_back_to_config(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".haex-hive.json").write_text(
        json.dumps({"tracked_branches": ["trunk"]})
    )
    branches = tb.tracked_branches(repo)
    assert branches == {"trunk"}


def test_outside_repo_returns_empty(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert tb.tracked_branches(plain) == set()


def test_current_branch(repo_with_default: Path) -> None:
    assert tb.current_branch(repo_with_default) == "main"
