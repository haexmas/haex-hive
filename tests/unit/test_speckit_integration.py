from __future__ import annotations

import io
import json
import sys

import pytest

from spaex.integrations.speckit import (
    build_install_argv,
    declaration_fingerprint,
    emit_results,
    parse_selection,
    parse_version_output,
    resolve_cli_executable,
    run_cli,
    select_integrations,
)
from spaex.model.install_lock import SpeckitLockRecord
from spaex.model.molecule_manifest import SpeckitCliProvisioning, SpeckitDeclaration
from spaex.model.version_constraint import VersionConstraint
from spaex.util.errors import (
    SpeckitCliFailedError,
    SpeckitCliMissingError,
    SpeckitCliVersionIncompatibleError,
    SpeckitDeclarationConflictError,
    SpeckitDeclarationInvalidError,
    SpeckitIntegrationUnsupportedError,
    SpeckitSelectionRequiredError,
)


class _TtyInput(io.StringIO):
    def isatty(self) -> bool:
        return True


def _declaration() -> SpeckitDeclaration:
    return SpeckitDeclaration(
        version_constraint=VersionConstraint.parse("0.8.1"),
        integrations={"claude": "", "codex": "--skills"},
        cli=SpeckitCliProvisioning(
            package="specify-cli",
            version=VersionConstraint.parse("0.8.1"),
        ),
    )


def test_parse_version_output_accepts_official_cli_text() -> None:
    assert parse_version_output("CLI Version    0.8.1.dev0") == (0, 8, 1)


def test_selection_parser_canonicalizes_and_rejects_unknown() -> None:
    assert parse_selection("codex,claude", {"claude", "codex"}) == ("claude", "codex")
    with pytest.raises(ValueError):
        parse_selection("gemini", {"claude", "codex"})


def test_selection_requires_input_in_noninteractive_mode() -> None:
    with pytest.raises(SpeckitSelectionRequiredError):
        select_integrations(
            None,
            ("claude", "codex"),
            persisted=None,
        )


def test_selection_prompt_accepts_all() -> None:
    output = io.StringIO()
    selected = select_integrations(
        None,
        ("claude", "codex"),
        persisted=None,
        stdin=_TtyInput("all\n"),
        stdout=output,
    )
    assert selected == ("claude", "codex")
    assert "claude" in output.getvalue()


def test_install_argv_passes_options_as_one_argument() -> None:
    assert build_install_argv("specify", "codex", "--skills") == [
        "specify",
        "integration",
        "install",
        "codex",
        "--integration-options=--skills",
    ]


def test_provisioned_cli_uses_uv_tool_run_with_exact_package() -> None:
    assert resolve_cli_executable(_declaration()) == [
        sys.executable,
        "-m",
        "uv",
        "tool",
        "run",
        "--from",
        "specify-cli==0.8.1",
        "specify",
    ]


def test_install_cli_output_is_streamed(monkeypatch, tmp_path) -> None:
    calls = {}

    class Completed:
        returncode = 0
        stdout = None
        stderr = None

    def fake_run(argv, **kwargs):
        calls.update(kwargs)
        return Completed()

    monkeypatch.setattr("spaex.integrations.speckit.subprocess.run", fake_run)
    run_cli(
        ["specify", "integration", "install", "codex"],
        repo_root=tmp_path,
        capture_output=False,
    )

    assert "capture_output" not in calls


def test_declaration_fingerprint_is_stable() -> None:
    first = declaration_fingerprint(_declaration(), "https://example.com/p", "a" * 40)
    second = declaration_fingerprint(_declaration(), "https://example.com/p", "a" * 40)
    assert first == second
    assert first.startswith("sha256:")


@pytest.mark.parametrize(
    ("error_type", "key"),
    [
        (SpeckitDeclarationInvalidError, "speckit-declaration-invalid"),
        (SpeckitCliMissingError, "speckit-cli-missing"),
        (SpeckitCliVersionIncompatibleError, "speckit-cli-version-incompatible"),
        (SpeckitIntegrationUnsupportedError, "speckit-integration-unsupported"),
        (SpeckitSelectionRequiredError, "speckit-selection-required"),
        (SpeckitCliFailedError, "speckit-cli-failed"),
        (SpeckitDeclarationConflictError, "speckit-declaration-conflict"),
    ],
)
def test_documented_diagnostic_keys_are_stable(error_type, key: str) -> None:
    assert error_type(message="test").diagnostic_key == key


def test_machine_readable_result_contains_one_entry_per_outcome(capsys) -> None:
    emit_results(
        {
            "com.example.speckit": SpeckitLockRecord(
                cli_version="0.8.1",
                declaration_fingerprint="sha256:" + "a" * 64,
                selected=("codex",),
                outcomes={"codex": "installed"},
            )
        }
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["speckit"] == [
        {
            "cli_version": "0.8.1",
            "integration": "codex",
            "molecule": "com.example.speckit",
            "status": "installed",
        }
    ]
