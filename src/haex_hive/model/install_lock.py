"""InstallLock v3 — the on-disk contract for `.haex-hive/install.lock`.

Spec 007 landed the constitution section; Spec 008 adds `atoms`, immutable
`generation_inputs`, `participating_roots`, and `visibility_marker`. Spec 013
renames the top-level `atoms[]` array to `molecules[]` and `AtomInstallRecord`
to `MoleculeInstallRecord`. Every field is a first-class dataclass here so
writers get a compile-time-visible surface and readers get validated shapes
on load.

The still-present `unknown_top_level` bag preserves *actually* unknown
fields (anything the schema doesn't yet describe) across a read/write
round-trip — under the project's pre-user policy we don't need it for
Spec 007-vintage records (they refuse at schema validation), but we do
need it if we ever ship a v4 field a downstream v3 reader must survive.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from haex_hive.io import json_deterministic
from haex_hive.model._immutable import freeze_json, thaw_json
from haex_hive.model.source_url import CanonicalSourceUrl
from haex_hive.schema import validator as schema_validator
from haex_hive.util.errors import (
    InstallLockSchemaInvalidError,
    InstallLockSourcesNotCanonicalError,
)

_KNOWN_TOP_LEVEL_FIELDS = frozenset(
    {
        "haex_hive_version",
        "generated_by",
        "constitution",
        "molecules",
        "generation_inputs",
        "participating_roots",
        "visibility_marker",
    }
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


@dataclass(frozen=True)
class MoleculeInstallRecord:
    """One adopted molecule's sealed contribution (data-model.md §MoleculeInstallRecord)."""

    id: str
    source: str
    revision: str
    contributed_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "contributed_paths", tuple(self.contributed_paths))


@dataclass(frozen=True)
class VisibilityMarkerRef:
    """Cross-reference to `.haex-hive/visibility.json` (data-model.md §InstallLock)."""

    generation_id: str


@dataclass(frozen=True)
class GenerationInputIdentity:
    """One immutable generator input and its canonical serialization profile."""

    kind: Literal["adapter", "tool-config"]
    id: str
    revision: str
    serialization: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "serialization", freeze_json(dict(self.serialization)))


@dataclass(frozen=True)
class InstallLock:
    haex_hive_version: str
    generated_by: str
    constitution: ConstitutionLockSection | None = None
    molecules: tuple[MoleculeInstallRecord, ...] | None = None
    generation_inputs: tuple[GenerationInputIdentity, ...] | None = None
    participating_roots: tuple[str, ...] | None = None
    visibility_marker: VisibilityMarkerRef | None = None
    unknown_top_level: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.molecules is not None:
            object.__setattr__(self, "molecules", tuple(self.molecules))
        if self.generation_inputs is not None:
            inputs = tuple(self.generation_inputs)
            object.__setattr__(self, "generation_inputs", inputs)
            identities = [(item.kind, item.id) for item in inputs]
            if len(identities) != len(set(identities)):
                raise InstallLockSchemaInvalidError(
                    message="generation_inputs contains duplicate (kind, id) values",
                    context={"field_path": "/generation_inputs"},
                )
            if identities != sorted(identities):
                raise InstallLockSchemaInvalidError(
                    message="generation_inputs are not sorted by (kind, id)",
                    context={"field_path": "/generation_inputs"},
                )
        if self.participating_roots is not None:
            object.__setattr__(self, "participating_roots", tuple(self.participating_roots))
        object.__setattr__(
            self,
            "unknown_top_level",
            freeze_json(dict(self.unknown_top_level)),
        )

    @staticmethod
    def from_json(raw: bytes) -> InstallLock:
        try:
            data = json.loads(raw.decode("utf-8"))
            data = _migrate_pre_amendment_v3(data)
            if isinstance(data, dict):
                # Keep unknown top-level fields so a v3 reader can round-trip
                # fields introduced by a newer lock schema. The v3 schema has
                # additionalProperties=false, so validate only its known
                # projection while retaining the complete unknown bag.
                unknown = {
                    key: value
                    for key, value in data.items()
                    if key not in _KNOWN_TOP_LEVEL_FIELDS
                }
                validation_data = {
                    key: value
                    for key, value in data.items()
                    if key in _KNOWN_TOP_LEVEL_FIELDS
                }
            else:
                unknown = {}
                validation_data = data
            schema_validator.validate(validation_data, "install-lock.v3.schema.json")
        except (UnicodeError, ValueError) as exc:
            detail = (
                f": {exc}"
                if isinstance(exc, schema_validator.SchemaValidationError)
                else ""
            )
            raise InstallLockSchemaInvalidError(
                message=(
                    "install.lock is not valid against install-lock.v3.schema.json"
                    + detail
                ),
                context={"schema": "install-lock.v3.schema.json"},
            ) from exc

        constitution = _parse_constitution(data.get("constitution"))
        molecules = _parse_molecules(data.get("molecules"))
        generation_inputs = _parse_generation_inputs(data.get("generation_inputs"))
        participating_roots = _parse_participating_roots(data.get("participating_roots"))
        visibility_marker = _parse_visibility_marker(data.get("visibility_marker"))

        return InstallLock(
            haex_hive_version=data["haex_hive_version"],
            generated_by=data["generated_by"],
            constitution=constitution,
            molecules=molecules,
            generation_inputs=generation_inputs,
            participating_roots=participating_roots,
            visibility_marker=visibility_marker,
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
                "sources": [
                    {"id": s.id, "revision": s.revision, "source": s.source}
                    for s in self.constitution.sources
                ],
            }
        if self.molecules is not None:
            obj["molecules"] = [_serialize_molecule(m) for m in self.molecules]
        if self.generation_inputs is not None:
            obj["generation_inputs"] = [
                _serialize_generation_input(item) for item in self.generation_inputs
            ]
        if self.participating_roots is not None:
            obj["participating_roots"] = list(self.participating_roots)
        if self.visibility_marker is not None:
            obj["visibility_marker"] = {
                "generation_id": self.visibility_marker.generation_id,
            }
        for k, v in self.unknown_top_level.items():
            obj.setdefault(k, thaw_json(v))
        return json_deterministic.dumps(obj)


