"""T062 — unit tests for `git.publisher_fetch` (Spec 013)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from haex_hive.git import publisher_fetch
from haex_hive.migrate.transform import clone_dir
from haex_hive.util.errors import RevisionNotFoundError, SourceUrlInvalidError


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _make_publisher(tmp_path: Path) -> tuple[Path, str, str]:
    """Return (bare_repo_path, head_sha, older_sha)."""
    working = tmp_path / "working"
    working.mkdir()
    _git(working, "init", "-q", "-b", "main")
    _git(working, "config", "user.email", "t@e")
    _git(working, "config", "user.name", "t")
    _git(working, "config", "commit.gpgsign", "false")
    (working / "a.txt").write_text("first\n")
    _git(working, "add", ".")
    _git(working, "commit", "-q", "-m", "first")
    older = _git(working, "rev-parse", "HEAD")
    (working / "a.txt").write_text("second\n")
    _git(working, "add", ".")
    _git(working, "commit", "-q", "-m", "second")
    head = _git(working, "rev-parse", "HEAD")

    bare = tmp_path / "publisher.git"
    subprocess.run(
        ["git", "clone", "--bare", "-q", str(working), str(bare)], check=True
    )
    return bare, head, older


def test_resolve_sha_uses_revision_verbatim() -> None:
    sha = "0" * 40
    assert (
        publisher_fetch.resolve_sha("https://github.com/example/publisher", sha) == sha
    )


def test_resolve_sha_refuses_non_40_hex_revision() -> None:
    with pytest.raises(RevisionNotFoundError):
        publisher_fetch.resolve_sha(
            "https://github.com/example/publisher", "not-a-sha"
        )


def test_resolve_sha_head_reads_git_ls_remote(tmp_path: Path) -> None:
    bare, head, _ = _make_publisher(tmp_path)
    resolved = publisher_fetch.resolve_sha(str(bare), None)
    assert resolved == head


def test_resolve_sha_head_refuses_unreachable_remote(tmp_path: Path) -> None:
    with pytest.raises(SourceUrlInvalidError):
        publisher_fetch.resolve_sha(
            str(tmp_path / "does-not-exist.git"), None
        )


def test_ensure_object_creates_clone_and_fetches_sha(tmp_path: Path) -> None:
    bare, head, older = _make_publisher(tmp_path)
    state_root = tmp_path / "state"
    repo_dir = publisher_fetch.ensure_object(str(bare), older, state_root)
    assert repo_dir.is_dir()
    # older is now available in the clone
    subprocess.run(
        ["git", "-C", str(repo_dir), "cat-file", "-e", older], check=True
    )
    assert repo_dir == clone_dir(state_root, str(bare))


def test_ensure_object_refuses_missing_sha(tmp_path: Path) -> None:
    bare, _, _ = _make_publisher(tmp_path)
    state_root = tmp_path / "state"
    with pytest.raises(RevisionNotFoundError):
        publisher_fetch.ensure_object(str(bare), "0" * 40, state_root)


def test_ensure_object_is_idempotent_for_present_sha(tmp_path: Path) -> None:
    bare, head, _ = _make_publisher(tmp_path)
    state_root = tmp_path / "state"
    repo_dir = publisher_fetch.ensure_object(str(bare), head, state_root)
    repo_dir_again = publisher_fetch.ensure_object(str(bare), head, state_root)
    assert repo_dir == repo_dir_again
