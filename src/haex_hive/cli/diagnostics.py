"""Single stderr formatter for every CLI-level refusal.

Every diagnostic line begins with `error: exit=<code> key=<slug>`; additional
`k=v` pairs are drawn from `HaexError.context` and any `extra` dict passed at
the call site. Secret payload values are never echoed — the caller must place
only non-sensitive metadata into `context`/`extra`.
"""

from __future__ import annotations

import sys
from typing import TextIO

from haex_hive.util.errors import HaexError


def emit_refuse(
    exc: HaexError,
    *,
    extra: dict[str, str] | None = None,
    stream: TextIO | None = None,
) -> None:
    stream = stream if stream is not None else sys.stderr
    parts = [f"error: exit={exc.exit_code}", f"key={exc.diagnostic_key}"]
    merged: dict[str, str] = {}
    merged.update(exc.context)
    if extra:
        merged.update(extra)
    for key, value in merged.items():
        parts.append(f"{key}={value}")
    stream.write(" ".join(parts) + "\n")
    if exc.message:
        stream.write(f"  {exc.message}\n")
    if exc.hint:
        stream.write(f"  hint: {exc.hint}\n")
