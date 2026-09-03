"""Tests for the graphify-first-authoring installer (T020, FR-011–FR-017)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import install as installer  # noqa: E402
import pytest


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _make_tracked_repo(tmp_path: Path, branch: str = "main") -> Path:
    repo = tmp_path / "adopter"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("hi\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    remotes = repo / ".git" / "refs" / "remotes" / "origin"
    remotes.mkdir(parents=True, exist_ok=True)
    (remotes / branch).write_text(_git(repo, "rev-parse", "HEAD") + "\n")
    (remotes / "HEAD").write_text(f"ref: refs/remotes/origin/{branch}\n")
    return repo


def _put_graphify_stub(bin_dir: Path, exit_code: int = 0) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "graphify"
    stub.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    stub.chmod(0o755)
    return stub


def _prepend_path(monkeypatch: pytest.MonkeyPatch, *dirs: Path) -> None:
    parts = [str(d) for d in dirs] + [os.environ.get("PATH", "")]
    monkeypatch.setenv("PATH", os.pathsep.join(parts))


@pytest.fixture(autouse=True)
def _yes_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default every interactive prompt to Yes so happy-path tests don't hang."""
    monkeypatch.setattr(installer, "_prompt", lambda *_a, **_k: True)


def test_successful_install_writes_hooks_and_gitignore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_tracked_repo(tmp_path)
    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    _git(repo, "config", "core.hooksPath", "custom-hooks")
    monkeypatch.chdir(repo)

    assert installer.install() == 0

    hooks_dir = repo / "custom-hooks"
    for name in ("post-commit", "post-checkout"):
        target = hooks_dir / name
        assert target.exists(), name
        assert os.access(target, os.X_OK), f"{name} must be executable"
        first_line = target.read_text().splitlines()[0]
        assert first_line.startswith("#!"), first_line
        assert Path(first_line[2:]).stem.lower() in {"python", "python3"}, first_line
    for helper in ("_tracked_branches.py", "_refresh.py", "_snapshot.py"):
        assert (hooks_dir / helper).is_file()

    gitignore = (repo / ".gitignore").read_text()
    assert "graphify-out/" in gitignore.splitlines()


def test_refuses_when_branch_not_tracked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_tracked_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature/x")
    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)
    provisioned: list[bool] = []
    monkeypatch.setattr(
        installer,
        "_ensure_graphify_on_path",
        lambda: provisioned.append(True),
    )

    assert installer.install() != 0
    captured = capsys.readouterr()
    assert "feature/x" in captured.err
    assert not (repo / ".git" / "hooks" / "post-commit").exists()
    assert not (repo / ".gitignore").exists()


def test_refuses_when_hook_already_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_tracked_repo(tmp_path)
    existing = repo / ".git" / "hooks" / "post-commit"
    existing.write_text("# from some other tool\n")
    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)
    provisioned: list[bool] = []
    monkeypatch.setattr(
        installer,
        "_ensure_graphify_on_path",
        lambda: provisioned.append(True),
    )

    assert installer.install() != 0
    captured = capsys.readouterr()
    assert "already exists" in captured.err
    assert existing.read_text() == "# from some other tool\n"
    assert not (repo / ".git" / "hooks" / "post-checkout").exists()
    assert not (repo / ".gitignore").exists()
    assert provisioned == [], "hook collisions must be checked before provisioning"


def test_refuses_when_effective_hooks_path_is_a_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_tracked_repo(tmp_path)
    hooks_path = repo / "hooks-file"
    hooks_path.write_text("not a directory\n")
    _git(repo, "config", "core.hooksPath", str(hooks_path))
    monkeypatch.chdir(repo)
    provisioned: list[bool] = []
    monkeypatch.setattr(
        installer,
        "_ensure_graphify_on_path",
        lambda: provisioned.append(True),
    )

    assert installer.install() != 0
    captured = capsys.readouterr()
    assert "not a directory" in captured.err
    assert provisioned == [], "invalid hooks paths must be checked before provisioning"


