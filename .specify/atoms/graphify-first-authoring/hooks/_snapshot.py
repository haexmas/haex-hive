"""Fork-point snapshot of ``graphify-out/`` for the post-checkout hook.

Per contracts/git-hooks.md §post-checkout and FR-008: when a new worktree is
created with ``GRAPHIFY_PARENT_WORKTREE`` set to its parent, copy that
parent's complete ``graphify-out/``
(including ``graph.json``) into the new one so the feature branch sees a
correct fork-point graph immediately. Never overwrite an existing
complete ``graphify-out/`` in the new worktree. An incomplete destination is
treated as absent and replaced once a complete parent graph is available.
Never raise — warn to stderr on any failure, so the calling hook can always
exit 0 and the underlying ``git worktree add``/``git checkout`` cannot be
affected.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

_PARENT_WORKTREE_ENV = "GRAPHIFY_PARENT_WORKTREE"


def _parent_worktree(current: Path) -> Path | None:
    """Return the explicit source worktree selected for this checkout.

    Git's ``post-checkout`` hook receives no source-worktree path. The supported
    worktree creation path therefore passes ``GRAPHIFY_PARENT_WORKTREE`` and
    this function validates that path against the repository's registered
    worktrees instead of guessing from list order.
    """
    source_value = os.environ.get(_PARENT_WORKTREE_ENV)
    if not source_value:
        return None

    source = Path(source_value).expanduser().resolve()
    if source == current.resolve():
        return None

    try:
        proc = subprocess.run(
            ["git", "-C", str(current), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            registered = Path(line[len("worktree "):].strip()).resolve()
            if registered == source:
                return source
    return None


def snapshot(current_worktree: Path) -> bool:
    """Copy the explicitly selected parent graph into ``current_worktree``.

    Returns ``True`` if a copy was performed, ``False`` on any no-op or
    failure. A ``False`` return is silent when the situation is a legitimate
    no-op (destination exists, no parent, parent has no complete graph) and
    warns to stderr only on genuine failure (a partial copy that had to be
    rolled back). Without ``GRAPHIFY_PARENT_WORKTREE`` or with an unregistered
    source, it is a silent no-op so the agent-side backstop can handle it. An
    incomplete destination directory is removed only after a complete parent
    graph has been found. Never raises.
    """
    dest = current_worktree / "graphify-out"
    if dest.exists() and (
        not dest.is_dir() or (dest / "graph.json").is_file()
    ):
        return False

    parent = _parent_worktree(current_worktree)
    if parent is None:
        return False

    source = parent / "graphify-out"
    if not source.is_dir() or not (source / "graph.json").is_file():
        return False

    try:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest, symlinks=False)
    except OSError as exc:
        print(
            f"graphify-first-authoring post-checkout: snapshot failed ({exc}) — "
            "leaving graphify-out/ absent (agent bootstrap will handle it)",
            file=sys.stderr,
        )
        if dest.exists():
            with contextlib.suppress(OSError):
                shutil.rmtree(dest)
        return False

    return True
