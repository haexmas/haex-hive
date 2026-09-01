"""In-flight recovery state dispatcher (T042, research §R7).

The install transaction's durable state is encoded in the presence/absence of
three same-filesystem sibling directories beside each participating output
root — `<root>/` (live), `<root>.next/` (staged, verified, awaiting swap),
`<root>.prev/` (retained pre-image during the swap). Recovery reads that
combination and dispatches per §R7's state table.

Every legal combination has a deterministic recovery action; three
combinations are integrity failures that require operator attention.
"""

from __future__ import annotations

import enum
import os
import shutil
import sys
from contextlib import suppress
from pathlib import Path

_IS_WINDOWS = sys.platform == "win32"


class InflightState(enum.Enum):
    """One of the eight §R7 recovery-state combinations."""

    STEADY = "steady"                # only <root>/ — no in-flight install
    UNINITIALIZED = "uninitialized"  # none of the three — first install
    PRE_SWAP = "pre_swap"            # <root>/ + <root>.next/; abort before rename A
    MID_SWAP = "mid_swap"            # <root>.next/ + <root>.prev/; complete forward
    POST_SWAP = "post_swap"          # <root>/ + <root>.prev/; cleanup .prev
    ORPHAN_PREV = "orphan_prev"      # only <root>.prev/ — integrity failure
    ILLEGAL_ALL = "illegal_all"      # all three — integrity failure
    ORPHAN_NEXT = "orphan_next"      # only <root>.next/ — integrity failure


class InflightIntegrityError(RuntimeError):
    """Raised when the R7 state table yields an integrity-failure row."""

    def __init__(self, state: InflightState, live: Path) -> None:
        self.state = state
        self.live = live
        super().__init__(
            f"install in-flight recovery integrity failure at {live!s}: {state.value}"
        )


def _paths(live: Path) -> tuple[Path, Path]:
    parent = live.parent
    name = live.name
    return parent / f"{name}.next", parent / f"{name}.prev"


def inspect(live: Path) -> InflightState:
    """Return the §R7 state without side effects."""
    next_dir, prev_dir = _paths(live)
    return _classify(
        live_exists=live.exists(),
        next_exists=next_dir.exists(),
        prev_exists=prev_dir.exists(),
    )


def _classify(*, live_exists: bool, next_exists: bool, prev_exists: bool) -> InflightState:
    match (live_exists, next_exists, prev_exists):
        case (True, False, False):
            return InflightState.STEADY
        case (False, False, False):
            return InflightState.UNINITIALIZED
        case (True, True, False):
            return InflightState.PRE_SWAP
        case (False, True, True):
            return InflightState.MID_SWAP
        case (True, False, True):
            return InflightState.POST_SWAP
        case (False, False, True):
            return InflightState.ORPHAN_PREV
        case (True, True, True):
            return InflightState.ILLEGAL_ALL
        case (False, True, False):
            return InflightState.ORPHAN_NEXT
    raise AssertionError("unreachable: three booleans exhaust to 8 rows")


def resolve(live: Path) -> InflightState:
    """Inspect the R7 state and perform the prescribed recovery action.

    Returns the observed state so callers can log/telemeter it. Steady and
    uninitialized are no-ops. Pre-swap deletes `<root>.next/`. Mid-swap
    completes forward (`os.rename(<root>.next, <root>)` then removes
    `<root>.prev`). Post-swap removes `<root>.prev`. The three integrity-
    failure rows raise `InflightIntegrityError`; the operator resolves them
    manually (usually by inspecting the on-disk content and picking which
    sibling to keep).
    """
    state = inspect(live)
    next_dir, prev_dir = _paths(live)
    parent = live.parent
    if state is InflightState.STEADY or state is InflightState.UNINITIALIZED:
        return state
    if state is InflightState.PRE_SWAP:
        _rmtree(next_dir)
        _fsync_dir(parent)
        return state
    if state is InflightState.MID_SWAP:
        os.rename(str(next_dir), str(live))
        _fsync_dir(parent)
        _rmtree(prev_dir)
        _fsync_dir(parent)
        return state
    if state is InflightState.POST_SWAP:
        _rmtree(prev_dir)
        _fsync_dir(parent)
        return state
    raise InflightIntegrityError(state, live)


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
