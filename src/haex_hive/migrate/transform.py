"""Deterministic v1 → v2 rewrite (design-doc migration table)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haex_hive.constitution.safety import validate_no_plaintext_secrets
from haex_hive.git import remote as git_remote
from haex_hive.git import revparse as git_revparse
from haex_hive.git import show as git_show
from haex_hive.io import json_deterministic
from haex_hive.model.atom_id import AtomId
from haex_hive.model.publisher_manifest import PublisherManifest
from haex_hive.model.repo_relative_path import RepoRelativePath
from haex_hive.model.source_url import canonicalize
from haex_hive.util.errors import (
    AtomIdCollisionError,
    IdentityMismatchError,
    MissingAtomManifestError,
    MissingPublisherManifestError,
    PermissionOnlyEntryError,
)

_ROLE_TO_CONTRIBUTES = {
    "constitution": "constitution",
    "spec": "spec",
    "rules": "rules",
    "hooks": "hooks",
    "skills": "skills",
}

_GITHUB_IDENTITY_RE = re.compile(r"^github\.com/([^/]+)/([^/]+)$")


def clone_dir(state_root: Path, canonical_source: str) -> Path:
    digest = hashlib.sha256(canonical_source.encode("utf-8")).hexdigest()[:16]
    return state_root / "repos" / digest


def _convert_identity(v1_identity: str) -> str:
    match = _GITHUB_IDENTITY_RE.match(v1_identity)
    if match:
        owner, repo = match.groups()
        candidate = f"com.github.{owner.lower()}.{repo.lower()}"
        return AtomId.parse_identity(candidate)
    try:
        return AtomId.parse_identity(v1_identity)
    except ValueError as exc:
        raise IdentityMismatchError(
            message=f"identity {v1_identity!r} is neither GitHub-style nor a reverse-DNS ID: {exc}",
            context={"identity": v1_identity},
        ) from None


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _relative_path_segments(path: str) -> list[str]:
    RepoRelativePath.validate(path)
    return [_nfc(seg) for seg in path.split("/")]


@dataclass
class _ResolvedEntry:
    source: str
    revision: str
    atom_id: str


def _select_atom_for_path(
    publisher: PublisherManifest,
    repo_dir: Path,
    revision: str,
    role: str,
    v1_path: str,
) -> str:
    contributes_key = _ROLE_TO_CONTRIBUTES[role]
    path_segments = _relative_path_segments(v1_path)

    matches: list[str] = []
    for atom_id, entry in publisher.atoms.items():
        atom_segments = _relative_path_segments(entry.path)
        if path_segments[: len(atom_segments)] != atom_segments:
            continue
        atom_manifest_bytes = git_show.show_bytes(
            repo_dir,
            revision,
            f"{entry.path}/manifest.json",
            not_found_error=MissingAtomManifestError,
        )
        atom_data = json.loads(atom_manifest_bytes.decode("utf-8"))
        contributes = atom_data.get("contributes") or {}
        declared = contributes.get(contributes_key)
        if declared is None:
            continue
        relative = "/".join(path_segments[len(atom_segments) :])
        if isinstance(declared, str):
            if _nfc(declared) == relative:
                matches.append(atom_id)
        else:
            continue
    if not matches:
        raise MissingAtomManifestError(
            message=f"no atom in publisher matches path {v1_path!r} for role {role!r}",
            context={"path": v1_path, "role": role},
        )
    if len(matches) > 1:
        raise AtomIdCollisionError(
            message=f"multiple atoms match path {v1_path!r}: {sorted(matches)}",
            context={"path": v1_path, "matches": ",".join(sorted(matches))},
        )
    return matches[0]


def _resolve_v1_entry(
    entry: dict[str, Any],
    index: int,
    repo_root: Path,
    state_root: Path,
) -> _ResolvedEntry:
    role = entry.get("role")
    repository = entry.get("repository")
    revision = entry.get("revision")
    path = entry.get("path")

    if role is None:
        raise PermissionOnlyEntryError(
            message=f"harness_sources[{index}] is permission-only (no role)",
            context={"entry": str(index)},
        )
    if path is None:
        raise PermissionOnlyEntryError(
            message=f"harness_sources[{index}] has no contribution path",
            context={"entry": str(index)},
        )
    if role not in _ROLE_TO_CONTRIBUTES:
        raise PermissionOnlyEntryError(
            message=f"harness_sources[{index}] role {role!r} is not supported",
            context={"entry": str(index), "role": role},
        )
    if repository is None or revision is None:
        raise PermissionOnlyEntryError(
            message=f"harness_sources[{index}] missing repository or revision",
            context={"entry": str(index)},
        )

    if repository == "self":
        raw_source = git_remote.origin_url(repo_root)
        publisher_dir = repo_root
    else:
        raw_source = repository
        publisher_dir = None  # resolved below

    canonical_source = canonicalize(raw_source)
    if publisher_dir is None:
        publisher_dir = clone_dir(state_root, canonical_source)

    full_sha = git_revparse.full_sha(publisher_dir, revision)

    publisher_bytes = git_show.show_bytes(
        publisher_dir,
        full_sha,
        "manifest.json",
        not_found_error=MissingPublisherManifestError,
    )
    publisher = PublisherManifest.from_json(publisher_bytes)

    atom_id = _select_atom_for_path(publisher, publisher_dir, full_sha, role, path)

    return _ResolvedEntry(
        source=canonical_source,
        revision=full_sha,
        atom_id=atom_id,
    )


def migrate_v1_to_v2(raw_v1: bytes, repo_root: Path, state_root: Path) -> bytes:
    validate_no_plaintext_secrets(raw_v1, location="original .haex-hive.json")

    data = json.loads(raw_v1.decode("utf-8"))
    if data.get("haex_hive_version") != "1":
        raise ValueError("migrate_v1_to_v2 called on non-v1 input")

    identity = _convert_identity(data["identity"])

    resolved: list[_ResolvedEntry] = []
    for i, entry in enumerate(data.get("harness_sources", [])):
        resolved.append(_resolve_v1_entry(entry, i, repo_root, state_root))

    grouped: dict[tuple[str, str], list[str]] = {}
    for r in resolved:
        grouped.setdefault((r.source, r.revision), []).append(r.atom_id)

    atoms_out = []
    for (source, revision), atom_ids in sorted(grouped.items()):
        includes = sorted(set(atom_ids), key=lambda s: s.encode("utf-8"))
        atoms_out.append(
            {
                "source": source,
                "revision": revision,
                "includes": includes,
            }
        )

    obj: dict[str, Any] = {
        "haex_hive_version": "2",
        "haex_hive_min_version": ">=2.0.0",
        "identity": identity,
        "atoms": atoms_out,
    }

    if "identity_note" in data:
        obj["identity_note"] = data["identity_note"]
    if "groups" in data:
        obj["groups"] = data["groups"]
    if "active_feature" in data:
        obj["active_feature"] = data["active_feature"]

    result = json_deterministic.dumps(obj)
    validate_no_plaintext_secrets(result, location="proposed v2 sidecar")
    return result
