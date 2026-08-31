"""Integration test for the installed post-checkout hook (T016, FR-008)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ATOM_HOOKS = _REPO_ROOT / ".specify" / "atoms" / "graphify-first-authoring" / "hooks"


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return proc.stdout.strip()


def _init_parent(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("hi\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    graph = root / "graphify-out"
    graph.mkdir()
    (graph / ".meta.json").write_text(
        json.dumps({"indexed_at_sha": _git(root, "rev-parse", "HEAD")})
    )
    (graph / "graph.json").write_text('{"nodes": [], "edges": []}\n')
    (graph / "nodes.jsonl").write_text('{"id": "n1"}\n')
    return root


def _install_post_checkout_hook_globally(parent_repo: Path, interpreter: str) -> Path:
    """Install the atom's post-checkout hook and its sibling modules.

    Places them in the parent repo's ``.git/hooks/``. When ``git worktree add``
    creates a new worktree, that new worktree shares this ``.git/hooks/``
    directory (git uses per-repo hook config, not per-worktree), so the hook
    fires there too.
    """
    hooks_dir = parent_repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "post-checkout"
    body = (_ATOM_HOOKS / "post-checkout").read_text(encoding="utf-8")
    target.write_text(f"#!{interpreter}\n{body}", encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    for name in ("_snapshot.py", "_tracked_branches.py", "_refresh.py"):
        shutil.copy2(_ATOM_HOOKS / name, hooks_dir / name)
    return target


@pytest.fixture
def parent_repo_with_hook(tmp_path: Path) -> Path:
    parent = _init_parent(tmp_path / "parent")
    _install_post_checkout_hook_globally(parent, sys.executable)
    return parent


def test_worktree_add_triggers_snapshot_copy(
    parent_repo_with_hook: Path,
    tmp_path: Path,
) -> None:
    child = tmp_path / "child"
    env = os.environ.copy()
    env["GRAPHIFY_PARENT_WORKTREE"] = str(parent_repo_with_hook)
    _git(
        parent_repo_with_hook,
        "worktree",
        "add",
        "-q",
        "-b",
        "feature/x",
        str(child),
        env=env,
    )

    child_graph = child / "graphify-out"
    assert child_graph.is_dir(), (
        "post-checkout hook should have populated the new worktree's graphify-out/"
    )
    meta = child_graph / ".meta.json"
    assert meta.is_file()
    parent_head = _git(parent_repo_with_hook, "rev-parse", "HEAD")
    assert json.loads(meta.read_text())["indexed_at_sha"] == parent_head


def test_worktree_add_from_linked_worktree_uses_that_parent(
    parent_repo_with_hook: Path,
    tmp_path: Path,
) -> None:
    linked = tmp_path / "linked"
    main_env = os.environ.copy()
    main_env["GRAPHIFY_PARENT_WORKTREE"] = str(parent_repo_with_hook)
    _git(
        parent_repo_with_hook,
        "worktree",
        "add",
        "-q",
        "-b",
        "linked/x",
        str(linked),
        env=main_env,
    )
    linked_marker = linked / "graphify-out" / ".meta.json"
    linked_marker.write_text('{"indexed_at_sha": "linked-parent"}\n')

    child = tmp_path / "child-from-linked"
    linked_env = os.environ.copy()
    linked_env["GRAPHIFY_PARENT_WORKTREE"] = str(linked)
    _git(
        linked,
        "worktree",
        "add",
        "-q",
        "-b",
        "feature/from-linked",
        str(child),
        env=linked_env,
    )

    assert json.loads(
        (child / "graphify-out" / ".meta.json").read_text()
    )["indexed_at_sha"] == "linked-parent"


def test_hook_exits_zero_when_snapshot_would_fail(
    tmp_path: Path,
) -> None:
    """Simulate a snapshot failure via a corrupted source and verify the
    installed hook still exits 0 — the shared-failure principle in
    contracts/git-hooks.md ("Neither hook may make a git operation fail on its
    own account") is enforceable only if MY hook itself always exits 0.
    """
    parent = _init_parent(tmp_path / "parent")
    _install_post_checkout_hook_globally(parent, sys.executable)

    child = tmp_path / "child"
    env = os.environ.copy()
    env["GRAPHIFY_PARENT_WORKTREE"] = str(parent)
    _git(
        parent,
        "worktree",
        "add",
        "-q",
        "-b",
        "feature/x",
        str(child),
        env=env,
    )
    shutil.rmtree(child / "graphify-out")

    # Turn parent's graphify-out/ into an invalid source so the hook no-ops.
    graph = parent / "graphify-out"
    for child_path in graph.iterdir():
        child_path.unlink()
    graph.rmdir()
    graph.write_text("not a directory")

    hook = parent / ".git" / "hooks" / "post-checkout"

    # Invoke the hook directly with git's post-checkout argv: prev, new, flag=1.
    proc = subprocess.run(
        [sys.executable, str(hook), "0" * 40, "1" * 40, "1"],
        capture_output=True,
        text=True,
        cwd=str(child),
        env=env,
    )
    assert proc.returncode == 0, (
        f"hook must exit 0 even when its underlying snapshot fails; "
        f"got {proc.returncode}, stderr={proc.stderr}"
    )
