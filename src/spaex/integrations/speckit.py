"""Typed boundary around the official Spec Kit integration installer.

spaex owns declaration validation, selection, provenance, and diagnostics. The
official ``specify`` CLI owns agent-specific files, layouts, and conflict
behavior; this module never copies a Spec Kit skill itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TextIO

from spaex.constitution.resolve import ResolvedMolecule
from spaex.model.install_lock import InstallLock, SpeckitLockRecord, SpeckitOutcomeStatus
from spaex.model.molecule_manifest import SpeckitDeclaration
from spaex.util.errors import (
    SpeckitCliFailedError,
    SpeckitCliMissingError,
    SpeckitCliVersionIncompatibleError,
    SpeckitDeclarationConflictError,
    SpeckitIntegrationUnsupportedError,
    SpeckitSelectionRequiredError,
)

_VERSION_RE = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")
_KEY_RE = re.compile(r"^│\s*([a-z0-9][a-z0-9-]*)\s+│")


@dataclass(frozen=True)
class SpeckitCliResult:
    """Captured result from one official CLI command."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class SpeckitInstallRecords(Mapping[str, SpeckitLockRecord]):
    """CLI results plus the lock records safe to publish for this run."""

    results: Mapping[str, SpeckitLockRecord]
    publication_records: Mapping[str, SpeckitLockRecord]

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", MappingProxyType(dict(self.results)))
        object.__setattr__(
            self,
            "publication_records",
            MappingProxyType(dict(self.publication_records)),
        )

    def __getitem__(self, key: str) -> SpeckitLockRecord:
        return self.results[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)


def parse_version_output(output: str) -> tuple[int, int, int]:
    """Extract the first semantic version from official CLI output."""
    match = _VERSION_RE.search(output)
    if match is None:
        raise ValueError("specify output did not contain a semantic version")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def parse_supported_integrations(output: str) -> tuple[str, ...]:
    """Parse integration keys from the official table output."""
    keys = sorted(
        {
            match.group(1)
            for line in output.splitlines()
            if (match := _KEY_RE.search(line))
        }
    )
    return tuple(keys)


def parse_selection(raw: str, declared: set[str] | Sequence[str]) -> tuple[str, ...]:
    """Parse ``all``, ``none``, or a comma-separated declared-key selection."""
    declared_set = set(declared)
    value = raw.strip().lower()
    if value == "all":
        return tuple(sorted(declared_set))
    if value in {"", "none"}:
        return ()
    selected = tuple(sorted({part.strip() for part in value.split(",") if part.strip()}))
    unknown = sorted(set(selected) - declared_set)
    if unknown:
        raise ValueError(f"unknown Spec Kit integration(s): {', '.join(unknown)}")
    return selected


