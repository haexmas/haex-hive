"""T051 — unit tests for the D11 two-step lookup in constitution/resolve.py."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from haex_hive.constitution.resolve import resolve_constitution_contributions
from haex_hive.migrate.transform import clone_dir
from haex_hive.model.consumer_manifest import AtomEntry, ConsumerManifest
from haex_hive.util.errors import (
    AtomIdCollisionError,
    MissingAtomManifestError,
    MissingPublisherManifestError,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "haex-test@example.com")
    _git(root, "config", "user.name", "haex-test")
    _git(root, "config", "commit.gpgsign", "false")


def _publish(
    publisher: Path, publisher_manifest: dict, atoms: dict[str, tuple[dict, bytes]]
) -> str:
    """Write a publisher root manifest plus one directory per atom, then commit."""
    publisher.mkdir(parents=True, exist_ok=True)
    _init_repo(publisher)
    (publisher / "manifest.json").write_text(json.dumps(publisher_manifest, sort_keys=True))
    for path, (atom_manifest, body) in atoms.items():
        atom_dir = publisher / path
        atom_dir.mkdir(parents=True, exist_ok=True)
        (atom_dir / "manifest.json").write_text(json.dumps(atom_manifest, sort_keys=True))
        if body is not None:
            (atom_dir / "constitution.md").write_bytes(body)
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "publish")
    return _git(publisher, "rev-parse", "HEAD")


def _clone(state_root: Path, canonical: str, publisher: Path) -> None:
    target = clone_dir(state_root, canonical)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(publisher, target)


def _manifest(atoms: list[AtomEntry]) -> ConsumerManifest:
    return ConsumerManifest(
        haex_hive_version="2",
        identity="com.github.example.consumer",
        atoms=tuple(atoms),
    )


def test_publisher_key_atom_id_mismatch(tmp_path: Path) -> None:
    canonical = "https://github.com/example/publisher"
    publisher = tmp_path / "publisher"
    atom_key = "com.github.example.publisher.constitution"
    sha = _publish(
        publisher,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {atom_key: {"path": "c", "version": "1.0.0"}},
        },
        {
            "c": (
                {
                    "haex_hive_version": "2",
                    "id": "com.github.example.publisher.wrong-id",
                    "version": "1.0.0",
                    "contributes": {"constitution": "constitution.md"},
                },
                b"body",
            )
        },
    )
    state_root = tmp_path / "state"
    _clone(state_root, canonical, publisher)

    manifest = _manifest(
        [
            AtomEntry(
                source=canonical,
                revision=sha,
                includes=("com.github.example.publisher.constitution",),
            )
        ]
    )
    with pytest.raises(MissingAtomManifestError):
        resolve_constitution_contributions(manifest, state_root)


def test_version_mismatch(tmp_path: Path) -> None:
    canonical = "https://github.com/example/publisher"
    publisher = tmp_path / "publisher"
    atom_id = "com.github.example.publisher.constitution"
    sha = _publish(
        publisher,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {atom_id: {"path": "c", "version": "2.0.0"}},
        },
        {
            "c": (
                {
                    "haex_hive_version": "2",
                    "id": atom_id,
                    "version": "1.0.0",
                    "contributes": {"constitution": "constitution.md"},
                },
                b"body",
            )
        },
    )
    state_root = tmp_path / "state"
    _clone(state_root, canonical, publisher)

    manifest = _manifest(
        [AtomEntry(source=canonical, revision=sha, includes=(atom_id,))]
    )
    with pytest.raises(MissingAtomManifestError):
        resolve_constitution_contributions(manifest, state_root)


def test_atom_not_declared_by_publisher(tmp_path: Path) -> None:
    canonical = "https://github.com/example/publisher"
    publisher = tmp_path / "publisher"
    sha = _publish(
        publisher,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {"com.github.example.publisher.other": {"path": "other", "version": "1.0.0"}},
        },
        {
            "other": (
                {
                    "haex_hive_version": "2",
                    "id": "com.github.example.publisher.other",
                    "version": "1.0.0",
                    "contributes": {"spec": "spec.md"},
                },
                None,
            )
        },
    )
    state_root = tmp_path / "state"
    _clone(state_root, canonical, publisher)

    manifest = _manifest(
        [
            AtomEntry(
                source=canonical,
                revision=sha,
                includes=("com.github.example.publisher.constitution",),
            )
        ]
    )
    with pytest.raises(MissingAtomManifestError):
        resolve_constitution_contributions(manifest, state_root)


def test_atom_id_collision_across_two_source_revision_pairs(tmp_path: Path) -> None:
    atom_id = "com.github.example.publisher.constitution"

    canonical_a = "https://github.com/example/publisher-a"
    publisher_a = tmp_path / "publisher-a"
    sha_a = _publish(
        publisher_a,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {atom_id: {"path": "c", "version": "1.0.0"}},
        },
        {
            "c": (
                {
                    "haex_hive_version": "2",
                    "id": atom_id,
                    "version": "1.0.0",
                    "contributes": {"constitution": "constitution.md"},
                },
                b"body-a",
            )
        },
    )
    canonical_b = "https://github.com/example/publisher-b"
    publisher_b = tmp_path / "publisher-b"
    sha_b = _publish(
        publisher_b,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {atom_id: {"path": "c", "version": "1.0.0"}},
        },
        {
            "c": (
                {
                    "haex_hive_version": "2",
                    "id": atom_id,
                    "version": "1.0.0",
                    "contributes": {"constitution": "constitution.md"},
                },
                b"body-b",
            )
        },
    )
    state_root = tmp_path / "state"
    _clone(state_root, canonical_a, publisher_a)
    _clone(state_root, canonical_b, publisher_b)

    manifest = _manifest(
        [
            AtomEntry(source=canonical_a, revision=sha_a, includes=(atom_id,)),
            AtomEntry(source=canonical_b, revision=sha_b, includes=(atom_id,)),
        ]
    )
    with pytest.raises(AtomIdCollisionError):
        resolve_constitution_contributions(manifest, state_root)


def test_same_atom_same_source_revision_is_not_a_collision(tmp_path: Path) -> None:
    """Two atoms[] entries pointing at the SAME (source, revision) and atom-id is fine."""
    canonical = "https://github.com/example/publisher"
    atom_id = "com.github.example.publisher.constitution"
    publisher = tmp_path / "publisher"
    sha = _publish(
        publisher,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {atom_id: {"path": "c", "version": "1.0.0"}},
        },
        {
            "c": (
                {
                    "haex_hive_version": "2",
                    "id": atom_id,
                    "version": "1.0.0",
                    "contributes": {"constitution": "constitution.md"},
                },
                b"body",
            )
        },
    )
    state_root = tmp_path / "state"
    _clone(state_root, canonical, publisher)

    manifest = _manifest(
        [
            AtomEntry(source=canonical, revision=sha, includes=(atom_id,)),
            AtomEntry(source=canonical, revision=sha, includes=(atom_id,)),
        ]
    )
    contributions = resolve_constitution_contributions(manifest, state_root)
    assert len(contributions) == 2
    assert all(c.body == b"body" for c in contributions)


def test_non_contribution_atom_is_filtered_not_errored(tmp_path: Path) -> None:
    canonical = "https://github.com/example/publisher"
    atom_id = "com.github.example.publisher.profile"
    publisher = tmp_path / "publisher"
    sha = _publish(
        publisher,
        {
            "haex_hive_version": "2",
            "publisher": "com.github.example.publisher",
            "atoms": {atom_id: {"path": "c", "version": "1.0.0"}},
        },
        {},
    )
    (publisher / "c").mkdir()
    (publisher / "c" / "manifest.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "2",
                "id": atom_id,
                "version": "1.0.0",
                "includes": ["com.github.example.other.placeholder"],
            }
        )
    )
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "amend: non-contribution atom")
    sha = _git(publisher, "rev-parse", "HEAD")

    state_root = tmp_path / "state"
    _clone(state_root, canonical, publisher)

    manifest = _manifest([AtomEntry(source=canonical, revision=sha, includes=(atom_id,))])
    assert resolve_constitution_contributions(manifest, state_root) == []


def test_canonicalization_idempotence_refusal(tmp_path: Path) -> None:
    """resolve.py defensively re-validates source canonicality (D3, contract text)."""
    non_canonical = "https://github.com/example/publisher.git"
    manifest = _manifest(
        [AtomEntry(source=non_canonical, revision="0" * 40, includes=("com.example.atom",))]
    )
    with pytest.raises(ValueError):
        resolve_constitution_contributions(manifest, tmp_path / "state")


def test_publisher_manifest_not_found(tmp_path: Path) -> None:
    canonical = "https://github.com/example/publisher"
    publisher = tmp_path / "publisher"
    publisher.mkdir()
    _init_repo(publisher)
    (publisher / "README.md").write_text("no manifest here")
    _git(publisher, "add", ".")
    _git(publisher, "commit", "-q", "-m", "no manifest")
    sha = _git(publisher, "rev-parse", "HEAD")

    state_root = tmp_path / "state"
    _clone(state_root, canonical, publisher)

    manifest = _manifest(
        [AtomEntry(source=canonical, revision=sha, includes=("com.example.publisher.atom",))]
    )
    with pytest.raises(MissingPublisherManifestError):
        resolve_constitution_contributions(manifest, state_root)
