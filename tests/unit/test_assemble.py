"""Regression coverage for constitution publication validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haex_hive.constitution.assemble import _publish_constitution
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
