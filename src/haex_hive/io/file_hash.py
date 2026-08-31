"""D15 one-file `haex-hive-tree-v1` digest (R11).

Serialization framing for the one-file constitution.md tree:

    b"haex-hive-tree-v1\\0F\\0"
    + b"100644\\0"
    + str(len(path_bytes)).encode("ascii") + b"\\0" + path_bytes
    + str(len(body)).encode("ascii") + b"\\0" + body + b"\\0"

The digest returned is `sha256-<base64url-nopad>` (RFC 4648 §5, unpadded).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re

_CONSTITUTION_PATH = b"constitution.md"
_LEGACY_SHA256_RE = re.compile(r"^sha256-[A-Za-z0-9+/]{43}=$")


def _serialize(path_bytes: bytes, body: bytes) -> bytes:
    """Frame one file according to the D15 tree serialization contract."""
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
    """Return the unpadded Base64URL SRI digest for a constitution body."""
    tree_bytes = _serialize(_CONSTITUTION_PATH, body)
    digest = hashlib.sha256(tree_bytes).digest()
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def canonicalize_digest_identifier(value: str) -> str:
    """Convert a valid legacy padded Base64 SHA-256 identifier to Base64URL."""
    if not _LEGACY_SHA256_RE.fullmatch(value):
        return value
    try:
        digest = base64.b64decode(value.removeprefix("sha256-"), validate=True)
    except (ValueError, binascii.Error):
        return value
    if len(digest) != hashlib.sha256().digest_size:
        return value
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
