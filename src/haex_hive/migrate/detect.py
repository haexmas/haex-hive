"""Detect `.haex-hive.json` version."""

from __future__ import annotations

import json
from typing import Literal

from haex_hive.util.errors import HaexError


class UnsupportedHaexHiveVersionError(HaexError):
    diagnostic_key: str = "unsupported-haex-hive-version"
    exit_code: int = 5
    hint: str = "Expected haex_hive_version 1 or 2."


def detect_version(raw: bytes) -> Literal[1, 2]:
    data = json.loads(raw.decode("utf-8"))
    version = data.get("haex_hive_version")
    if version == "1":
        return 1
    if version == "2":
        return 2
    raise UnsupportedHaexHiveVersionError(
        message=f"unsupported haex_hive_version {version!r}",
        context={"got": str(version)},
    )