def _migrate_pre_amendment_v3(data: Any) -> Any:
    """Normalize a stale pre-amendment lock shape for the current reader.

    Older locks persisted output digests, root records, and an ownership
    inventory. Those fields were deliberately retired by the trust-git
    amendment. They must be removed before validating the current schema so a
    crashed install can still resume and replace the old lock atomically.
    """
    if not isinstance(data, dict):
        return data

    migrated = dict(data)
    constitution = migrated.get("constitution")
    if isinstance(constitution, dict) and "content_integrity" in constitution:
        constitution = dict(constitution)
        constitution.pop("content_integrity", None)
        migrated["constitution"] = constitution

    molecules = migrated.get("molecules")
    if isinstance(molecules, list):
        migrated["molecules"] = [
            (
                {key: value for key, value in item.items() if key != "content_integrity"}
                if isinstance(item, dict)
                else item
            )
            for item in molecules
        ]

    roots = migrated.get("participating_roots")
    if isinstance(roots, list) and all(isinstance(item, dict) for item in roots):
        migrated["participating_roots"] = [item.get("root") for item in roots]

    marker = migrated.get("visibility_marker")
    if isinstance(marker, dict) and "content_integrity" in marker:
        marker = dict(marker)
        marker.pop("content_integrity", None)
        migrated["visibility_marker"] = marker

    migrated.pop("ownership", None)
    return migrated


def _parse_constitution(section: Any) -> ConstitutionLockSection | None:
    if section is None:
        return None
    sources = tuple(
        ConstitutionSource(
            id=s["id"],
            revision=s["revision"],
            source=CanonicalSourceUrl.validate(s["source"]),
        )
        for s in section["sources"]
    )
    _semantic_check_sources(sources)
    return ConstitutionLockSection(
        sources=sources,
        assembled_by=AssembledBy(
            tool=section["assembled_by"]["tool"],
            version=section["assembled_by"]["version"],
        ),
    )


def _parse_molecules(raw: Any) -> tuple[MoleculeInstallRecord, ...] | None:
    if raw is None:
        return None
    return tuple(
        MoleculeInstallRecord(
            id=item["id"],
            source=CanonicalSourceUrl.validate(item["source"]),
            revision=item["revision"],
            contributed_paths=tuple(item["contributed_paths"]),
        )
        for item in raw
    )


def _parse_generation_inputs(raw: Any) -> tuple[GenerationInputIdentity, ...] | None:
    if raw is None:
        return None
    return tuple(
        GenerationInputIdentity(
            kind=item["kind"],
            id=item["id"],
            revision=item["revision"],
            serialization=item["serialization"],
        )
        for item in raw
    )


def _parse_participating_roots(raw: Any) -> tuple[str, ...] | None:
    if raw is None:
        return None
    return tuple(raw)


def _parse_visibility_marker(raw: Any) -> VisibilityMarkerRef | None:
    if raw is None:
        return None
    return VisibilityMarkerRef(
        generation_id=raw["generation_id"],
    )


def _serialize_molecule(molecule: MoleculeInstallRecord) -> dict[str, Any]:
    return {
        "id": molecule.id,
        "source": molecule.source,
        "revision": molecule.revision,
        "contributed_paths": list(molecule.contributed_paths),
    }


def _serialize_generation_input(item: GenerationInputIdentity) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "id": item.id,
        "revision": item.revision,
        "serialization": thaw_json(item.serialization),
    }


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
