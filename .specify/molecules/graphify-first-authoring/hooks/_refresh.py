"""Incremental refresh of ``graphify-out/`` for the post-commit hook.

Per contracts/git-hooks.md §post-commit and FR-006: run
``graphify update <repo-root>`` on the current working tree. On any failure
(non-zero exit, missing binary, timeout), warn to stderr and return normally —
**never** raise, so the calling hook can always exit 0 and the underlying
``git commit`` cannot be affected.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_TIMEOUT_SECONDS = 120


def refresh(repo_root: Path) -> bool:
    """Incrementally refresh ``graphify-out/`` for ``repo_root``.

    Returns ``True`` on success, ``False`` on any failure. A ``False`` return
    always coincides with a stderr warning; a ``True`` return leaves stderr
    untouched. Never raises.
    """
    # Keep the exact platform-resolved executable (for example graphify.EXE on
    # Windows) so subprocess receives the same command that PATH resolution
    # selected.
    binary = shutil.which("graphify")
    if binary is None:
        print(
            "graphify-first-authoring post-commit: 'graphify' not on PATH — "
            "skipping refresh (freshness marker will be caught on next agent use)",
            file=sys.stderr,
        )
        return False

    try:
        proc = subprocess.run(
            [binary, "update", str(repo_root)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(
            f"graphify-first-authoring post-commit: refresh timed out after "
            f"{_TIMEOUT_SECONDS}s — leaving graph stale",
            file=sys.stderr,
        )
        return False
    except OSError as exc:
        print(
            f"graphify-first-authoring post-commit: refresh could not start "
            f"({exc}) — leaving graph stale",
            file=sys.stderr,
        )
        return False

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        print(
            f"graphify-first-authoring post-commit: 'graphify update' exited "
            f"{proc.returncode} ({stderr_tail[0]}) — leaving graph stale",
            file=sys.stderr,
        )
        return False

    graph_path = repo_root / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        print(
            "graphify-first-authoring post-commit: 'graphify update' exited "
            "successfully but did not produce graphify-out/graph.json — "
            "leaving graph unavailable",
            file=sys.stderr,
        )
        return False

    try:
        head_proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=True,
        )
        head = head_proc.stdout.strip()
        if not head:
            raise OSError("git rev-parse HEAD returned no commit")
        meta_dir = graph_path.parent
        meta_dir.mkdir(parents=True, exist_ok=True)
        marker_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=meta_dir,
                prefix=".meta.",
                suffix=".tmp",
                delete=False,
            ) as marker:
                marker.write(json.dumps({"indexed_at_sha": head}) + "\n")
                marker.flush()
                os.fsync(marker.fileno())
                marker_path = Path(marker.name)
            os.replace(marker_path, meta_dir / ".meta.json")
            marker_path = None
        finally:
            if marker_path is not None:
                with contextlib.suppress(OSError):
                    marker_path.unlink()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(
            f"graphify-first-authoring post-commit: could not write freshness "
            f"marker ({exc}) — leaving graph stale",
            file=sys.stderr,
        )
        return False

    return True
