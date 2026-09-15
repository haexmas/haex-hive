"""Rollback coverage for the outer install generation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from spaex.cli import install


def test_behavior_failure_restores_previous_generation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    live = repo / ".spaex"
    live.mkdir(parents=True)
    (live / "install.lock").write_text("old generation", encoding="utf-8")
    resolved = [
        SimpleNamespace(
            molecule_manifest=SimpleNamespace(
                atoms={"behavior": ["fragment.md"]},
                constitution_fragments={},
            )
        )
    ]

    behavior_transaction = install._preserve_generation_for_behavior(repo, resolved)
    with pytest.raises(RuntimeError, match="composer failed"), behavior_transaction:
        (live / "install.lock").write_text("new generation", encoding="utf-8")
        raise RuntimeError("composer failed")

    assert (live / "install.lock").read_text(encoding="utf-8") == "old generation"


def test_behavior_failure_preserves_composer_log(tmp_path: Path) -> None:
    """`ComposerInvalidOutputError`'s hint sends the operator to
    `.spaex/composer.log` for the raw response. The rollback restores the
    pre-run `.spaex/` snapshot wholesale, so a log written *during* the
    failed attempt (a file the snapshot predates and never had) must not be
    thrown away along with it.
    """
    repo = tmp_path / "repo"
    live = repo / ".spaex"
    live.mkdir(parents=True)
    (live / "install.lock").write_text("old generation", encoding="utf-8")
    resolved = [
        SimpleNamespace(
            molecule_manifest=SimpleNamespace(
                atoms={"behavior": ["fragment.md"]},
                constitution_fragments={},
            )
        )
    ]

    behavior_transaction = install._preserve_generation_for_behavior(repo, resolved)
    with pytest.raises(RuntimeError, match="composer failed"), behavior_transaction:
        (live / "install.lock").write_text("new generation", encoding="utf-8")
        (live / "composer.log").write_text("raw response, no sentinel", encoding="utf-8")
        raise RuntimeError("composer failed")

    assert (live / "install.lock").read_text(encoding="utf-8") == "old generation"
    assert (live / "composer.log").read_text(encoding="utf-8") == (
        "raw response, no sentinel"
    )
