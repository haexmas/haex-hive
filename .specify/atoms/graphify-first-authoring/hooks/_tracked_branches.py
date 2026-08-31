"""Tracked-branch detection for the graphify-first-authoring atom.

Per research.md D4: the tracked-branch set is the repository's auto-detected
default branch (from ``git symbolic-ref refs/remotes/origin/HEAD``) merged with
any additional branch names declared in ``.haex-hive.json``'s optional
``tracked_branches[]`` array.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _repo_root(start: Path | None = None) -> Path | None:
    """Return the top-level of the git working tree containing ``start``.

    Uses ``git rev-parse --show-toplevel`` — the standard way to obtain the
    working-tree root from any subdirectory. Returns ``None`` if not inside a
    git repository.
    """
    cwd = start if start is not None else Path.cwd()
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    top = proc.stdout.strip()
    return Path(top) if top else None


def _default_branch(repo_root: Path) -> str | None:
    """Return the repo's default branch name, or ``None`` if undetectable.

    Reads ``refs/remotes/origin/HEAD`` — set by ``git clone`` (and refreshable
    via ``git remote set-head origin --auto``). Returns just the short branch
    name (e.g. ``main``), not the full ref.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    ref = proc.stdout.strip()
    prefix = "refs/remotes/origin/"
    if ref.startswith(prefix):
        return ref[len(prefix):]
    return None


def _configured_branches(repo_root: Path) -> list[str]:
    """Return ``tracked_branches[]`` from ``.haex-hive.json`` if present.

    Missing file, unparseable JSON, or a missing/non-list ``tracked_branches``
    field all yield an empty list — the caller must not depend on this raising.
    """
    config = repo_root / ".haex-hive.json"
    if not config.is_file():
        return []
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries = data.get("tracked_branches")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, str) and entry]


def tracked_branches(repo_root: Path | None = None) -> set[str]:
    """Return the set of tracked branch names for the current repo.

    Recomputes on every call — cheap enough that caching isn't warranted, and a
    cache would go stale if ``.haex-hive.json`` changes (data-model.md
    §TrackedBranchSet).
    """
    root = repo_root if repo_root is not None else _repo_root()
    if root is None:
        return set()
    result: set[str] = set()
    default = _default_branch(root)
    if default:
        result.add(default)
    result.update(_configured_branches(root))
    return result


def is_tracked(branch: str, repo_root: Path | None = None) -> bool:
    """Return ``True`` if ``branch`` is in the tracked-branch set."""
    if not branch:
        return False
    return branch in tracked_branches(repo_root)


def current_branch(repo_root: Path | None = None) -> str | None:
    """Return the currently checked-out branch name, or ``None`` if detached.

    ``git symbolic-ref --short HEAD`` returns the short branch name; on a
    detached HEAD it exits non-zero, in which case this returns ``None``.
    """
    root = repo_root if repo_root is not None else _repo_root()
    if root is None:
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    name = proc.stdout.strip()
    return name or None
