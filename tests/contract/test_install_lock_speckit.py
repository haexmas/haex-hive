from __future__ import annotations

import json

import pytest

from spaex.model.install_lock import InstallLock, MoleculeEntry, SpeckitLockRecord
from spaex.schema import validator as schema_validator
from spaex.util.errors import InstallLockSchemaInvalidError


def test_install_lock_round_trips_speckit_record() -> None:
    lock = InstallLock(
        spaex_version="4",
        generation_id="g_20260914T120000Z_abcd",
        molecules=(
            MoleculeEntry(
                id="com.example.publisher.speckit",
                source="https://github.com/example/publisher",
                revision="0" * 40,
                paths=(),
                speckit=SpeckitLockRecord(
                    cli_version="0.8.1",
                    declaration_fingerprint="sha256:" + "a" * 64,
                    selected=("codex", "claude"),
                    outcomes={"claude": "installed", "codex": "already_satisfied"},
                ),
            ),
        ),
    )
    encoded = lock.to_json_bytes()
    decoded = InstallLock.from_json(encoded)
    assert decoded.molecules[0].speckit is not None
    assert decoded.molecules[0].speckit.selected == ("claude", "codex")
    schema_validator.validate(__import__("json").loads(encoded), "install-lock.v4.schema.json")


def test_invalid_speckit_outcome_is_rejected_by_schema() -> None:
    data = {
        "spaex_version": "4",
        "generation_id": "g_20260914T120000Z_abcd",
        "molecules": [
            {
                "id": "com.example.publisher.speckit",
                "source": "https://github.com/example/publisher",
                "revision": "0" * 40,
                "paths": [],
                "speckit": {
                    "cli_version": "0.8.1",
                    "declaration_fingerprint": "sha256:" + "a" * 64,
                    "selected": ["codex"],
                    "outcomes": {"codex": "failed"},
                },
            }
        ],
    }
    with pytest.raises(schema_validator.SchemaValidationError):
        schema_validator.validate(data, "install-lock.v4.schema.json")


@pytest.mark.parametrize("outcomes", [{}, {"codex": "skipped"}])
def test_selected_speckit_requires_successful_outcome(outcomes: dict[str, str]) -> None:
    data = {
        "spaex_version": "4",
        "generation_id": "g_20260914T120000Z_abcd",
        "molecules": [
            {
                "id": "com.example.publisher.speckit",
                "source": "https://github.com/example/publisher",
                "revision": "0" * 40,
                "paths": [],
                "speckit": {
                    "cli_version": "0.8.1",
                    "declaration_fingerprint": "sha256:" + "a" * 64,
                    "selected": ["codex"],
                    "outcomes": outcomes,
                },
            }
        ],
    }

    with pytest.raises(InstallLockSchemaInvalidError):
        InstallLock.from_json(json.dumps(data).encode())
