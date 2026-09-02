"""Stale-sibling cleanup before install (Spec 008, simplified §R7).

The 2026-09-02 detect+retry simplification retired the 8-state recovery
dispatcher. Under the current contract the rename-swap primitive gives
readers atomic visibility for free (they see either the pre-install
generation, no live directory, or the post-install generation — never a
mixed state), and `haex install` is deterministic and idempotent, so a
crashed install converges to a valid generation on the next invocation.

The only durable state we now inspect is: are there leftover
`<root>.next/` or `<root>.prev/` siblings from a prior crashed install?
If yes, delete them under the exclusive install lock, then let the
regular install pipeline run to completion. This matches the pip/npm
"detect + retry" model rather than the earlier journal-style
recovery-forward design.
"""

from __future__ import annotations

import os
import shutil
import sys
from contextlib import suppress
from pathlib import Path

_IS_WINDOWS = sys.platform == "win32"


def clean_stale_siblings(live: Path) -> tuple[bool, bool]:
    """Remove any leftover `<live>.next/` and `<live>.prev/` siblings.

    Returns `(next_removed, prev_removed)` so callers may log whether a
    prior invocation crashed mid-transaction. Safe to call unconditionally
    under the exclusive install lock; a no-op when neither sibling exists.
    """
    next_dir = live.with_name(f"{live.name}.next")
    prev_dir = live.with_name(f"{live.name}.prev")

    next_removed = next_dir.exists()
    prev_removed = prev_dir.exists()

    if next_removed:
        _rmtree(next_dir)
    if prev_removed:
        _rmtree(prev_dir)
    if next_removed or prev_removed:
        _fsync_dir(live.parent)

    return next_removed, prev_removed


def _rmtree(path: Path) -> None:
    with suppress(FileNotFoundError):
        shutil.rmtree(str(path))


def _fsync_dir(path: Path) -> None:
    if _IS_WINDOWS:
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
