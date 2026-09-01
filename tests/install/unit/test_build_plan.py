"""T024 unit tests — plan-build entry point.

Uses the existing `single_source_constitution_fixture` from tests/conftest.py
because it already provides a real publisher git clone plus a v2 consumer
manifest. Under strict MVP scope only the constitution-only case ships.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from haex_hive.install.plan import (
    MultiSourceNotSupportedByBuildPlan,
    PlanBuildResult,
    PlanSnapshot,
    build_plan,
)
from haex_hive.util.errors import NoSourcesDeclaredError

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def test_build_plan_empty_manifest_refuses(tmp_path: Path) -> None:
    """A manifest with no atoms is a Principle V refusal, not an empty plan."""
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / ".haex-hive.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "identity": "com.example.consumer",
                "atoms": [],
            }
        )
    )
    with pytest.raises(NoSourcesDeclaredError):
        build_plan(consumer, tmp_path / "state")


def test_build_plan_single_source_emits_three_step_mvp_plan(
    single_source_constitution_fixture: dict,
) -> None:
    """The MVP plan is stage_file → seal_install_lock → publish_marker under `.haex-hive/`."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    result = build_plan(consumer, state_root)

    assert isinstance(result, PlanBuildResult)
    snapshot = result.snapshot
    assert isinstance(snapshot, PlanSnapshot)
    step_types = [step.step_type for step in snapshot.steps]
    assert step_types == ["stage_file", "seal_install_lock", "publish_marker"]
    for step in snapshot.steps:
        assert step.participating_root == ".haex-hive/"


def test_build_plan_single_source_records_input_digests(
    single_source_constitution_fixture: dict,
) -> None:
    """The sealed snapshot carries digests for `.haex-hive.json`, publisher, atom."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    result = build_plan(consumer, state_root)
    snapshot = result.snapshot

    assert snapshot.haex_hive_json_digest.startswith("sha256-")
    assert len(snapshot.publisher_manifest_digests) == 1
    assert len(snapshot.atom_manifest_digests) == 1
    assert snapshot.plan_snapshot_digest.startswith("sha256-")


def test_build_plan_single_source_returns_resolved_constitution_body(
    single_source_constitution_fixture: dict,
) -> None:
    """`PlanBuildResult.constitution` carries the resolved body for T026 to stage."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    result = build_plan(consumer, state_root)

    assert result.constitution.body == b"# Example Constitution\n\nBe kind.\n"
    assert result.constitution.source.id == single_source_constitution_fixture["atom_id"]
    assert (
        result.constitution.source.revision
        == single_source_constitution_fixture["commit_sha"]
    )


def test_build_plan_stage_file_payload_pins_constitution_digest(
    single_source_constitution_fixture: dict,
) -> None:
    """The stage_file payload records the digest of the constitution body."""
    import base64
    import hashlib

    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    result = build_plan(consumer, state_root)
    step_zero = result.snapshot.steps[0]
    body_digest = "sha256-" + base64.urlsafe_b64encode(
        hashlib.sha256(result.constitution.body).digest()
    ).rstrip(b"=").decode("ascii")

    assert step_zero.payload["path"] == "constitution.md"
    assert step_zero.payload["content_integrity"] == body_digest


def test_build_plan_multi_source_refuses(
    multi_source_constitution_fixture: dict,
) -> None:
    """Multi-source manifests are refused by the MVP build_plan."""
    consumer = multi_source_constitution_fixture["consumer"]
    state_root = multi_source_constitution_fixture["state_root"]

    with pytest.raises(MultiSourceNotSupportedByBuildPlan):
        build_plan(consumer, state_root)
