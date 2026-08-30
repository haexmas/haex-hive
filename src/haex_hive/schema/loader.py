"""Package-data JSON Schema loader."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

_KNOWN_SCHEMAS = frozenset(
    {
        "haex-hive.v2.schema.json",
        "publisher-manifest.v2.schema.json",
        "atom-manifest.v2.schema.json",
        "install-lock.v2.schema.json",
    }
)


def load(name: str) -> dict[str, Any]:
    if name not in _KNOWN_SCHEMAS:
        raise KeyError(f"unknown schema name: {name!r}")
    resource = files("haex_hive.schema.data").joinpath(name)
    text = resource.read_text(encoding="utf-8")
    return json.loads(text)
