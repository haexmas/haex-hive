"""Per-root Merkle-tree digest (FR-005, research §R5).

Computes the `sha256-<base64url-nopad>` digest of one participating output
root by:

1. Enumerating the root's owned paths in POSIX-byte-sorted order.
2. Hashing each file's bytes with SHA-256 (hex representation).
3. Concatenating `<repo-relative-path>:<hex-content-hash>\\n` for each path.
4. Hashing the concatenation with SHA-256 and encoding as base64url-nopad.

`.haex-hive/` is haex-owned: the enumeration walks the whole tree but
excludes `visibility.json` and `install.lock` to avoid recursive lock/marker
integrity references (FR-005). Mixed-ownership roots pass an explicit
`overlay_paths` allowlist; the enumeration then covers ONLY those paths —
sibling entries in the target root are never touched.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath

HAEX_HIVE_ROOT = ".haex-hive/"
_HAEX_HIVE_EXCLUDED_NAMES = frozenset({"visibility.json", "install.lock"})


def compute_root_digest(
    root_dir: Path,
    root_name: str,
    overlay_paths: list[str] | None = None,
) -> str:
    """Return the base64url-nopad SRI digest of one participating root.

    `root_dir` is the on-disk directory (an absolute or repo-relative Path).
    `root_name` is the repo-relative directory name with a trailing slash
    (e.g. `.haex-hive/`, `.claude/`) — the value that appears in
    `visibility.json.participating_roots[].root`; it prefixes every entry
    in the concatenation preimage so a digest is uniquely tied to its root.

    For haex-owned roots (`overlay_paths is None`), walk the whole tree
    under `root_dir` excluding `visibility.json` and `install.lock` at the
    root level.

    For mixed-ownership roots, pass an exhaustive `overlay_paths` list of
    repo-relative POSIX paths under `root_name`. Only those paths are
    hashed; sibling entries are never enumerated.
    """
    if overlay_paths is None:
        candidate_paths = _enumerate_haex_owned(root_dir, root_name)
    else:
        candidate_paths = sorted(overlay_paths, key=lambda p: p.encode("utf-8"))
    lines: list[bytes] = []
    for repo_relative_path in candidate_paths:
        file_bytes = _read_bytes_under(root_dir, root_name, repo_relative_path)
        content_hex = hashlib.sha256(file_bytes).hexdigest()
        line = f"{repo_relative_path}:{content_hex}\n".encode()
        lines.append(line)
    concatenation = b"".join(lines)
    digest = hashlib.sha256(concatenation).digest()
    return "sha256-" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _enumerate_haex_owned(root_dir: Path, root_name: str) -> list[str]:
    """Walk `root_dir` and return repo-relative paths sorted bytewise."""
    if not root_dir.is_dir():
        return []
    entries: list[str] = []
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        relative_to_root = path.relative_to(root_dir).as_posix()
        if root_name == HAEX_HIVE_ROOT and relative_to_root in _HAEX_HIVE_EXCLUDED_NAMES:
            continue
        entries.append(root_name + relative_to_root)
    return sorted(entries, key=lambda p: p.encode("utf-8"))


def _read_bytes_under(root_dir: Path, root_name: str, repo_relative_path: str) -> bytes:
    """Resolve `repo_relative_path` beneath `root_dir` and read its bytes."""
    if not repo_relative_path.startswith(root_name):
        raise ValueError(
            f"path {repo_relative_path!r} does not belong to root {root_name!r}"
        )
    under_root = repo_relative_path[len(root_name):]
    if PurePosixPath(under_root).is_absolute() or PureWindowsPath(under_root).is_absolute():
        raise ValueError(f"path {repo_relative_path!r} must be relative to its root")

    root_resolved = root_dir.resolve()
    candidate = (root_dir / under_root).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"path {repo_relative_path!r} escapes root {root_dir!s}"
        ) from exc
    return candidate.read_bytes()
