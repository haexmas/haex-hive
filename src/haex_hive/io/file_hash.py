"""D15 one-file `haex-hive-tree-v1` digest (R11).

Serialization framing for the one-file constitution.md tree:

    b"haex-hive-tree-v1\\0F\\0"
    + b"100644\\0"
    + str(len(path_bytes)).encode("ascii") + b"\\0" + path_bytes
    + str(len(body)).encode("ascii") + b"\\0" + body + b"\\0"

The digest returned is `sha256-<standard-base64>` (RFC 4648, padded).
"""

from __future__ import annotations

import base64
import hashlib

_CONSTITUTION_PATH = b"constitution.md"


def _serialize(path_bytes: bytes, body: bytes) -> bytes:
    return (
        b"haex-hive-tree-v1\x00F\x00"
        + b"100644\x00"
        + str(len(path_bytes)).encode("ascii")
        + b"\x00"
        + path_bytes
        + str(len(body)).encode("ascii")
        + b"\x00"
        + body
        + b"\x00"
    )


def d15_one_file_tree_digest(body: bytes) -> str:
    tree_bytes = _serialize(_CONSTITUTION_PATH, body)
    digest = hashlib.sha256(tree_bytes).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")
