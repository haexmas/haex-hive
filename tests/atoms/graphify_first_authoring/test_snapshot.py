"""Unit tests for the post-checkout snapshot logic (T015, FR-008)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import _snapshot  # noqa: E402
import pytest


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


@pytest.fixture
def parent_with_graph(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(parent_worktree, prepared_child_dir)``.

    The parent is a real git repo with a populated ``graphify-out/``; the child
    is a fresh worktree already registered with git (so ``git worktree list``
    reports both). The child does **not** yet have ``graphify-out/`` — that is
    what the snapshot fixture leaves for the test itself to trigger.
    """
    parent = tmp_path / "parent"
    parent.mkdir()
    _git(parent, "init", "-q", "-b", "main")
    _git(parent, "config", "user.email", "t@t.t")
    _git(parent, "config", "user.name", "t")
    _git(parent, "config", "commit.gpgsign", "false")
    (parent / "README.md").write_text("hi\n")
    _git(parent, "add", ".")
    _git(parent, "commit", "-q", "-m", "init")

    graph = parent / "graphify-out"
    graph.mkdir()
    (graph / ".meta.json").write_text(
        json.dumps({"indexed_at_sha": _git(parent, "rev-parse", "HEAD")})
    )
    (graph / "nodes.jsonl").write_text('{"id": "n1"}\n')

    child = tmp_path / "child"
    _git(parent, "worktree", "add", "-q", "-b", "feature/x", str(child))
    return parent, child


def test_copies_when_absent_locally(parent_with_graph: tuple[Path, Path]) -> None:
    parent, child = parent_with_graph
    assert not (child / "graphify-out").exists()
    assert _snapshot.snapshot(child) is True
    assert (child / "graphify-out" / ".meta.json").is_file()
    assert (child / "graphify-out" / "nodes.jsonl").is_file()
    meta = json.loads((child / "graphify-out" / ".meta.json").read_text())
    parent_head = _git(parent, "rev-parse", "HEAD")
    assert meta["indexed_at_sha"] == parent_head


def test_noop_when_already_present(parent_with_graph: tuple[Path, Path]) -> None:
    _, child = parent_with_graph
    existing = child / "graphify-out"
    existing.mkdir()
    marker = existing / "PREEXISTING"
    marker.write_text("keep me")

    assert _snapshot.snapshot(child) is False
    assert marker.read_text() == "keep me"
    assert not (existing / "nodes.jsonl").exists(), (
        "existing dir must never be overwritten"
    )


def test_noop_when_parent_has_no_graph(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    _git(parent, "init", "-q", "-b", "main")
    _git(parent, "config", "user.email", "t@t.t")
    _git(parent, "config", "user.name", "t")
    _git(parent, "config", "commit.gpgsign", "false")
    (parent / "README.md").write_text("hi\n")
    _git(parent, "add", ".")
    _git(parent, "commit", "-q", "-m", "init")

    child = tmp_path / "child"
    _git(parent, "worktree", "add", "-q", "-b", "feature/x", str(child))
    assert not (parent / "graphify-out").exists()

    assert _snapshot.snapshot(child) is False
    assert not (child / "graphify-out").exists()


def test_snapshot_never_raises_when_outside_git(tmp_path: Path) -> None:
    orphan = tmp_path / "not-a-repo"
    orphan.mkdir()
    _snapshot.snapshot(orphan)
