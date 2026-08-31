"""Unit tests for the post-checkout snapshot logic (T015, FR-008)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import _snapshot  # noqa: E402
import pytest


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
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
    (graph / "graph.json").write_text('{"nodes": [], "edges": []}\n')
    (graph / "nodes.jsonl").write_text('{"id": "n1"}\n')

    child = tmp_path / "child"
    env = os.environ.copy()
    env[_snapshot._PARENT_WORKTREE_ENV] = str(parent)
    _git(parent, "worktree", "add", "-q", "-b", "feature/x", str(child), env=env)
    return parent, child


def test_copies_when_absent_locally(
    parent_with_graph: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child = parent_with_graph
    monkeypatch.setenv(_snapshot._PARENT_WORKTREE_ENV, str(parent))
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
    (existing / "graph.json").write_text('{"nodes": [], "edges": []}\n')
    marker = existing / "PREEXISTING"
    marker.write_text("keep me")

    assert _snapshot.snapshot(child) is False
    assert marker.read_text() == "keep me"
    assert not (existing / "nodes.jsonl").exists(), (
        "existing dir must never be overwritten"
    )


def test_replaces_incomplete_destination(
    parent_with_graph: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child = parent_with_graph
    monkeypatch.setenv(_snapshot._PARENT_WORKTREE_ENV, str(parent))
    existing = child / "graphify-out"
    existing.mkdir()
    (existing / ".meta.json").write_text("{}")

    assert _snapshot.snapshot(child) is True
    assert (existing / "graph.json").is_file()
    assert (existing / "nodes.jsonl").is_file()


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
    env = os.environ.copy()
    env[_snapshot._PARENT_WORKTREE_ENV] = str(parent)
    _git(parent, "worktree", "add", "-q", "-b", "feature/x", str(child), env=env)
    incomplete_graph = parent / "graphify-out"
    incomplete_graph.mkdir()
    (incomplete_graph / ".meta.json").write_text("{}")

    assert _snapshot.snapshot(child) is False
    assert not (child / "graphify-out").exists()


def test_noop_without_explicit_parent_signal(
    parent_with_graph: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, child = parent_with_graph
    graph = child / "graphify-out"
    assert not graph.exists()

    monkeypatch.delenv(_snapshot._PARENT_WORKTREE_ENV, raising=False)
    assert _snapshot.snapshot(child) is False
    assert not graph.exists()


def test_snapshot_never_raises_when_outside_git(tmp_path: Path) -> None:
    orphan = tmp_path / "not-a-repo"
    orphan.mkdir()
    _snapshot.snapshot(orphan)
