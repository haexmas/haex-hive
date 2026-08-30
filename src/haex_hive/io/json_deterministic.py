"""Deterministic JSON serialization (R2).

`sort_keys=True`, `indent=2`, `ensure_ascii=False`, LF line endings only, and
a single trailing `\n` appended to satisfy FR-036 across every platform.
"""

from __future__ import annotations

import json
from typing import Any


def dumps(obj: Any) -> bytes:
    text = json.dumps(
        obj,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        separators=(",", ": "),
        allow_nan=False,
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (text + "\n").encode("utf-8")
