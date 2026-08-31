"""InstallLock — Spec-007 subset of `.haex-hive/install.lock`.

Preserves unknown top-level fields (FR-030 forward-compat) and applies the
required post-schema semantic check on `constitution.sources[]` uniqueness
and bytewise UTF-8 sort order.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from haex_hive.io import json_deterministic
from haex_hive.io.file_hash import canonicalize_digest_identifier
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


@dataclass
class InstallLock:
    haex_hive_version: str
    generated_by: str
    constitution: ConstitutionLockSection | None = None
    unknown_top_level: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(raw: bytes) -> InstallLock:
        try:
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict):
                constitution_data = data.get("constitution")
                if isinstance(constitution_data, dict):
                    integrity = constitution_data.get("content_integrity")
                    if isinstance(integrity, str):
                        constitution_data[
                            "content_integrity"
                        ] = canonicalize_digest_identifier(
                            integrity
                        )
            schema_validator.validate(data, "install-lock.v2.schema.json")
        except (UnicodeError, ValueError) as exc:
            raise InstallLockSchemaInvalidError(
                message="install.lock is not valid against install-lock.v2.schema.json",
                context={"schema": "install-lock.v2.schema.json"},
            ) from exc

        constitution: ConstitutionLockSection | None = None
        if "constitution" in data:
            section = data["constitution"]
            sources = tuple(
                ConstitutionSource(
                    id=s["id"], revision=s["revision"], source=s["source"]
                )
                for s in section["sources"]
            )
            _semantic_check_sources(sources)
            constitution = ConstitutionLockSection(
                sources=sources,
                assembled_by=AssembledBy(
                    tool=section["assembled_by"]["tool"],
                    version=section["assembled_by"]["version"],
                ),
                content_integrity=section["content_integrity"],
            )

        ownership = data.get("ownership")
        if ownership is not None:
            paths = [record["path"] for record in ownership["paths"]]
            if len(paths) != len(set(paths)):
                raise InstallLockSchemaInvalidError(
                    message="ownership.paths contains duplicate path values",
                    context={"field_path": "/ownership/paths/path"},
                )

        known = {"haex_hive_version", "generated_by", "constitution"}
        unknown = freeze_json({k: v for k, v in data.items() if k not in known})
        return InstallLock(
            haex_hive_version=data["haex_hive_version"],
            generated_by=data["generated_by"],
            constitution=constitution,
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
        for k, v in self.unknown_top_level.items():
            obj.setdefault(k, thaw_json(v))
        return json_deterministic.dumps(obj)


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
