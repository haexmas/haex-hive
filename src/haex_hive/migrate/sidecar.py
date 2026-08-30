"""Sidecar publication for `haex migrate` (FR-014–FR-016)."""

from __future__ import annotations

from pathlib import Path

from haex_hive.io import atomic

SIDECAR_SUFFIX = ".migrated"


def sidecar_path(repo_root: Path) -> Path:
    return repo_root / (".haex-hive.json" + SIDECAR_SUFFIX)


def invalidate_stale_sidecar(repo_root: Path) -> None:
    try:
        sidecar_path(repo_root).unlink()
    except FileNotFoundError:
        pass


def publish_sidecar(repo_root: Path, v2_bytes: bytes) -> None:
    atomic.write_replace(sidecar_path(repo_root), v2_bytes)
