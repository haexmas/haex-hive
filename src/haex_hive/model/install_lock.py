"""InstallLock v2 — the on-disk contract for `.haex-hive/install.lock`.

Spec 007 landed the constitution section; Spec 008 adds `atoms`,
`participating_roots`, `visibility_marker`, and a versioned `ownership`
set. Every added field is a first-class dataclass here so writers get a
compile-time-visible surface and readers get validated shapes on load.

The still-present `unknown_top_level` bag preserves *actually* unknown
fields (anything the schema doesn't yet describe) across a read/write
round-trip — under the project's pre-user policy we don't need it for
Spec 007-vintage records (they refuse at schema validation), but we do
need it if we ever ship a v3 field a downstream v2 reader must survive.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from haex_hive.io import json_deterministic
from haex_hive.model._immutable import freeze_json, thaw_json
from haex_hive.schema import validator as schema_validator
from haex_hive.util.errors import (
    InstallLockSchemaInvalidError,
    InstallLockSourcesNotCanonicalError,
)


@dataclass(frozen=True)
class ConstitutionSource:
    id: str
    revision: str
    source: str


@dataclass(frozen=True)
class AssembledBy:
    tool: str
    version: str


@dataclass(frozen=True)
class ConstitutionLockSection:
    sources: tuple[ConstitutionSource, ...]
    assembled_by: AssembledBy
    content_integrity: str


@dataclass(frozen=True)
class AtomInstallRecord:
    """One adopted atom's sealed contribution (data-model.md §AtomInstallRecord)."""

    id: str
    source: str
    revision: str
    content_integrity: str
    contributed_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "contributed_paths", tuple(self.contributed_paths))


@dataclass(frozen=True)
class RootRecord:
    """One participating output root (data-model.md §RootRecord)."""

    root: str
    content_integrity: str
    overlay_paths: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.overlay_paths is not None:
            object.__setattr__(self, "overlay_paths", tuple(self.overlay_paths))


@dataclass(frozen=True)
class VisibilityMarkerRef:
    """Cross-reference to `.haex-hive/visibility.json` (data-model.md §InstallLock)."""

    generation_id: str
    content_integrity: str


@dataclass(frozen=True)
class OwnerResource:
    """Atom, adapter, or hook that owns one generated path."""

    kind: Literal["atom", "adapter", "hook"]
    resource: str
    source: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class PreviousPathState:
    """Prior generation state for one owned path (rollback metadata)."""

    generation_id: str
    existed: bool
    content_integrity: str | None = None


@dataclass(frozen=True)
class PathOwnershipRecord:
    """One owned path in an install generation (data-model.md §PathOwnershipRecord)."""

    path: str
    owner: OwnerResource
    generation_id: str
    content_integrity: str
    previous: PreviousPathState | None = None


@dataclass(frozen=True)
class OwnershipSet:
    """Authoritative per-path ownership for one installed generation."""

    paths: tuple[PathOwnershipRecord, ...]
    version: Literal[1] = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", tuple(self.paths))
        path_ids = [record.path for record in self.paths]
        if len(path_ids) != len(set(path_ids)):
            raise InstallLockSchemaInvalidError(
                message="ownership.paths contains duplicate path values",
                context={"field_path": "/ownership/paths/path"},
            )


