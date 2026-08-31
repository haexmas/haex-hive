"""Device-local transaction state paths shared by install and constitution commands."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from haex_hive.git.remote import origin_url
from haex_hive.model.source_url import canonicalize


@dataclass(frozen=True)
class TransactionPaths:
    """Resolved device-local paths for one project identity."""

    state_root: Path
    identity: str
    repo_key: str
    lock_dir: Path
    mutex: Path
    journal: Path
    identity_record: Path
    legacy_mutex: Path
    legacy_journal: Path


def default_state_root() -> Path:
    """Return the configured state root without creating it."""
    configured = os.environ.get("HAEX_HIVE_STATE")
    if configured:
        return Path(configured)
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "haex-hive"
    return Path.home() / ".local" / "share" / "haex-hive"


def project_identity(repo_root: Path) -> str:
    """Resolve the canonical, device-independent identity for a project.

    Git-backed projects use the canonical origin URL. Non-git folders use the
    contents of `.harness-id`. The manifest identity is retained as a narrow
    compatibility fallback for pre-Spec-008 fixture projects that have neither.
    """
    try:
        return canonicalize(origin_url(repo_root))
    except Exception as exc:
        harness_id = repo_root / ".harness-id"
        if harness_id.is_file():
            identity = harness_id.read_text(encoding="utf-8").strip()
            if identity and "/" not in identity and "\\" not in identity:
                return identity

        manifest = repo_root / ".haex-hive.json"
        if manifest.is_file():
            try:
                identity = json.loads(manifest.read_text(encoding="utf-8"))["identity"]
            except (OSError, KeyError, TypeError, ValueError):
                identity = ""
            if isinstance(identity, str) and identity:
                return identity
        raise ValueError("project has no canonical git identity or .harness-id") from exc


def transaction_paths(repo_root: Path, state_root: Path | None = None) -> TransactionPaths:
    """Return shared transaction paths for ``repo_root``.

    The full identity is never used as a path segment. Legacy paths are exposed
    only so callers can discover and migrate pre-Spec-008 transaction state.
    """
    identity = project_identity(repo_root)
    repo_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    root = state_root if state_root is not None else default_state_root()
    lock_dir = root / "locks" / repo_key
    return TransactionPaths(
        state_root=root,
        identity=identity,
        repo_key=repo_key,
        lock_dir=lock_dir,
        mutex=lock_dir / "install.mutex",
        journal=lock_dir / "install.journal",
        identity_record=lock_dir / "repo-identity.v1.json",
        legacy_mutex=repo_root / ".haex-hive" / "constitution-transaction.lock",
        legacy_journal=repo_root / ".haex-hive" / "constitution-transaction.json",
    )


def write_identity_record(paths: TransactionPaths) -> None:
    """Persist the non-secret canonical identity for collision diagnostics."""
    paths.lock_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "identity": paths.identity,
        "repo_key": paths.repo_key,
    }
    temporary = paths.identity_record.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, paths.identity_record)
