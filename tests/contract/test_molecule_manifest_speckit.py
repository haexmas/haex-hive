from __future__ import annotations

import json
from typing import Any

import pytest

from spaex.model.molecule_manifest import MoleculeManifest
from spaex.schema import validator as schema_validator


def _valid() -> dict[str, Any]:
    return {
        "spaex_version": "4",
        "id": "com.example.publisher.speckit",
        "version": "1.0.0",
        "priority": 100,
        "atoms": {},
        "speckit": {
            "version_constraint": ">=0.8.1",
            "force": True,
            "cli": {"package": "specify-cli", "version": "0.8.1"},
            "integrations": {
                "claude": {"integration_options": "--skills"},
                "codex": {"integration_options": "--skills"},
            },
        },
    }


def test_speckit_only_manifest_is_valid_and_parsed() -> None:
    parsed = MoleculeManifest.from_json(json.dumps(_valid()).encode())
    assert parsed.speckit is not None
    assert parsed.speckit.version_constraint.operator == ">="
    assert parsed.speckit.integrations["codex"] == "--skills"
    assert parsed.speckit.cli is not None
    assert parsed.speckit.cli.package == "specify-cli"
    assert parsed.speckit.cli.version.version == (0, 8, 1)
    assert parsed.speckit.force is True


def test_empty_atoms_without_speckit_remains_invalid() -> None:
    data = _valid()
    del data["speckit"]
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, "molecule-manifest.v4.schema.json")


def test_integration_key_must_be_a_lowercase_identifier() -> None:
    data = _valid()
    data["speckit"]["integrations"]["Codex CLI"] = {}
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, "molecule-manifest.v4.schema.json")


@pytest.mark.parametrize("option", ["--global", "--project", "foo && bar", "foo\nbar"])
def test_unsafe_speckit_option_is_rejected(option: str) -> None:
    data = _valid()
    data["speckit"]["integrations"]["codex"]["integration_options"] = option
    with pytest.raises(ValueError):
        MoleculeManifest.from_json(json.dumps(data).encode())


def test_cli_version_must_be_exact_and_satisfy_policy() -> None:
    data = _valid()
    data["speckit"]["cli"]["version"] = ">=0.8.1"
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, "molecule-manifest.v4.schema.json")

    data["speckit"]["cli"]["version"] = "0.7.0"
    with pytest.raises(ValueError, match="satisfy version_constraint"):
        MoleculeManifest.from_json(json.dumps(data).encode())


def test_force_must_be_boolean() -> None:
    data = _valid()
    data["speckit"]["force"] = "yes"
    with pytest.raises(schema_validator.SchemaValidationError, match="force.*boolean"):
        MoleculeManifest.from_json(json.dumps(data).encode())