def select_integrations(
    explicit: str | None,
    declared: Sequence[str],
    *,
    persisted: Sequence[str] | None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> tuple[str, ...]:
    """Apply explicit, persisted, interactive, then non-interactive selection precedence."""
    if explicit is not None:
        try:
            return parse_selection(explicit, declared)
        except ValueError as exc:
            raise SpeckitSelectionRequiredError(message=str(exc)) from exc
    if persisted is not None:
        try:
            return parse_selection(",".join(persisted), declared)
        except ValueError as exc:
            raise SpeckitSelectionRequiredError(message=str(exc)) from exc

    input_stream = stdin if stdin is not None else sys.stdin
    output_stream = stdout if stdout is not None else sys.stdout
    if stdin is None and not input_stream.isatty():
        raise SpeckitSelectionRequiredError(
            message=(
                "Spec Kit integrations are declared but no selection was provided; "
                "use --speckit-agents or --no-speckit-integrations"
            ),
            context={"available": ",".join(sorted(declared))},
        )
    output_stream.write("Spec Kit integrations:\n")
    output_stream.write("  " + ", ".join(sorted(declared)) + "\n")
    output_stream.write("Select integrations (all, none, or comma-separated keys): ")
    output_stream.flush()
    try:
        raw = input_stream.readline()
    except OSError as exc:
        raise SpeckitSelectionRequiredError(message=f"could not read selection: {exc}") from exc
    try:
        return parse_selection(raw, declared)
    except ValueError as exc:
        raise SpeckitSelectionRequiredError(message=str(exc)) from exc


def declaration_fingerprint(
    declaration: SpeckitDeclaration,
    source: str,
    revision: str,
    config: Mapping[str, object] | None = None,
) -> str:
    """Hash the declaration and immutable molecule identity canonically."""
    payload = {
        "declaration": {
            "version_constraint": _constraint_text(declaration),
            "integrations": dict(sorted(declaration.integrations.items())),
        },
        "source": source,
        "revision": revision,
        "config": dict(config or {}),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_install_argv(executable: str, key: str, options: str) -> list[str]:
    """Build a shell-free official install invocation."""
    argv = [executable, "integration", "install", key]
    if options:
        argv.append(f"--integration-options={options}")
    return argv


def run_cli(
    argv: Sequence[str],
    *,
    repo_root: Path,
    capture_output: bool = True,
) -> SpeckitCliResult:
    """Run one official CLI command with inherited visible output semantics."""
    try:
        if capture_output:
            completed = subprocess.run(
                list(argv),
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            completed = subprocess.run(
                list(argv),
                cwd=repo_root,
                text=True,
                check=False,
            )
    except FileNotFoundError as exc:
        raise SpeckitCliMissingError(
            message="the official `specify` executable was not found on PATH",
            context={"executable": argv[0]},
        ) from exc
    except OSError as exc:
        raise SpeckitCliFailedError(
            message=f"could not launch official Spec Kit CLI: {exc}",
            context={"command": " ".join(argv)},
        ) from exc
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if capture_output and stdout:
        sys.stdout.write(stdout)
    if capture_output and stderr:
        sys.stderr.write(stderr)
    return SpeckitCliResult(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def verify_cli(
    declaration: SpeckitDeclaration,
    *,
    repo_root: Path,
    executable: str = "specify",
) -> tuple[str, tuple[str, ...]]:
    """Verify CLI version and supported keys before any install invocation."""
    version_result = run_cli([executable, "version"], repo_root=repo_root)
    if version_result.returncode != 0:
        raise SpeckitCliFailedError(
            message="official `specify version` failed",
            context={"exit_code": str(version_result.returncode)},
        )
    try:
        version = parse_version_output(version_result.stdout + "\n" + version_result.stderr)
    except ValueError as exc:
        raise SpeckitCliVersionIncompatibleError(message=str(exc)) from exc
    if not declaration.version_constraint.satisfied_by(version):
        version_text = ".".join(str(part) for part in version)
        raise SpeckitCliVersionIncompatibleError(
            message=(
                f"specify CLI {version_text} does not satisfy "
                f"{_constraint_text(declaration)!r}"
            ),
            context={"installed": version_text, "required": _constraint_text(declaration)},
        )

    list_result = run_cli([executable, "integration", "list"], repo_root=repo_root)
    if list_result.returncode != 0:
        raise SpeckitCliFailedError(
            message="official `specify integration list` failed",
            context={"exit_code": str(list_result.returncode)},
        )
    return ".".join(str(part) for part in version), parse_supported_integrations(
        list_result.stdout
    )


def install_selected(
    declaration: SpeckitDeclaration,
    selected: Sequence[str],
    *,
    repo_root: Path,
    cli_version: str,
    executable: str = "specify",
) -> dict[str, SpeckitOutcomeStatus]:
    """Install selected integrations serially through the official CLI."""
    outcomes: dict[str, SpeckitOutcomeStatus] = {}
    for key in sorted(selected):
        result = run_cli(
            build_install_argv(executable, key, declaration.integrations[key]),
            repo_root=repo_root,
            capture_output=False,
        )
        if result.returncode != 0:
            raise SpeckitCliFailedError(
                message=f"official Spec Kit installation failed for {key!r}",
                context={"integration": key, "exit_code": str(result.returncode)},
            )
        outcomes[key] = "installed"
    return outcomes


def ensure_supported(selected: Sequence[str], supported: Sequence[str]) -> None:
    """Refuse unsupported keys before any integration install command."""
    unsupported = sorted(set(selected) - set(supported))
    if unsupported:
        raise SpeckitIntegrationUnsupportedError(
            message=(
                f"Spec Kit integration(s) not supported by this CLI: {', '.join(unsupported)}"
            ),
            context={"unsupported": ",".join(unsupported), "available": ",".join(supported)},
        )


def emit_results(records: Mapping[str, SpeckitLockRecord]) -> None:
    """Emit one stable JSON result object for each declared integration."""
    outcomes = [
        {
            "integration": integration,
            "status": status,
            "cli_version": record.cli_version,
            "molecule": molecule_id,
        }
        for molecule_id, record in sorted(records.items())
        for integration, status in sorted(record.outcomes.items())
    ]
    if outcomes:
        sys.stdout.write(json.dumps({"speckit": outcomes}, sort_keys=True) + "\n")


def prepare_install(
    resolved: Sequence[ResolvedMolecule],
    *,
    repo_root: Path,
    existing_lock: InstallLock | None,
    explicit_selection: str | None = None,
    disabled: bool = False,
    executable: str = "specify",
) -> SpeckitInstallRecords:
    """Validate declarations, select agents, and install external integrations.

    ``resolved`` is intentionally accepted as a sequence of resolver records
    with the small public attributes used here. Keeping this adapter at the
    resolver boundary avoids coupling the external CLI to constitution files.
    """
    declarations = [
        record
        for record in resolved
        if getattr(getattr(record, "molecule_manifest", None), "speckit", None)
        is not None
    ]
    if not declarations:
        return SpeckitInstallRecords({}, {})

    first_manifest = declarations[0].molecule_manifest
    assert first_manifest is not None
    first = first_manifest.speckit
    assert first is not None
    for record in declarations[1:]:
        manifest = record.molecule_manifest
        assert manifest is not None
        declaration = manifest.speckit
        assert declaration is not None
        if declaration != first:
            raise SpeckitDeclarationConflictError(
                message="adopted molecules declare incompatible Spec Kit policies",
                context={
                    "molecules": ",".join(
                        sorted(r.molecule_id for r in declarations)
                    )
                },
            )

    fingerprints = {
        record.molecule_id: declaration_fingerprint(
            first, record.source_url, record.revision
        )
        for record in declarations
    }
    existing_by_id = {
        entry.id: entry.speckit
        for entry in (existing_lock.molecules if existing_lock is not None else ())
        if entry.speckit is not None
    }
    persisted: tuple[str, ...] | None = None
    for record in declarations:
        previous = existing_by_id.get(record.molecule_id)
        if (
            previous is not None
            and previous.declaration_fingerprint == fingerprints[record.molecule_id]
        ):
            persisted = previous.selected
            break

    if disabled:
        skipped_records = {
            record.molecule_id: SpeckitLockRecord(
                cli_version="not-run",
                declaration_fingerprint=fingerprints[record.molecule_id],
                selected=(),
                outcomes={key: "skipped" for key in first.integrations},
            )
            for record in declarations
        }
        publication_records = {
            record.molecule_id: (
                previous
                if (previous := existing_by_id.get(record.molecule_id)) is not None
                and previous.declaration_fingerprint == fingerprints[record.molecule_id]
                else skipped_records[record.molecule_id]
            )
            for record in declarations
        }
        return SpeckitInstallRecords(skipped_records, publication_records)

    selected = select_integrations(
        explicit_selection,
        tuple(first.integrations),
        persisted=persisted,
    )
    if not selected:
        skipped_records = {
            record.molecule_id: SpeckitLockRecord(
                cli_version="not-run",
                declaration_fingerprint=fingerprints[record.molecule_id],
                selected=(),
                outcomes={key: "skipped" for key in first.integrations},
            )
            for record in declarations
        }
        return SpeckitInstallRecords(skipped_records, skipped_records)

    cli_version, supported = verify_cli(first, repo_root=repo_root, executable=executable)
    ensure_supported(selected, supported)
    existing_for_first = existing_by_id.get(declarations[0].molecule_id)
    already_selected = (
        existing_for_first is not None
        and existing_for_first.declaration_fingerprint == fingerprints[declarations[0].molecule_id]
        and existing_for_first.cli_version == cli_version
    )
    previous_selected = (
        existing_for_first.selected if already_selected and existing_for_first else ()
    )
    new_keys = tuple(
        key for key in selected if not already_selected or key not in previous_selected
    )
    outcomes = install_selected(
        first,
        new_keys,
        repo_root=repo_root,
        cli_version=cli_version,
        executable=executable,
    )
    if existing_for_first is not None and already_selected:
        outcomes = {
            **dict(existing_for_first.outcomes),
            **outcomes,
        }
    records = {
        record.molecule_id: SpeckitLockRecord(
            cli_version=cli_version,
            declaration_fingerprint=fingerprints[record.molecule_id],
            selected=selected,
            outcomes={key: outcomes.get(key, "already_satisfied") for key in selected},
        )
        for record in declarations
    }
    return SpeckitInstallRecords(records, records)


def _constraint_text(declaration: SpeckitDeclaration) -> str:
    operator = declaration.version_constraint.operator
    major, minor, patch = declaration.version_constraint.version
    return f"{operator if operator == '>=' else ''}{major}.{minor}.{patch}"


__all__ = [
    "SpeckitCliResult",
    "SpeckitInstallRecords",
    "build_install_argv",
    "declaration_fingerprint",
    "emit_results",
    "ensure_supported",
    "install_selected",
    "parse_selection",
    "parse_supported_integrations",
    "parse_version_output",
    "run_cli",
    "select_integrations",
    "verify_cli",
]