@dataclass(frozen=True)
class InstallLock:
    haex_hive_version: str
    generated_by: str
    constitution: ConstitutionLockSection | None = None
    atoms: tuple[AtomInstallRecord, ...] | None = None
    participating_roots: tuple[RootRecord, ...] | None = None
    visibility_marker: VisibilityMarkerRef | None = None
    ownership: OwnershipSet | None = None
    unknown_top_level: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.atoms is not None:
            object.__setattr__(self, "atoms", tuple(self.atoms))
        if self.participating_roots is not None:
            roots = tuple(self.participating_roots)
            object.__setattr__(self, "participating_roots", roots)
            names = [record.root for record in roots]
            if len(names) != len(set(names)):
                raise InstallLockSchemaInvalidError(
                    message="participating_roots contains duplicate root values",
                    context={"field_path": "/participating_roots/root"},
                )
        object.__setattr__(
            self,
            "unknown_top_level",
            freeze_json(dict(self.unknown_top_level)),
        )

    @staticmethod
    def from_json(raw: bytes) -> InstallLock:
        try:
            data = json.loads(raw.decode("utf-8"))
            schema_validator.validate(data, "install-lock.v2.schema.json")
        except (UnicodeError, ValueError) as exc:
            detail = (
                f": {exc}"
                if isinstance(exc, schema_validator.SchemaValidationError)
                else ""
            )
            raise InstallLockSchemaInvalidError(
                message=(
                    "install.lock is not valid against install-lock.v2.schema.json"
                    + detail
                ),
                context={"schema": "install-lock.v2.schema.json"},
            ) from exc

        constitution = _parse_constitution(data.get("constitution"))
        atoms = _parse_atoms(data.get("atoms"))
        participating_roots = _parse_participating_roots(data.get("participating_roots"))
        visibility_marker = _parse_visibility_marker(data.get("visibility_marker"))
        ownership = _parse_ownership(data.get("ownership"))

        known = {
            "haex_hive_version",
            "generated_by",
            "constitution",
            "atoms",
            "participating_roots",
            "visibility_marker",
            "ownership",
        }
        unknown = {k: v for k, v in data.items() if k not in known}
        return InstallLock(
            haex_hive_version=data["haex_hive_version"],
            generated_by=data["generated_by"],
            constitution=constitution,
            atoms=atoms,
            participating_roots=participating_roots,
            visibility_marker=visibility_marker,
            ownership=ownership,
            unknown_top_level=unknown,
        )

    def to_json_bytes(self) -> bytes:
        obj: dict[str, Any] = {
            "haex_hive_version": self.haex_hive_version,
            "generated_by": self.generated_by,
        }
        if self.constitution is not None:
            obj["constitution"] = {
                "assembled_by": {
                    "tool": self.constitution.assembled_by.tool,
                    "version": self.constitution.assembled_by.version,
                },
                "content_integrity": self.constitution.content_integrity,
                "sources": [
                    {"id": s.id, "revision": s.revision, "source": s.source}
                    for s in self.constitution.sources
                ],
            }
        if self.atoms is not None:
            obj["atoms"] = [_serialize_atom(atom) for atom in self.atoms]
        if self.participating_roots is not None:
            obj["participating_roots"] = [
                _serialize_root(root) for root in self.participating_roots
            ]
        if self.visibility_marker is not None:
            obj["visibility_marker"] = {
                "generation_id": self.visibility_marker.generation_id,
                "content_integrity": self.visibility_marker.content_integrity,
            }
        if self.ownership is not None:
            obj["ownership"] = _serialize_ownership(self.ownership)
        for k, v in self.unknown_top_level.items():
            obj.setdefault(k, thaw_json(v))
        return json_deterministic.dumps(obj)


def _parse_constitution(section: Any) -> ConstitutionLockSection | None:
    if section is None:
        return None
    sources = tuple(
        ConstitutionSource(id=s["id"], revision=s["revision"], source=s["source"])
        for s in section["sources"]
    )
    _semantic_check_sources(sources)
    return ConstitutionLockSection(
        sources=sources,
        assembled_by=AssembledBy(
            tool=section["assembled_by"]["tool"],
            version=section["assembled_by"]["version"],
        ),
        content_integrity=section["content_integrity"],
    )


def _parse_atoms(raw: Any) -> tuple[AtomInstallRecord, ...] | None:
    if raw is None:
        return None
    return tuple(
        AtomInstallRecord(
            id=item["id"],
            source=item["source"],
            revision=item["revision"],
            content_integrity=item["content_integrity"],
            contributed_paths=tuple(item["contributed_paths"]),
        )
        for item in raw
    )


