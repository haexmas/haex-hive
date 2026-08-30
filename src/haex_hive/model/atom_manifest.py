"""AtomManifest — one atom's `manifest.json` at a pinned SHA (D13)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from haex_hive.model.atom_id import AtomId
from haex_hive.model.repo_relative_path import RepoRelativePath
from haex_hive.schema import validator as schema_validator


@dataclass(frozen=True)
class ContributesBlock:
    constitution: Optional[str] = None
    spec: Optional[str] = None
    rules: tuple[str, ...] = ()
    hooks: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class AtomManifest:
    haex_hive_version: str
    id: str
    version: str
    priority: int = 100
    contributes: Optional[ContributesBlock] = None
    includes: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    config_schema: Optional[str] = None

    @staticmethod
    def from_json(raw: bytes) -> "AtomManifest":
        data = json.loads(raw.decode("utf-8"))
        schema_validator.validate(data, "atom-manifest.v2.schema.json")

        AtomId.parse(data["id"])

        contributes = None
        if "contributes" in data:
            block = data["contributes"]
            constitution = block.get("constitution")
            spec = block.get("spec")
            if constitution is not None:
                RepoRelativePath.validate(constitution)
            if spec is not None:
                RepoRelativePath.validate(spec)
            contributes = ContributesBlock(
                constitution=constitution,
                spec=spec,
                rules=tuple(block.get("rules", ())),
                hooks=tuple(block.get("hooks", ())),
                skills=tuple(block.get("skills", ())),
            )

        includes: tuple[str, ...] = ()
        if "includes" in data:
            includes = tuple(AtomId.parse(a) for a in data["includes"])

        if contributes is None and not includes:
            raise ValueError(
                f"atom {data['id']!r} declares neither contributes nor includes"
            )

        config_schema = data.get("config_schema")
        if config_schema is not None:
            RepoRelativePath.validate(config_schema)

        defaults = data.get("defaults", {})
        if "priority" in defaults:
            raise ValueError(
                f"atom {data['id']!r} config_schema/defaults MUST NOT declare priority"
            )

        return AtomManifest(
            haex_hive_version=data["haex_hive_version"],
            id=data["id"],
            version=data["version"],
            priority=data.get("priority", 100),
            contributes=contributes,
            includes=includes,
            defaults=defaults,
            config_schema=config_schema,
        )
