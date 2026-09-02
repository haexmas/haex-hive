"""Install-specific `HaexError` subclasses.

Each carries a canonical `diagnostic_key` and the exit code from
[haex-install.cli.md](../../../specs/008-install-transaction/contracts/haex-install.cli.md).
The base `HaexError` type and the shared exit-code enum live in
`haex_hive.util.errors` and `haex_hive.util.exit_codes`.
"""

from __future__ import annotations

from dataclasses import dataclass

from haex_hive.util import exit_codes
from haex_hive.util.errors import HaexError


@dataclass
class HaexInstallError(HaexError):
    """Base class for every diagnostic emitted by `haex install` itself.

    Subclasses set `diagnostic_key` and `exit_code` per the CLI contract.
    """


@dataclass
class InstallLockBusy(HaexInstallError):
    diagnostic_key: str = "install-lock-busy"
    exit_code: int = exit_codes.INSTALL_LOCK_BUSY
    hint: str = "Wait for the current owner to release or re-run once it has exited."


@dataclass
class IncompleteTransaction(HaexInstallError):
    diagnostic_key: str = "install-transaction-incomplete"
    exit_code: int = exit_codes.INCOMPLETE_TRANSACTION
    hint: str = "Retry `haex install` to clean up and rebuild the interrupted install."


@dataclass
class CommitSnapshotMismatch(HaexInstallError):
    diagnostic_key: str = "install-commit-snapshot-mismatch"
    exit_code: int = exit_codes.VALIDATION_REFUSE
    hint: str = "An input file mutated during the install. Re-run once the writer is done."


@dataclass
class OverlayUnsupported(HaexInstallError):
    diagnostic_key: str = "install-overlay-unsupported"
    exit_code: int = exit_codes.SYSTEM_REFUSE
    hint: str = "The current platform lacks the required overlay primitive for this path."


@dataclass
class SealMismatch(HaexInstallError):
    diagnostic_key: str = "install-seal-mismatch"
    exit_code: int = exit_codes.POST_WRITE_VALIDATION
    hint: str = "A sealed output does not match its recorded digest; re-run the install."
