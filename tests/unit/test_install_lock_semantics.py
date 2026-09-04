"""FR-030 semantic check on `constitution.sources[]` uniqueness + sort."""

from __future__ import annotations

import json

import pytest

from haex_hive.model.install_lock import InstallLock
from haex_hive.util.errors import (
    CredentialInUrlError,
    InstallLockSchemaInvalidError,
    InstallLockSourcesNotCanonicalError,
)

_BASE = {
    "haex_hive_version": "3",
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


def test_rejects_credentials_in_constitution_source() -> None:
    """Reject source URL userinfo before it can be stored or serialized."""
    sources = [
        {
            "id": "com.a.b",
            "revision": "0" * 40,
            "source": "https://user:pass@example.com/publisher",
        }
    ]
    with pytest.raises(CredentialInUrlError):
        InstallLock.from_json(_payload(sources))


def test_rejects_credentials_in_atom_source() -> None:
    """Reject credentials in an installed atom source before serialization."""
    data = {
        **_BASE,
        "molecules": [
            {
                "id": "com.a.b",
                "revision": "0" * 40,
                "source": "https://user:pass@example.com/publisher",
                "contributed_paths": [".haex-hive/constitution.md"],
            }
        ],
        "participating_roots": [".haex-hive/"],
    }
    with pytest.raises(CredentialInUrlError):
        InstallLock.from_json(json.dumps(data).encode())


def test_preserves_unknown_top_level_fields() -> None:
    """Forward-compatible lock fields survive parsing and serialization."""
    data = json.loads(json.dumps(_BASE))
    data["future_field"] = {"nested": [1, "value"]}

    lock = InstallLock.from_json(json.dumps(data).encode())
    serialized = json.loads(lock.to_json_bytes())

    assert lock.unknown_top_level["future_field"]["nested"] == (1, "value")
    assert serialized["future_field"] == data["future_field"]


def _molecule_lock_data(paths: list[str], roots: list[str] | None = None) -> dict:
    """Build a lock payload for contributed-path containment checks."""
    data = {
        "haex_hive_version": "3",
        "generated_by": "haex 3.0.0",
        "molecules": [
            {
                "id": "com.example.molecule",
                "source": "https://example.com/publisher",
                "revision": "0" * 40,
                "contributed_paths": paths,
            }
        ],
    }
    if roots is not None:
        data["participating_roots"] = roots
    return data


def test_rejects_contributed_path_outside_participating_roots() -> None:
    """Reject a non-empty contribution that is outside all output roots."""
    data = _molecule_lock_data(["README.md"], [".haex-hive/"])

    with pytest.raises(InstallLockSchemaInvalidError):
        InstallLock.from_json(json.dumps(data).encode())


def test_rejects_contributed_path_without_participating_roots() -> None:
    """Require roots whenever a molecule contributes a non-empty path."""
    data = _molecule_lock_data([".haex-hive/constitution.md"])

    with pytest.raises(InstallLockSchemaInvalidError):
        InstallLock.from_json(json.dumps(data).encode())


def test_allows_empty_contributed_paths_without_participating_roots() -> None:
    """Keep empty contribution ledgers valid for locks without output roots."""
    lock = InstallLock.from_json(json.dumps(_molecule_lock_data([])).encode())

    assert lock.molecules is not None
    assert lock.molecules[0].contributed_paths == ()