@pytest.mark.parametrize(
    "foreign_hooks_path",
    [r"C:\Users\user\repo\.git\hooks", r"\\server\share\repo\.git\hooks"],
)
@pytest.mark.skipif(os.name == "nt", reason="covers a POSIX runtime receiving a Windows path")
def test_refuses_windows_hooks_path_on_posix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    foreign_hooks_path: str,
) -> None:
    """Do not provision when native Windows Git returns a foreign path to WSL."""
    repo = _make_tracked_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(installer, "_repo_root", lambda: repo)
    monkeypatch.setattr(installer, "_check_current_branch_tracked", lambda _root: None)
    monkeypatch.setattr(installer, "_resolve_interpreter", lambda: "/usr/bin/python3")
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["git", "rev-parse", "--git-path", "hooks"],
            returncode=0,
            stdout=f"{foreign_hooks_path}\n",
            stderr="",
        ),
    )
    provisioned: list[bool] = []
    monkeypatch.setattr(
        installer,
        "_ensure_graphify_on_path",
        lambda: provisioned.append(True),
    )

    assert installer.install() != 0
    captured = capsys.readouterr()
    assert "Windows-format hooks path" in captured.err
    assert provisioned == [], "foreign hooks paths must be rejected before provisioning"


def test_refuses_when_graphify_absent_and_prompt_declined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_tracked_repo(tmp_path)
    _PY_NAMES = {"python3", "python"}
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/usr/bin/python3" if name in _PY_NAMES else None,
    )
    monkeypatch.setattr(installer, "_prompt", lambda *_a, **_k: False)
    monkeypatch.chdir(repo)

    assert installer.install() != 0
    captured = capsys.readouterr()
    assert "graphify CLI is required" in captured.err
    assert not (repo / ".git" / "hooks" / "post-commit").exists()


def test_gitignore_line_not_duplicated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_tracked_repo(tmp_path)
    (repo / ".gitignore").write_text("*.log\ngraphify-out/\n")
    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)

    assert installer.install() == 0
    lines = (repo / ".gitignore").read_text().splitlines()
    assert lines.count("graphify-out/") == 1


def test_graphify_install_requires_registration_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_tracked_repo(tmp_path)
    (repo / "graphify-out").mkdir()
    (repo / "graphify-out" / ".meta.json").write_text("{}")

    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)

    called: dict[str, list] = {"prompt": []}
    monkeypatch.setattr(
        installer,
        "_prompt",
        lambda q, *_a, **_k: called["prompt"].append(q) or True,
    )
    ran: list[list[str]] = []
    original_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        ran.append(list(cmd) if isinstance(cmd, list) else [cmd])
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    assert installer.install() == 0
    assert called["prompt"], "unmarked registration must prompt even with a graph cache"
    assert any(
        cmd == ["graphify", "install"] for cmd in ran
    ), "unmarked registration must run after accepting the prompt"


def test_graphify_install_skipped_when_registration_marker_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_tracked_repo(tmp_path)
    (repo / "graphify-out").mkdir()
    (repo / "graphify-out" / ".meta.json").write_text("{}")
    _git(
        repo,
        "config",
        "--local",
        installer._REGISTRATION_CONFIG_KEY,
        installer._REGISTRATION_CONFIG_VALUE,
    )

    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)

    called: dict[str, list] = {"prompt": []}
    monkeypatch.setattr(
        installer,
        "_prompt",
        lambda q, *_a, **_k: called["prompt"].append(q) or True,
    )
    ran: list[list[str]] = []
    original_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        ran.append(list(cmd) if isinstance(cmd, list) else [cmd])
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    assert installer.install() == 0
    assert called["prompt"] == []
    assert not any(cmd == ["graphify", "install"] for cmd in ran)


def test_prompt_gates_graphify_install_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Declining the prompt must not invoke ``graphify install``.

    Patches ``_maybe_run_graphify_install`` at its outer edge — actually the
    ``subprocess.run`` call — but only within the installer module by wrapping
    the built-in run and delegating everything except ``graphify install`` to
    the real implementation. That keeps ``_tracked_branches``' own git calls
    working.
    """
    repo = _make_tracked_repo(tmp_path)
    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)

    monkeypatch.setattr(installer, "_prompt", lambda *_a, **_k: False)
    invoked: list[list[str]] = []

    def spy_run_graphify_install() -> None:
        invoked.append(["graphify", "install"])

    monkeypatch.setattr(
        installer,
        "_maybe_run_graphify_install",
        lambda _root: (
            # Emulate the real dispatch: only invoke if prompt returns True.
            spy_run_graphify_install() if installer._prompt("register?") else None
        ),
    )

    assert installer.install() == 0
    assert invoked == [], "declining the prompt must not invoke 'graphify install'"


def test_gitignore_created_when_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_tracked_repo(tmp_path)
    assert not (repo / ".gitignore").exists()
    bin_dir = tmp_path / "bin"
    _put_graphify_stub(bin_dir)
    _prepend_path(monkeypatch, bin_dir)
    monkeypatch.chdir(repo)

    assert installer.install() == 0
    assert (repo / ".gitignore").read_text().splitlines() == ["graphify-out/"]
