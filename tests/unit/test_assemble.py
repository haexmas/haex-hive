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


def test_publish_rejects_mismatched_published_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"# Constitution\n"
    source = ConstitutionSource(
        id="com.example.constitution",
        revision="0" * 40,
        source="https://example.com/publisher",
    )

    def corrupting_publish(
        repo_root: Path,
        constitution_body: bytes,
        install_lock_bytes: bytes,
        *,
        post_write_verify: object,
        visibility_body: bytes,
    ) -> None:
        hive_dir = repo_root / transaction.HAEX_HIVE_DIR
        hive_dir.mkdir()
        (hive_dir / transaction.CONSTITUTION_NAME).write_bytes(constitution_body)
        lock_data = json.loads(install_lock_bytes)
        lock_data["constitution"]["content_integrity"] = "sha256-" + "A" * 43 + "="
        (hive_dir / transaction.INSTALL_LOCK_NAME).write_text(json.dumps(lock_data))
        assert callable(post_write_verify)
        post_write_verify()

    monkeypatch.setattr(transaction, "publish_pair", corrupting_publish)

    with pytest.raises(PostWriteValidationError):
        _publish_constitution((source,), body, tmp_path, tool_version="2.0.0")


def test_multi_source_adapter_receives_contributions_in_stable_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
