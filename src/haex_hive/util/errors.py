"""Typed exception hierarchy for every diagnostic emitted by `haex`.

Each subclass carries its canonical diagnostic key (used by `emit_refuse`) and
its canonical exit code from `haex_hive.util.exit_codes`. Every CLI contract
diagnostic path is represented; no CLI handler is allowed to invent a new key
or exit code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from haex_hive.util import exit_codes


@dataclass
class HaexError(Exception):
    """Base for every diagnostic emitted by the CLI.

    Subclasses set `diagnostic_key` and `exit_code` as class attributes.
    Instances may attach a machine-parseable `context` dict with fields such
    as `entry`, `atom_id`, or `field_path`; the values are formatted by
    `emit_refuse` without leaking secret payload contents.
    """

    message: str = ""
    context: dict[str, str] = field(default_factory=dict)

    diagnostic_key: str = ""
    exit_code: int = 1
    hint: str = ""

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message or self.diagnostic_key)


# --- Migrate boundary --------------------------------------------------------


@dataclass
class CredentialInUrlError(HaexError):
    diagnostic_key: str = "credential-in-source-url"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Remove credentials from the URL. Configure git to use a credential helper instead."


@dataclass
class UnsupportedSchemeError(HaexError):
    diagnostic_key: str = "unsupported-source-scheme"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Use https:// or ssh:// for the atom source."


@dataclass
class PermissionOnlyEntryError(HaexError):
    diagnostic_key: str = "permission-only-entry"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Permission-only entries cannot be widened into v2 atom grants."


@dataclass
class IdentityMismatchError(HaexError):
    diagnostic_key: str = "identity-not-github-nor-reverse-dns"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Provide a reverse-DNS identity or a GitHub org/user identity."


@dataclass
class InvalidHaexHiveManifestError(HaexError):
    diagnostic_key: str = "haex-hive-json-invalid"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Fix .haex-hive.json and retry the migration."


@dataclass
class MissingRemoteOriginError(HaexError):
    diagnostic_key: str = "missing-remote-origin"
    exit_code: int = exit_codes.IO_REFUSE
    hint: str = "Configure `git remote add origin` before running migrate."


@dataclass
class MissingPublisherManifestError(HaexError):
    diagnostic_key: str = "publisher-manifest-not-found"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Verify the publisher declares manifest.json at the pinned revision."


@dataclass
class MissingAtomManifestError(HaexError):
    diagnostic_key: str = "atom-manifest-not-found"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Verify the atom declares its manifest.json at the pinned revision."


@dataclass
class AtomIdCollisionError(HaexError):
    diagnostic_key: str = "atom-id-collision"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Two different (source, revision) pairs map to the same atom-id."


@dataclass
class VersionBelowMinError(HaexError):
    diagnostic_key: str = "haex-hive-version-below-min"
    exit_code: int = exit_codes.SYSTEM_REFUSE
    hint: str = "Upgrade the installed haex-hive to satisfy `haex_hive_min_version`."


@dataclass
class NoSourcesDeclaredError(HaexError):
    diagnostic_key: str = "no-sources-declared"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Add at least one atom that contributes a constitution."


@dataclass
class ConstitutionNotAssembledError(HaexError):
    diagnostic_key: str = "constitution-not-assembled"
    exit_code: int = exit_codes.INPUT_REFUSE
    hint: str = "Run `haex constitution assemble` first."


@dataclass
class InstallLockMissingError(HaexError):
    diagnostic_key: str = "install-lock-missing"
    exit_code: int = exit_codes.IO_REFUSE
    hint: str = "Run `haex constitution assemble` to (re)generate install.lock."


@dataclass
class InstallLockSchemaInvalidError(HaexError):
    diagnostic_key: str = "install-lock-schema-invalid"
    exit_code: int = exit_codes.VALIDATION_REFUSE
    hint: str = "Regenerate install.lock via `haex constitution assemble`."


@dataclass
class InstallLockSourcesNotCanonicalError(HaexError):
    diagnostic_key: str = "install-lock-sources-not-canonical"
    exit_code: int = exit_codes.VALIDATION_REFUSE
    hint: str = "Regenerate install.lock via `haex constitution assemble`."


@dataclass
class ConstitutionIntegrityMismatchError(HaexError):
    diagnostic_key: str = "constitution-integrity-mismatch"
    exit_code: int = exit_codes.POST_WRITE_VALIDATION
    hint: str = "Run `git pull` or `haex constitution assemble` to restore a matched generation."


@dataclass
class IncompleteAssemblyTransactionError(HaexError):
    diagnostic_key: str = "constitution-transaction-incomplete"
    exit_code: int = exit_codes.INCOMPLETE_TRANSACTION
    hint: str = "Run `haex constitution assemble` to recover the paired output generation."


@dataclass
class PublisherCloneUnavailableError(HaexError):
    diagnostic_key: str = "publisher-clone-unavailable"
    exit_code: int = exit_codes.IO_REFUSE
    hint: str = "Ensure the publisher clone exists under $HAEX_HIVE_STATE/repos/."


@dataclass
class PinnedRevisionNotFoundError(HaexError):
    diagnostic_key: str = "pinned-revision-not-found"
    exit_code: int = exit_codes.IO_REFUSE
    hint: str = "Fetch the missing revision into the publisher clone."


@dataclass
class ContributionFileNotFoundError(HaexError):
    diagnostic_key: str = "contribution-file-not-found"
    exit_code: int = exit_codes.IO_REFUSE
    hint: str = "Verify the declared contribution path exists at the pinned revision."


@dataclass
class PostWriteValidationError(HaexError):
    diagnostic_key: str = "post-write-validation-failed"
    exit_code: int = exit_codes.POST_WRITE_VALIDATION
    hint: str = "Investigate storage-layer corruption; both output files were rolled back."


@dataclass
class LlmRequiredForMultiSourceError(HaexError):
    diagnostic_key: str = "llm-required-for-multi-source"
    exit_code: int = exit_codes.VALIDATION_REFUSE
    hint: str = "Run on a device with LLM access, or pass --llm=file for the two-phase flow."


@dataclass
class MergeNotConfirmedError(HaexError):
    diagnostic_key: str = "merge-not-confirmed"
    exit_code: int = exit_codes.MERGE_NOT_CONFIRMED
    hint: str = "Send `--haex-confirm: yes\\n` after reviewing the candidate."


@dataclass
class PendingMergeInputsMismatchError(HaexError):
    diagnostic_key: str = "pending-merge-inputs-mismatch"
    exit_code: int = exit_codes.PENDING_MERGE_INPUTS_MISMATCH
    hint: str = "Re-run `haex constitution assemble --llm=file` to refresh pending inputs."


@dataclass
class ConstitutionWriterBusyError(HaexError):
    diagnostic_key: str = "constitution-writer-busy"
    exit_code: int = exit_codes.WRITER_BUSY
    hint: str = "Another `haex constitution assemble` is running; retry after it releases the lock."


@dataclass
class PlaintextSecretDetectedError(HaexError):
    diagnostic_key: str = "plaintext-secret-detected"
    exit_code: int = exit_codes.PLAINTEXT_SECRET
    hint: str = "Remove the secret; commit no plaintext credentials."


@dataclass
class TerminalUnsafeContributionError(HaexError):
    diagnostic_key: str = "terminal-unsafe-contribution"
    exit_code: int = exit_codes.TERMINAL_UNSAFE_CONTRIBUTION
    hint: str = "Reject terminal control characters other than LF and TAB."


@dataclass
class ConstitutionConcealmentInstructionError(HaexError):
    diagnostic_key: str = "constitution-concealment-instruction"
    exit_code: int = exit_codes.CONSTITUTION_CONCEALMENT
    hint: str = "Reject candidates instructing agents to conceal or withhold information."


@dataclass
class UsageError(HaexError):
    diagnostic_key: str = "usage"
    exit_code: int = exit_codes.USAGE
    hint: str = ""
