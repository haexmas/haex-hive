"""ConsumerManifest — parsed `.haex-hive.json` v2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from haex_hive.io import json_deterministic
from haex_hive.model.atom_id import AtomId
from haex_hive.model.source_url import canonicalize
from haex_hive.model.version_constraint import VersionConstraint
from haex_hive.schema import validator as schema_validator

_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ConfigEntry:
    priority: Optional[int] = None
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AtomEntry:
    source: str
    revision: str
    includes: tuple[str, ...]
    track: Optional[str] = None
    config: dict[str, ConfigEntry] = field(default_factory=dict)


@dataclass(frozen=True)
class ConsumerManifest:
    haex_hive_version: str
    identity: str
    atoms: tuple[AtomEntry, ...]
    haex_hive_min_version: Optional[VersionConstraint] = None
    groups: tuple[str, ...] = ()
    active_feature: Optional[str] = None
    identity_note: Optional[str] = None

    @staticmethod
    def from_json(raw: bytes) -> "ConsumerManifest":
        data = json.loads(raw.decode("utf-8"))
        schema_validator.validate(data, "haex-hive.v2.schema.json")

        AtomId.parse_identity(data["identity"])
        min_version = None
        if "haex_hive_min_version" in data:
            min_version = VersionConstraint.parse(data["haex_hive_min_version"])

        atoms: list[AtomEntry] = []
        for entry in data.get("atoms", []):
            source = entry["source"]
            canonical = canonicalize(source)
            if canonical != source:
                raise ValueError(
                    f"atoms[].source must be canonical: got {source!r}, expected {canonical!r}"
                )
            if not _SHA40_RE.match(entry["revision"]):
                raise ValueError(f"atoms[].revision must be 40 lowercase hex: {entry['revision']!r}")
            includes = tuple(AtomId.parse(a) for a in entry["includes"])
            if len(set(includes)) != len(includes):
                raise ValueError("atoms[].includes must be unique")
            config: dict[str, ConfigEntry] = {}
            for key, value in entry.get("config", {}).items():
                AtomId.parse(key)
                if key not in set(includes):
                    raise ValueError(f"atoms[].config[{key!r}] not resolved via includes")
                config[key] = ConfigEntry(
                    priority=value.get("priority"),
                    values=value.get("values", {}),
                )
            atoms.append(
                AtomEntry(
                    source=source,
                    revision=entry["revision"],
                    includes=includes,
                    track=entry.get("track"),
                    config=config,
                )
            )

        return ConsumerManifest(
            haex_hive_version=data["haex_hive_version"],
            identity=data["identity"],
            atoms=tuple(atoms),
            haex_hive_min_version=min_version,
            groups=tuple(data.get("groups", [])),
            active_feature=data.get("active_feature"),
            identity_note=data.get("identity_note"),
        )

    def to_json_bytes(self) -> bytes:
        obj: dict[str, Any] = {
            "haex_hive_version": self.haex_hive_version,
            "identity": self.identity,
            "atoms": [
                {
                    **({"source": a.source, "revision": a.revision, "includes": list(a.includes)}),
                    **({"track": a.track} if a.track else {}),
                    **(
                        {
                            "config": {
                                k: {
                                    **({"priority": v.priority} if v.priority is not None else {}),
                                    **({"values": v.values} if v.values else {}),
                                }
                                for k, v in a.config.items()
                            }
                        }
                        if a.config
                        else {}
                    ),
                }
                for a in self.atoms
            ],
        }
        if self.haex_hive_min_version is not None:
            op = self.haex_hive_min_version.operator
            v = self.haex_hive_min_version.version
            obj["haex_hive_min_version"] = (
                f"{'>=' if op == '>=' else ''}{v[0]}.{v[1]}.{v[2]}"
            )
        if self.groups:
            obj["groups"] = list(self.groups)
        if self.active_feature is not None:
            obj["active_feature"] = self.active_feature
        if self.identity_note is not None:
            obj["identity_note"] = self.identity_note
        return json_deterministic.dumps(obj)