def _parse_participating_roots(raw: Any) -> tuple[RootRecord, ...] | None:
    if raw is None:
        return None
    return tuple(
        RootRecord(
            root=item["root"],
            content_integrity=item["content_integrity"],
            overlay_paths=(
                tuple(item["overlay_paths"])
                if item.get("overlay_paths") is not None
                else None
            ),
        )
        for item in raw
    )


def _parse_visibility_marker(raw: Any) -> VisibilityMarkerRef | None:
    if raw is None:
        return None
    return VisibilityMarkerRef(
        generation_id=raw["generation_id"],
        content_integrity=raw["content_integrity"],
    )


def _parse_ownership(raw: Any) -> OwnershipSet | None:
    if raw is None:
        return None
    return OwnershipSet(
        version=raw["version"],
        paths=tuple(_parse_path_ownership(entry) for entry in raw["paths"]),
    )


def _parse_path_ownership(raw: Mapping[str, Any]) -> PathOwnershipRecord:
    return PathOwnershipRecord(
        path=raw["path"],
        owner=OwnerResource(
            kind=raw["owner"]["kind"],
            resource=raw["owner"]["resource"],
            source=raw["owner"].get("source"),
            revision=raw["owner"].get("revision"),
        ),
        generation_id=raw["generation_id"],
        content_integrity=raw["content_integrity"],
        previous=_parse_previous(raw.get("previous")),
    )


def _parse_previous(raw: Any) -> PreviousPathState | None:
    if raw is None:
        return None
    return PreviousPathState(
        generation_id=raw["generation_id"],
        existed=raw["existed"],
        content_integrity=raw.get("content_integrity"),
    )


def _serialize_atom(atom: AtomInstallRecord) -> dict[str, Any]:
    return {
        "id": atom.id,
        "source": atom.source,
        "revision": atom.revision,
        "content_integrity": atom.content_integrity,
        "contributed_paths": list(atom.contributed_paths),
    }


def _serialize_root(root: RootRecord) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "root": root.root,
        "content_integrity": root.content_integrity,
    }
    if root.overlay_paths is not None:
        obj["overlay_paths"] = list(root.overlay_paths)
    return obj


def _serialize_ownership(ownership: OwnershipSet) -> dict[str, Any]:
    return {
        "version": ownership.version,
        "paths": [_serialize_path_ownership(record) for record in ownership.paths],
    }


def _serialize_path_ownership(record: PathOwnershipRecord) -> dict[str, Any]:
    owner_obj: dict[str, Any] = {
        "kind": record.owner.kind,
        "resource": record.owner.resource,
    }
    if record.owner.source is not None:
        owner_obj["source"] = record.owner.source
    if record.owner.revision is not None:
        owner_obj["revision"] = record.owner.revision
    obj: dict[str, Any] = {
        "path": record.path,
        "owner": owner_obj,
        "generation_id": record.generation_id,
        "content_integrity": record.content_integrity,
        "previous": _serialize_previous(record.previous),
    }
    return obj


def _serialize_previous(previous: PreviousPathState | None) -> dict[str, Any] | None:
    if previous is None:
        return None
    obj: dict[str, Any] = {
        "generation_id": previous.generation_id,
        "existed": previous.existed,
        "content_integrity": previous.content_integrity,
    }
    return obj


def _semantic_check_sources(sources: tuple[ConstitutionSource, ...]) -> None:
    ids = [s.id for s in sources]
    if len(set(ids)) != len(ids):
        raise InstallLockSourcesNotCanonicalError(
            message="constitution.sources[].id values are not unique",
        )
    encoded = [s.id.encode("utf-8") for s in sources]
    if encoded != sorted(encoded):
        raise InstallLockSourcesNotCanonicalError(
            message="constitution.sources[] are not sorted in ascending bytewise UTF-8 id order",
        )
