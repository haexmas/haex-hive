"""Regression coverage for constitution publication validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haex_hive.constitution import assemble
from haex_hive.constitution.assemble import _publish_constitution
from haex_hive.constitution.llm import MergeResult
from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.io import transaction
from haex_hive.model.install_lock import ConstitutionSource
from haex_hive.util.errors import PostWriteValidationError


def test_publish_rejects_mismatched_published_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject publication when the persisted lock generation is corrupted."""
    body = b"# Constitution\n"
    source = ConstitutionSource(
        id="com.example.constitution",
        revision="0" * 40,
        source="https://example.com/publisher",
    )

    def corrupting_publish(
        live: Path,
        files,
        *,
        post_write_verify,
        state_root=None,
        repo_root=None,
    ) -> None:
        del state_root, repo_root
        live.mkdir(parents=True, exist_ok=True)
        for staged in files:
            if staged.relative_path == transaction.INSTALL_LOCK_NAME:
                data = json.loads(staged.data)
                data["visibility_marker"]["generation_id"] = "g_20260101T000000Z_dead"
                (live / staged.relative_path).write_text(json.dumps(data))
            else:
                (live / staged.relative_path).write_bytes(staged.data)
        assert callable(post_write_verify)
        post_write_verify()

    monkeypatch.setattr(transaction, "publish_generation", corrupting_publish)

    with pytest.raises(PostWriteValidationError):
        _publish_constitution((source,), body, tmp_path, tool_version="2.0.0")


def test_multi_source_adapter_receives_contributions_in_stable_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pass multi-source contributions to adapters in stable ID order."""
    contributions = [
        ResolvedConstitutionContribution(
            source=ConstitutionSource(
                id="com.example.z", revision="1" * 40, source="https://example.com/z"
            ),
            body=b"z",
        ),
        ResolvedConstitutionContribution(
            source=ConstitutionSource(
                id="com.example.a", revision="0" * 40, source="https://example.com/a"
            ),
            body=b"a",
        ),
    ]
    received_ids: list[str] = []

    class RecordingAdapter:
        def merge(self, ordered, task_prompt: str) -> MergeResult:
            received_ids.extend(c.source.id for c in ordered)
            return MergeResult(candidate=b"# merged\n", confirmed=True)

    monkeypatch.setattr(assemble, "_select_adapter", lambda method, root: RecordingAdapter())
    monkeypatch.setattr(assemble, "_publish_constitution", lambda *args, **kwargs: None)

    assert (
        assemble.assemble_multi_source(
            contributions,
            tmp_path,
            llm_method="stdio",
            accept_merged_path=None,
            tool_version="2.0.0",
        )
        == 0
    )
    assert received_ids == ["com.example.a", "com.example.z"]
