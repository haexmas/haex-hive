"""Regression tests for the PR #32 integrity review findings.

Note: the plan-snapshot, commit-snapshot, and per-root digest tests that
lived here were retired by the trust-git amendment (2026-09-01) together
with `install/plan.py` and `install/digest.py`, and the earlier journal
tests were retired by the R1/R7 amendment. Only the visibility-marker
collection-normalisation regression remains because `VisibilityMarker`
is still live.
"""

from __future__ import annotations

from haex_hive.install.visibility import VisibilityMarker


def test_visibility_collections_are_normalized_before_storage() -> None:
    """Visibility serialization is stable after caller-owned lists mutate."""
    roots = [".claude/"]
    marker = VisibilityMarker(
        generation_id="g_20260901T120000Z_abcd",
        participating_roots=roots,
    )
    roots.append(".codex/")

    assert marker.to_dict()["participating_roots"] == [".claude/"]
