"""Single-source constitution assembly (US2). Multi-source lands in Phase 5."""

from __future__ import annotations

from pathlib import Path

from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.constitution.safety import validate_no_plaintext_secrets
from haex_hive.io import transaction
from haex_hive.io.file_hash import d15_one_file_tree_digest
from haex_hive.model.install_lock import (
    AssembledBy,
    ConstitutionLockSection,
    InstallLock,
)
from haex_hive.util.errors import PostWriteValidationError

TOOL_NAME = "haex"


def _read_existing_lock(repo_root: Path) -> InstallLock | None:
    lock_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.INSTALL_LOCK_NAME
    if not lock_path.exists():
        return None
    try:
        return InstallLock.from_json(lock_path.read_bytes())
    except (OSError, ValueError):
        # Best-effort forward-compat preservation only; a corrupt existing lock
        # is simply replaced wholesale by the fresh generation below.
        return None


def assemble_single_source(
    contribution: ResolvedConstitutionContribution,
    repo_root: Path,
    *,
    tool_version: str,
) -> None:
    validate_no_plaintext_secrets(
        contribution.body, location=f"constitution source {contribution.source.id}"
    )

    content_integrity = d15_one_file_tree_digest(contribution.body)

    existing_lock = _read_existing_lock(repo_root)
    unknown_top_level = existing_lock.unknown_top_level if existing_lock is not None else {}

    lock = InstallLock(
        haex_hive_version="2",
        generated_by=f"{TOOL_NAME} {tool_version}",
        constitution=ConstitutionLockSection(
            sources=(contribution.source,),
            assembled_by=AssembledBy(tool=TOOL_NAME, version=tool_version),
            content_integrity=content_integrity,
        ),
        unknown_top_level=unknown_top_level,
    )
    lock_bytes = lock.to_json_bytes()

    def post_write_verify() -> None:
        constitution_path = repo_root / transaction.HAEX_HIVE_DIR / transaction.CONSTITUTION_NAME
        on_disk = constitution_path.read_bytes()
        actual = d15_one_file_tree_digest(on_disk)
        if actual != content_integrity:
            raise PostWriteValidationError(
                message="on-disk constitution.md does not match recorded content_integrity",
            )

    transaction.publish_pair(
        repo_root,
        contribution.body,
        lock_bytes,
        post_write_verify=post_write_verify,
    )
