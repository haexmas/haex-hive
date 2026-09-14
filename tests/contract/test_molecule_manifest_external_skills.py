"""Contract tests for Spec 018 external skill references."""

from __future__ import annotations

import pytest

from spaex.schema import validator as schema_validator

_SCHEMA = "molecule-manifest.v4.schema.json"


def _valid() -> dict:
    return {
        "spaex_version": "4",
        "id": "com.example.publisher.skills",
        "version": "1.0.0",
        "priority": 100,
        "atoms": {"constitution": ["constitution.md"]},
    }


def _with_external_skills(*references: str) -> dict:
    data = _valid()
    data["external_skills"] = list(references)
    data["install_hook"] = {"interpreter": "python3", "script": "install.py"}
    return data


def test_external_skills_are_valid_metadata() -> None:
    schema_validator.validate(
        _with_external_skills("example-org/example-skills", "https://agentskills.io/demo"),
        _SCHEMA,
    )


def test_external_skills_require_install_hook() -> None:
    data = _valid()
    data["external_skills"] = ["example-org/example-skills"]
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, _SCHEMA)


@pytest.mark.parametrize("category", ["skill", "skills"])
def test_retired_skill_atom_categories_are_rejected(category: str) -> None:
    data = _valid()
    data["atoms"] = {category: ["SKILL.md"]}
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, _SCHEMA)


def test_other_open_atom_categories_remain_valid() -> None:
    data = _valid()
    data["atoms"] = {"instructions": ["instructions.md"]}
    schema_validator.validate(data, _SCHEMA)


@pytest.mark.parametrize("bad", ["", " ", "example\norg/skill", "example\x00org/skill"])
def test_external_skill_references_reject_empty_or_control_values(bad: str) -> None:
    data = _with_external_skills(bad)
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, _SCHEMA)


def test_duplicate_external_skill_references_are_rejected() -> None:
    data = _with_external_skills("example-org/example-skills", "example-org/example-skills")
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, _SCHEMA)
