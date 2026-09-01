"""FR-030 semantic check on `constitution.sources[]` uniqueness + sort."""

from __future__ import annotations

import json

import pytest

from haex_hive.model.install_lock import InstallLock
from haex_hive.util.errors import InstallLockSourcesNotCanonicalError

_BASE = {
    "haex_hive_version": "2",
    "generated_by": "haex 2.0.0",
    "constitution": {
        "sources": [],
        "assembled_by": {"tool": "haex", "version": "2.0.0"},
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
