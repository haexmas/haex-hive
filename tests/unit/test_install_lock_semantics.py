"""FR-030 semantic check on `constitution.sources[]` uniqueness + sort."""

from __future__ import annotations

import json

import pytest

from haex_hive.model.install_lock import InstallLock
from haex_hive.util.errors import (
    InstallLockSchemaInvalidError,
    InstallLockSourcesNotCanonicalError,
)

_BASE = {
    "haex_hive_version": "2",
    "generated_by": "haex 2.0.0",
    "constitution": {
        "sources": [],
        "assembled_by": {"tool": "haex", "version": "2.0.0"},
        "content_integrity": "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    },
}


def _payload(sources: list[dict]) -> bytes:
    """Build an install lock payload containing the supplied sources."""
    data = json.loads(json.dumps(_BASE))
    data["constitution"]["sources"] = sources
    return json.dumps(data).encode("utf-8")


def test_rejects_duplicate_ids() -> None:
    """Reject duplicate constitution source identities."""
    sources = [
        {"id": "com.a.b", "revision": "0" * 40, "source": "https://github.com/a/b"},
        {"id": "com.a.b", "revision": "0" * 40, "source": "https://github.com/a/b"},
    ]
    with pytest.raises(InstallLockSourcesNotCanonicalError):
        InstallLock.from_json(_payload(sources))


def test_rejects_wrong_sort_order() -> None:
    """Reject constitution sources outside bytewise ID order."""
    sources = [
        {"id": "com.b.b", "revision": "0" * 40, "source": "https://github.com/b/b"},
        {"id": "com.a.b", "revision": "0" * 40, "source": "https://github.com/a/b"},
    ]
    with pytest.raises(InstallLockSourcesNotCanonicalError):
        InstallLock.from_json(_payload(sources))


def test_install_lock_rejects_duplicate_ownership_paths() -> None:
    first = {
        "path": ".haex-hive/generated/config.json",
        "owner": {"kind": "atom", "resource": "com.example.atom"},
        "generation_id": "g_20260831T142011Z_a4c2",
        "content_integrity": "sha256-" + "A" * 43,
        "previous": None,
    }
    second = dict(first)
    second["generation_id"] = "g_20260831T142012Z_b5d3"
    second["content_integrity"] = "sha256-" + "B" * 43
    raw = json.dumps(
        {
            "haex_hive_version": "2",
            "generated_by": "haex 2.0.0",
            "ownership": {"version": 1, "paths": [first, second]},
        }
    ).encode()

    with pytest.raises(InstallLockSchemaInvalidError, match="duplicate path"):
        InstallLock.from_json(raw)

    distinct = dict(second)
    distinct["path"] = ".haex-hive/generated/other.json"
    InstallLock.from_json(
        json.dumps(
            {
                "haex_hive_version": "2",
                "generated_by": "haex 2.0.0",
                "ownership": {"version": 1, "paths": [first, distinct]},
            }
        ).encode()
    )
