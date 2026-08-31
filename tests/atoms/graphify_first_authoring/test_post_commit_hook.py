"""Integration test for the installed post-commit hook (T012, FR-006).

Uses a scratch git repo and a shell-script ``graphify`` stub to verify the hook
runs the refresh on a tracked branch and writes a matching ``indexed_at_sha``.
The scratch repo is created from scratch — no dependency on this repo's actual
graphify installation.
"""

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


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
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
    remotes = repo / ".git" / "refs" / "remotes" / "origin"
    remotes.mkdir(parents=True, exist_ok=True)
    (remotes / "main").write_text(_git(repo, "rev-parse", "HEAD") + "\n")
    (remotes / "HEAD").write_text("ref: refs/remotes/origin/main\n")


def _install_hook(repo: Path, interpreter: str) -> None:
    hook_target = repo / ".git" / "hooks" / "post-commit"
    hook_source = _ATOM_HOOKS / "post-commit"
    body = hook_source.read_text(encoding="utf-8")
    hook_target.write_text(f"#!{interpreter}\n{body}", encoding="utf-8")
    hook_target.chmod(hook_target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    # Copy the sibling modules so the hook's ``import`` calls resolve — the
    # installer normally leaves them where they are and points ``sys.path`` at
    # the atom directory, but in tests we materialize them alongside the hook
    # to avoid depending on the atom being installed at a stable location.
    for name in ("_tracked_branches.py", "_refresh.py"):
        shutil.copy2(_ATOM_HOOKS / name, repo / ".git" / "hooks" / name)


def _make_graphify_stub(bin_dir: Path, meta_target_repo: Path) -> Path:
    """Install a cross-platform graphify stub that writes the freshness marker."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    implementation = bin_dir / "graphify_stub.py"
    implementation.write_text(
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "if len(sys.argv) > 2 and sys.argv[1] == 'update':\n"
        "    target_repo = Path(sys.argv[2])\n"
        "    meta_dir = target_repo / 'graphify-out'\n"
        "    meta_dir.mkdir(parents=True, exist_ok=True)\n"
        "    sha = subprocess.check_output(\n"
        "        ['git', '-C', str(target_repo), 'rev-parse', 'HEAD'],\n"
        "        text=True,\n"
        "    ).strip()\n"
        "    (meta_dir / '.meta.json').write_text(\n"
        "        json.dumps({'indexed_at_sha': sha}) + '\\n'\n"
        "    )\n"
    )
    if os.name == "nt":
        stub = bin_dir / "graphify.cmd"
        stub.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "%~dp0graphify_stub.py" %*\r\n'
        )
    else:
        stub = bin_dir / "graphify"
        stub.write_text(
            "#!/bin/sh\n"
            f'exec "{sys.executable}" "$(dirname "$0")/graphify_stub.py" "$@"\n'
        )
        stub.chmod(0o755)
    return stub


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    return repo


def test_post_commit_hook_refreshes_graph_on_tracked_branch(
    scratch_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    stub = _make_graphify_stub(bin_dir, scratch_repo)
    _install_hook(scratch_repo, sys.executable)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

    (scratch_repo / "next.txt").write_text("new content\n")
    _git(scratch_repo, "add", ".", env=env)
    _git(scratch_repo, "commit", "-q", "-m", "advance", env=env)

    head = _git(scratch_repo, "rev-parse", "HEAD")
    meta = scratch_repo / "graphify-out" / ".meta.json"
    assert meta.is_file(), "graphify-out/.meta.json was not written by the hook"
    assert json.loads(meta.read_text())["indexed_at_sha"] == head
    assert stub.exists()


def test_post_commit_hook_is_noop_on_untracked_branch(
    scratch_repo: Path,
    tmp_path: Path,
) -> None:
    _install_hook(scratch_repo, sys.executable)

    bin_dir = tmp_path / "bin"
    _make_graphify_stub(bin_dir, scratch_repo)

    _git(scratch_repo, "checkout", "-q", "-b", "feature/x")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

    (scratch_repo / "next.txt").write_text("new\n")
    _git(scratch_repo, "add", ".", env=env)
    _git(scratch_repo, "commit", "-q", "-m", "on feature", env=env)

    assert not (scratch_repo / "graphify-out").exists(), (
        "hook must not touch the graph on a non-tracked branch"
    )


def test_post_commit_hook_never_blocks_commit_on_refresh_failure(
    scratch_repo: Path,
    tmp_path: Path,
) -> None:
    _install_hook(scratch_repo, sys.executable)

    bin_dir = tmp_path / "bin"
    stub = bin_dir / "graphify"
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

    (scratch_repo / "boom.txt").write_text("x\n")
    _git(scratch_repo, "add", ".", env=env)
    proc = subprocess.run(
        ["git", "-C", str(scratch_repo), "commit", "-q", "-m", "should succeed"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, (
        "commit must succeed even when the refresh hook fails; "
        f"stderr={proc.stderr}"
    )
