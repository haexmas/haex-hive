"""Constitution show (US4): read-only, integrity-verified inspection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import BinaryIO

from haex_hive.io import transaction
from haex_hive.io.file_hash import d15_one_file_tree_digest
from haex_hive.model.install_lock import InstallLock
from haex_hive.util.errors import (
    ConstitutionIntegrityMismatchError,
    ConstitutionNotAssembledError,
    IncompleteAssemblyTransactionError,
    InstallLockMissingError,
)


def _render_preface(lock: InstallLock) -> bytes:
    assert lock.constitution is not None
    lines = "".join(
        f"- {s.id} @ {s.revision[:7]} ({s.source})\n" for s in lock.constitution.sources
    )
    return f"# Assembled from\n{lines}\n---\n\n".encode()


def show(
    repo_root: Path,
    *,
    no_preface: bool,
    out: BinaryIO | None = None,
    state_root: Path | None = None,
) -> None:
    if transaction.is_journaled(repo_root, state_root=state_root):
        raise IncompleteAssemblyTransactionError(
            message="an install transaction journal is present",
        )

    hive_dir = repo_root / transaction.HAEX_HIVE_DIR
    constitution_path = hive_dir / transaction.CONSTITUTION_NAME
    if not constitution_path.exists():
        raise ConstitutionNotAssembledError(
            message=".haex-hive/constitution.md does not exist",
        )

    lock_path = hive_dir / transaction.INSTALL_LOCK_NAME
    if not lock_path.exists():
        raise InstallLockMissingError(
            message=".haex-hive/install.lock does not exist",
        )

    lock = InstallLock.from_json(lock_path.read_bytes())
    if lock.constitution is None:
        raise InstallLockMissingError(
            message="install.lock has no constitution section",
        )

    body = constitution_path.read_bytes()
    actual = d15_one_file_tree_digest(body)
    if actual != lock.constitution.content_integrity:
        raise ConstitutionIntegrityMismatchError(
            message="constitution.md does not match install.lock constitution.content_integrity",
        )

    stream = out if out is not None else sys.stdout.buffer
    if not no_preface:
        stream.write(_render_preface(lock))
    stream.write(body)
