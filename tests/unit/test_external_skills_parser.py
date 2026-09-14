"""Parser tests for Spec 018 external skill references."""

from __future__ import annotations

import json

import pytest

from spaex.model.molecule_manifest import MoleculeManifest


def _base() -> dict:
    return {
        "spaex_version": "4",
        "id": "com.example.publisher.skills",
        "version": "1.0.0",
        "priority": 100,
        "atoms": {"constitution": ["constitution.md"]},
    }


def test_external_skills_preserve_order_and_are_immutable() -> None:
    data = _base()
    data["external_skills"] = [
        "example-org/first",
        "https://agentskills.io/second",
    ]
    data["install_hook"] = {"interpreter": "python3", "script": "install.py"}

    parsed = MoleculeManifest.from_json(json.dumps(data).encode())

    assert parsed.external_skills == (
        "example-org/first",
        "https://agentskills.io/second",
    )
    assert isinstance(parsed.external_skills, tuple)


def test_missing_external_skills_parses_to_empty_tuple() -> None:
    parsed = MoleculeManifest.from_json(json.dumps(_base()).encode())
    assert parsed.external_skills == ()


def test_external_skills_without_hook_are_rejected_before_install() -> None:
    data = _base()
    data["external_skills"] = ["example-org/first"]

    with pytest.raises(ValueError, match="install_hook"):
        MoleculeManifest.from_json(json.dumps(data).encode())
