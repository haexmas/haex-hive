"""PublisherManifest — root `manifest.json` at a publisher repo's pinned SHA."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from haex_hive.model._immutable import freeze_json
from haex_hive.model.atom_id import AtomId
from haex_hive.model.repo_relative_path import RepoRelativePath
from haex_hive.schema import validator as schema_validator


@dataclass(frozen=True)
class PublisherAtomEntry:
    path: str
    version: str
    description: str | None = None


@dataclass(frozen=True)
class PublisherManifest:
    haex_hive_version: str
    publisher: str
    atoms: Mapping[str, PublisherAtomEntry]

    @staticmethod
    def from_json(raw: bytes) -> PublisherManifest:
        data = json.loads(raw.decode("utf-8"))
        schema_validator.validate(data, "publisher-manifest.v2.schema.json")

        publisher = AtomId.parse(data["publisher"])
        prefix = publisher + "."
        atoms: dict[str, PublisherAtomEntry] = {}
        for atom_id, entry in data.get("atoms", {}).items():
            AtomId.parse(atom_id)
            if not atom_id.startswith(prefix):
                raise ValueError(
                    f"atom-id {atom_id!r} does not have publisher prefix {publisher!r}"
                )
            RepoRelativePath.validate(entry["path"])
            atoms[atom_id] = PublisherAtomEntry(
                path=entry["path"],
                version=entry["version"],
                description=entry.get("description"),
            )
        return PublisherManifest(
            haex_hive_version=data["haex_hive_version"],
            publisher=publisher,
            atoms=freeze_json(atoms),
        )
