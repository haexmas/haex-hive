"""Constitution show (US4): read-only, integrity-verified inspection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import BinaryIO

from haex_hive.install import inflight
from haex_hive.io import transaction
from haex_hive.model.install_lock import InstallLock
from haex_hive.util.errors import (
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
    hive_dir = repo_root / transaction.HAEX_HIVE_DIR
    del state_root  # recovery is a writer concern; show is read-only.
    state = inflight.inspect(hive_dir)
    if state not in (
        inflight.InflightState.STEADY,
        inflight.InflightState.UNINITIALIZED,
        inflight.InflightState.PRE_SWAP,
        inflight.InflightState.POST_SWAP,
    ):
        raise IncompleteAssemblyTransactionError(
            message=(
                "install transaction is in flight (state: "
                f"{state.value}); run `haex install` to resolve"
            ),
        )

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

    stream = out if out is not None else sys.stdout.buffer
    if not no_preface:
        stream.write(_render_preface(lock))
    stream.write(body)
