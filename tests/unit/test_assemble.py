"""Regression coverage for constitution publication validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haex_hive.constitution import assemble
from haex_hive.constitution.assemble import _publish_constitution
from haex_hive.constitution.llm import MergeResult, generation_input_identities
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


def test_publish_allocates_generation_id_after_existing_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every publication receives a fresh generation ID after the live one."""
    live = tmp_path / transaction.HAEX_HIVE_DIR
    live.mkdir()
    existing_generation_id = "g_20990101T000000Z_0000"
    (live / transaction.INSTALL_LOCK_NAME).write_bytes(
        json.dumps(
            {
                "haex_hive_version": "3",
                "generated_by": "haex 2.0.0",
                "constitution": {
                    "sources": [
                        {
                            "id": "com.example.constitution",
                            "revision": "0" * 40,
                            "source": "https://example.com/publisher",
                        }
                    ],
                    "assembled_by": {"tool": "haex", "version": "2.0.0"},
                },
                "participating_roots": [".haex-hive/"],
                "visibility_marker": {"generation_id": existing_generation_id},
            }
        ).encode()
    )
    captured: dict = {}

    def capture_publish(live_dir, files, **kwargs) -> None:
        del live_dir, kwargs
        for staged in files:
            if staged.relative_path == transaction.INSTALL_LOCK_NAME:
                captured.update(json.loads(staged.data))

    monkeypatch.setattr(transaction, "publish_generation", capture_publish)
    _publish_constitution(
        (
            ConstitutionSource(
                id="com.example.constitution",
                revision="0" * 40,
                source="https://example.com/publisher",
            ),
        ),
        b"# New Constitution\n",
        tmp_path,
        tool_version="2.0.0",
    )

    new_generation_id = captured["visibility_marker"]["generation_id"]
    assert new_generation_id != existing_generation_id
    assert new_generation_id > existing_generation_id


def test_generation_input_profiles_match_payload_formats() -> None:
    """Pin adapter text and compact tool-config JSON with distinct profiles."""
    adapter, tool_config = generation_input_identities("stdio", "merge")
    assert adapter.serialization["format"] == "text"
    assert adapter.serialization["key_order"] == "not-applicable"
    assert tool_config.serialization["format"] == "json"
    assert tool_config.serialization["key_order"] == "lexicographic-utf8"
    assert tool_config.serialization["indent"] is None


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


def test_multi_source_publishes_pinned_generation_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pass confirmed adapter identities into the published lock."""
    contributions = [
        ResolvedConstitutionContribution(
            source=ConstitutionSource(
                id="com.example.a", revision="0" * 40, source="https://example.com/a"
            ),
            body=b"a",
        ),
        ResolvedConstitutionContribution(
            source=ConstitutionSource(
                id="com.example.b", revision="1" * 40, source="https://example.com/b"
            ),
            body=b"b",
        ),
    ]
    captured: dict = {}

    class RecordingAdapter:
        def merge(self, ordered, task_prompt: str) -> MergeResult:
            del ordered, task_prompt
            return MergeResult(
                candidate=b"# merged\n",
                confirmed=True,
                generation_inputs=assemble.generation_input_identities(
                    "test", "merge"
                ),
            )

    def capture_publish(*args, **kwargs) -> None:
        del args
        captured.update(kwargs)

    monkeypatch.setattr(assemble, "_select_adapter", lambda method, root: RecordingAdapter())
    monkeypatch.setattr(assemble, "_publish_constitution", capture_publish)

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
    identities = captured["generation_inputs"]
    assert [(item.kind, item.id) for item in identities] == sorted(
        (item.kind, item.id) for item in identities
    )
    assert {item.kind for item in identities} == {"adapter", "tool-config"}
