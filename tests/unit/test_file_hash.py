from __future__ import annotations

import base64
import hashlib

from haex_hive.io.file_hash import d15_one_file_tree_digest


def _reference(body: bytes) -> str:
    """Compute the independent reference digest for a constitution body."""
    path = b"constitution.md"
    tree = (
        b"haex-hive-tree-v1\x00F\x00"
        + b"100644\x00"
        + str(len(path)).encode("ascii")
        + b"\x00"
        + path
        + str(len(body)).encode("ascii")
        + b"\x00"
        + body
        + b"\x00"
    )
    return "sha256-" + base64.urlsafe_b64encode(
        hashlib.sha256(tree).digest()
    ).rstrip(b"=").decode("ascii")


def test_empty_body_matches_reference() -> None:
    """Match the D15 reference for an empty constitution."""
    assert d15_one_file_tree_digest(b"") == _reference(b"")


def test_non_empty_body_matches_reference() -> None:
    """Match the D15 reference for a non-empty constitution."""
    body = b"# Constitution\n\nHello world.\n"
    assert d15_one_file_tree_digest(body) == _reference(body)
