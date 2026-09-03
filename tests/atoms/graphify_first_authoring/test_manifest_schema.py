"""Schema check for this molecule's manifest.json (T007, FR-001).

Validates the molecule's manifest against Spec 007's canonical
``molecule-manifest.v3.schema.json`` using the repo's existing ``jsonschema``
dependency, without pulling in any haex-hive CLI machinery.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOLECULE_DIR = _REPO_ROOT / ".specify" / "molecules" / "graphify-first-authoring"
_MOLECULE_MANIFEST = _MOLECULE_DIR / "manifest.json"
_SCHEMA = (
    _REPO_ROOT
    / "specs"
    / "007-unified-manifest-v2"
    / "contracts"
    / "molecule-manifest.v3.schema.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_conforms_to_v3_schema() -> None:
    schema = _load_json(_SCHEMA)
    manifest = _load_json(_MOLECULE_MANIFEST)
    jsonschema.validate(instance=manifest, schema=schema)


def test_manifest_declares_expected_identity() -> None:
    manifest = _load_json(_MOLECULE_MANIFEST)
    assert manifest["id"] == "com.github.haexmas.haex-hive.graphify-first-authoring"
    assert manifest["haex_hive_version"] == "3"
    assert manifest["atoms"]["constitution"] == ["constitution.md"]


def test_contributed_constitution_file_exists() -> None:
    manifest = _load_json(_MOLECULE_MANIFEST)
    rel = manifest["atoms"]["constitution"][0]
    assert (_MOLECULE_MANIFEST.parent / rel).is_file()
