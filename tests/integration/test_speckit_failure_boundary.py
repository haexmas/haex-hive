from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from spaex.constitution.resolve import ResolvedMolecule
from spaex.integrations.speckit import prepare_install
from spaex.model.molecule_manifest import MoleculeManifest
from spaex.util.errors import (
    SpeckitCliFailedError,
    SpeckitCliMissingError,
    SpeckitCliVersionIncompatibleError,
    SpeckitIntegrationUnsupportedError,
)


def _resolved(tmp_path: Path, *, integration_key: str = "codex") -> list[ResolvedMolecule]:
    manifest = MoleculeManifest.from_json(
        json.dumps(
            {
                "spaex_version": "4",
                "id": "com.example.speckit",
                "version": "1.0.0",
                "priority": 1,
                "atoms": {},
                "speckit": {
                    "version_constraint": "0.8.1",
                    "integrations": {
                        integration_key: {"integration_options": "--skills"}
                    },
                },
            }
        ).encode()
    )
    return [
        ResolvedMolecule(
            molecule_id=manifest.id,
            source_url="https://example.com/publisher",
            revision="a" * 40,
            repo_dir=tmp_path,
            molecule_path="molecule",
            install_hook=None,
            effective_priority=1,
            molecule_manifest=manifest,
            cache_dir=tmp_path,
        )
    ]


def _cli(tmp_path: Path, *, version: str = "0.8.1", fail_install: bool = False) -> Path:
    executable = tmp_path / "specify"
    install = (
        "touch \"$PWD/.agents/skills/partial.md\"; exit 7"
        if fail_install
        else "touch \"$PWD/.agents/skills/specify.md\"; exit 0"
    )
    executable.write_text(
        f"""#!/bin/sh
if [ \"$1\" = version ]; then echo 'CLI Version {version}'; exit 0; fi
if [ \"$1\" = integration ] && [ \"$2\" = list ]; then echo '│ codex │ Codex CLI │'; exit 0; fi
if [ \"$1\" = integration ] && [ \"$2\" = install ]; then
  mkdir -p \"$PWD/.agents/skills\"
  {install}
fi
exit 2
"""
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def test_missing_cli_is_typed(tmp_path: Path) -> None:
    with pytest.raises(SpeckitCliMissingError):
        prepare_install(
            _resolved(tmp_path, integration_key="gemini"),
            repo_root=tmp_path,
            existing_lock=None,
            explicit_selection="gemini",
            executable=str(tmp_path / "missing"),
        )


def test_incompatible_cli_is_typed(tmp_path: Path) -> None:
    with pytest.raises(SpeckitCliVersionIncompatibleError):
        prepare_install(
            _resolved(tmp_path),
            repo_root=tmp_path,
            existing_lock=None,
            explicit_selection="codex",
            executable=str(_cli(tmp_path, version="0.7.0")),
        )


def test_unsupported_selection_is_rejected_before_install(tmp_path: Path) -> None:
    with pytest.raises(SpeckitIntegrationUnsupportedError):
        prepare_install(
            _resolved(tmp_path, integration_key="gemini"),
            repo_root=tmp_path,
            existing_lock=None,
            explicit_selection="gemini",
            executable=str(_cli(tmp_path)),
        )


def test_failed_official_install_preserves_external_boundary(tmp_path: Path) -> None:
    executable = _cli(tmp_path, fail_install=True)
    with pytest.raises(SpeckitCliFailedError):
        prepare_install(
            _resolved(tmp_path),
            repo_root=tmp_path,
            existing_lock=None,
            explicit_selection="codex",
            executable=str(executable),
        )
    assert (tmp_path / ".agents/skills/partial.md").exists()
