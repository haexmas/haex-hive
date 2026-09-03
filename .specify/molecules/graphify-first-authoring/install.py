"""Installer for the graphify-first-authoring molecule.

Contract: see specs/atoms/graphify-first-authoring/contracts/install.cli.md.

Refuses cleanly (no partial changes) if any precondition fails. On success:
- writes Git's effective hooks directory's ``post-commit`` and ``post-checkout``
  files with a shebang resolved to whichever of ``python3``/``python`` is present;
- copies the sibling helper modules into Git's effective hooks directory so the entrypoints'
  imports resolve regardless of where the atom lives on disk;
- appends ``graphify-out/`` to ``.gitignore`` if not already present;
- prompts before running ``graphify install`` when the local registration marker
  is absent, and records successful registration in local git config.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_ATOM_DIR = Path(__file__).resolve().parent
_HOOKS_SRC = _ATOM_DIR / "hooks"

if str(_HOOKS_SRC) not in sys.path:
    sys.path.insert(0, str(_HOOKS_SRC))

import _tracked_branches  # noqa: E402

_HOOK_NAMES = ("post-commit", "post-checkout")
_HELPER_MODULES = ("_tracked_branches.py", "_refresh.py", "_snapshot.py")
_GITIGNORE_LINE = "graphify-out/"
_REGISTRATION_CONFIG_KEY = "graphify-first-authoring.registration"
_REGISTRATION_CONFIG_VALUE = "installed"


class InstallError(Exception):
    """Precondition failure. Message is printed to stderr; exit code non-zero."""


def _resolve_interpreter() -> str:
    """Return an absolute path to a working Python interpreter, or raise.

    Per research.md D1 / FR-015: ``python3`` first (modern Linux, macOS,
    WSL2), then ``python`` (native Windows). No polyglot shell wrapper.
    """
    for candidate in ("python3", "python"):
        path = shutil.which(candidate)
        if path:
            return path
    raise InstallError(
        "No 'python3' or 'python' on PATH — install a Python 3 interpreter "
        "and re-run the installer."
    )


def _repo_root() -> Path:
    root = _tracked_branches._repo_root(Path.cwd())
    if root is None:
        raise InstallError("Not inside a git working tree — run this from a clone.")
    return root


def _check_current_branch_tracked(repo_root: Path) -> None:
    branch = _tracked_branches.current_branch(repo_root)
    tracked = _tracked_branches.tracked_branches(repo_root)
    if branch is None:
        raise InstallError(
            "HEAD is detached — check out a tracked branch before installing."
        )
    if branch not in tracked:
        expected = ", ".join(sorted(tracked)) if tracked else "<none detected>"
        raise InstallError(
            f"Current branch '{branch}' is not tracked (expected one of: {expected}). "
            "Check out a tracked branch or extend .haex-hive.json's tracked_branches[]."
        )


def _prompt(question: str, default_yes: bool = True) -> bool:
    """Yes/no prompt. ``default_yes=True`` accepts empty input as yes."""
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        answer = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default_yes
    if not answer:
        return default_yes
    return answer.startswith("y")


def _ensure_graphify_on_path() -> None:
    """FR-011: if ``graphify`` is absent, offer to ``pip install graphifyy``."""
    if shutil.which("graphify"):
        return
    proceed = _prompt(
        "graphify CLI not found. Install now via 'pip install graphifyy'?",
        default_yes=True,
    )
    if not proceed:
        raise InstallError(
            "graphify CLI is required — install it with 'pip install graphifyy' "
            "and re-run."
        )
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "graphifyy"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InstallError(
            f"'pip install graphifyy' failed (exit {exc.returncode}) — install "
            "the graphify CLI manually and re-run."
        ) from exc
    if not shutil.which("graphify"):
        raise InstallError(
            "'pip install graphifyy' completed but 'graphify' is still not on "
            "PATH — check your PATH and re-run."
        )


def _check_hook_collisions(hooks_dir: Path) -> None:
    for name in _HOOK_NAMES:
        target = hooks_dir / name
        if target.exists():
            raise InstallError(
                f"Hook '{target}' already exists from another tool. Integrate "
                "manually rather than overwriting."
            )


def _write_hook(hooks_dir: Path, name: str, interpreter: str) -> None:
    source = _HOOKS_SRC / name
    body = source.read_text(encoding="utf-8")
    target = hooks_dir / name
    target.write_text(f"#!{interpreter}\n{body}", encoding="utf-8")
    target.chmod(target.stat().st_mode | 0o111)


def _copy_helpers(hooks_dir: Path) -> None:
    for name in _HELPER_MODULES:
        shutil.copy2(_HOOKS_SRC / name, hooks_dir / name)


def _ensure_gitignore_line(repo_root: Path) -> None:
    """FR-017: add ``graphify-out/`` to ``.gitignore`` if not already present."""
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        if _GITIGNORE_LINE in {line.strip() for line in lines}:
            return
        with gitignore.open("a", encoding="utf-8") as fh:
            if lines and lines[-1] != "":
                fh.write("\n")
            fh.write(f"{_GITIGNORE_LINE}\n")
    else:
        gitignore.write_text(f"{_GITIGNORE_LINE}\n", encoding="utf-8")


def _maybe_run_graphify_install(repo_root: Path) -> None:
    """FR-012: run ``graphify install`` when local registration is unmarked.

    ``graphify install`` registers graphify with the operator's agent harness.
    A successful run records an explicit, unversioned marker in this clone's
    local git config. The graph cache itself is not a registration signal:
    bootstrap, refresh, and worktree snapshots can all create it independently.
    """
    try:
        registration = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "config",
                "--local",
                "--get",
                _REGISTRATION_CONFIG_KEY,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        registration = None

    if (
        registration is not None
        and registration.returncode == 0
        and registration.stdout.strip() == _REGISTRATION_CONFIG_VALUE
    ):
        print(
            "graphify harness registration marker is present — skipping "
            "'graphify install'."
        )
        return
    proceed = _prompt(
        "graphify-first-authoring needs graphify registered for your agent "
        "harness. Run `graphify install` now?",
        default_yes=True,
    )
    if not proceed:
        print(
            "Skipped 'graphify install'. Run it manually with "
            "'graphify install [--platform P]' when you are ready."
        )
        return
    print("Running graphify install (idempotent)…")
    try:
        subprocess.run(["graphify", "install"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"Warning: 'graphify install' did not complete cleanly ({exc}). "
            "Re-run it manually if your harness is not registered.",
            file=sys.stderr,
        )
        return

    try:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "config",
                "--local",
                _REGISTRATION_CONFIG_KEY,
                _REGISTRATION_CONFIG_VALUE,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        print(
            f"Warning: could not record the graphify registration marker ({exc}). "
            "The installer will ask again on the next run.",
            file=sys.stderr,
        )


def install() -> int:
    try:
        interpreter = _resolve_interpreter()
        repo_root = _repo_root()
        _check_current_branch_tracked(repo_root)
        hooks_result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            check=False,
        )
        if hooks_result.returncode != 0 or not hooks_result.stdout.strip():
            detail = hooks_result.stderr.strip() or "no path returned"
            raise InstallError(
                f"Could not resolve Git's effective hooks directory: {detail}"
            )
        hooks_dir = Path(hooks_result.stdout.strip())
        if not hooks_dir.is_absolute():
            hooks_dir = repo_root / hooks_dir
        hooks_dir = hooks_dir.resolve()
        _check_hook_collisions(hooks_dir)
        _ensure_graphify_on_path()
    except InstallError as exc:
        print(f"graphify-first-authoring: {exc}", file=sys.stderr)
        return 1

    hooks_dir.mkdir(parents=True, exist_ok=True)

    for name in _HOOK_NAMES:
        _write_hook(hooks_dir, name, interpreter)
    _copy_helpers(hooks_dir)
    _ensure_gitignore_line(repo_root)
    _maybe_run_graphify_install(repo_root)

    print(
        "graphify-first-authoring: installed post-commit and post-checkout "
        f"hooks in {hooks_dir} (interpreter: {interpreter})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(install())
