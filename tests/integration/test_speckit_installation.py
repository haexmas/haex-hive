from __future__ import annotations

import json
import stat
from pathlib import Path

from spaex.constitution.resolve import ResolvedMolecule
from spaex.integrations.speckit import prepare_install
from spaex.model.install_lock import InstallLock, MoleculeEntry
from spaex.model.molecule_manifest import MoleculeManifest


def test_prepare_install_delegates_selected_agent_to_official_cli(tmp_path: Path) -> None:
    calls = tmp_path / "calls.log"
    executable = tmp_path / "specify"
    executable.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "CALLS"
if [ "$1" = version ]; then echo 'CLI Version 0.8.1.dev0'; exit 0; fi
if [ "$1" = integration ] && [ "$2" = list ]; then
  printf '│ claude │ Claude Code │\\n│ codex │ Codex CLI │\\n'
  exit 0
fi
if [ "$1" = integration ] && [ "$2" = install ]; then
  if [ "$3" = claude ]; then
    mkdir -p "$PWD/.claude/skills"
    touch "$PWD/.claude/skills/specify.md"
  fi
  if [ "$3" = codex ]; then
    mkdir -p "$PWD/.agents/skills"
    touch "$PWD/.agents/skills/specify.md"
  fi
  exit 0
fi
exit 2
""".replace("CALLS", calls.as_posix()), encoding="utf-8"
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    manifest = MoleculeManifest.from_json(
        json.dumps(
            {
                "spaex_version": "4",
                "id": "com.example.publisher.speckit",
                "version": "1.0.0",
                "priority": 1,
                "atoms": {},
                "speckit": {
                    "version_constraint": ">=0.8.1",
                    "integrations": {
                        "claude": {"integration_options": "--skills"},
                        "codex": {"integration_options": "--skills"},
                    },
                },
            }
        ).encode()
    )
    resolved = [
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

    records = prepare_install(
        resolved,
        repo_root=tmp_path,
        existing_lock=None,
        explicit_selection="codex",
        executable=str(executable),
    )

    assert (tmp_path / ".agents/skills/specify.md").exists()
    assert not (tmp_path / ".claude/skills/specify.md").exists()
    assert records[manifest.id].outcomes == {"codex": "installed"}
    assert "integration install codex --integration-options=--skills" in calls.read_text()

    lock = InstallLock(
        spaex_version="4",
        generation_id="g_20260914T120000Z_abcd",
        molecules=(
            MoleculeEntry(
                id=manifest.id,
                source="https://example.com/publisher",
                revision="a" * 40,
                paths=(),
                speckit=records[manifest.id],
            ),
        ),
    )
    prepare_install(
        resolved,
        repo_root=tmp_path,
        existing_lock=lock,
        explicit_selection=None,
        executable=str(executable),
    )
    assert calls.read_text().splitlines().count(
        "integration install codex --integration-options=--skills"
    ) == 1

    prepare_install(
        resolved,
        repo_root=tmp_path,
        existing_lock=lock,
        explicit_selection="all",
        executable=str(executable),
    )
    assert (tmp_path / ".claude/skills/specify.md").exists()
