"""LLM invocation abstraction for multi-source constitution assembly (R7).

Three adapters, selected by `--llm` > `HAEX_LLM` > TTY auto-detect:
`stdio` (framed candidate/confirmation over stdin/stdout), `file` (writes
pending merge state and signals `PendingMergeWritten`), `none` (always
refuses).
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol, TextIO

from haex_hive.constitution.pending import pending_path, serialize_pending
from haex_hive.constitution.resolve import ResolvedConstitutionContribution
from haex_hive.constitution.safety import (
    validate_no_plaintext_secrets,
    validate_terminal_safe_display,
)
from haex_hive.io import atomic, json_deterministic
from haex_hive.model.install_lock import GenerationInputIdentity
from haex_hive.util.errors import LlmRequiredForMultiSourceError

_CONFIRM_RECORD = b"--haex-confirm: yes\n"


@dataclass(frozen=True)
class MergeResult:
    candidate: bytes
    confirmed: bool
    generation_inputs: tuple[GenerationInputIdentity, ...] = ()


class PendingMergeWritten(Exception):
    """Normal control-flow signal: `FileMergeLLM` wrote pending state; no candidate yet."""


class MergeLLM(Protocol):
    def merge(
        self, contributions: Sequence[ResolvedConstitutionContribution], task_prompt: str
    ) -> MergeResult: ...


_TEXT_SERIALIZATION_PROFILE = {
    "format": "text",
    "encoding": "UTF-8",
    "newline": "LF",
    "key_order": "not-applicable",
    "indent": None,
    "ensure_ascii": False,
}

_JSON_SERIALIZATION_PROFILE = {
    "format": "json",
    "encoding": "UTF-8",
    "newline": "LF",
    "key_order": "lexicographic-utf8",
    "indent": None,
    "ensure_ascii": False,
}


def generation_input_identities(
    adapter_name: str, task_prompt: str
) -> tuple[GenerationInputIdentity, ...]:
    """Return the pinned adapter and task-configuration identities."""
    module_bytes = Path(__file__).read_bytes()
    git_blob = b"blob " + str(len(module_bytes)).encode("ascii") + b"\0" + module_bytes
    adapter_revision = "git:" + hashlib.sha1(git_blob).hexdigest()
    config_bytes = json_deterministic.compact_json(
        {"adapter": adapter_name, "task_prompt": task_prompt}
    )
    tool_config_revision = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    return (
        GenerationInputIdentity(
            kind="adapter",
            id=f"com.haex.hive.adapter.{adapter_name}",
            revision=adapter_revision,
            serialization=dict(_TEXT_SERIALIZATION_PROFILE),
        ),
        GenerationInputIdentity(
            kind="tool-config",
            id=f"com.haex.hive.tool-config.{adapter_name}",
            revision=tool_config_revision,
            serialization=dict(_JSON_SERIALIZATION_PROFILE),
        ),
    )


def _read_exact(stream: BinaryIO, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_candidate_record(stream: BinaryIO) -> bytes | None:
    """Read `Content-Length: <N>\\n` + exactly N bytes. `None` on EOF/malformed."""
    line = stream.readline()
    if not line or not line.endswith(b"\n"):
        return None
    prefix = b"Content-Length: "
    if not line.startswith(prefix):
        return None
    length_bytes = line[len(prefix) : -1]
    if not length_bytes.isdigit():
        return None
    return _read_exact(stream, int(length_bytes))


def read_confirmation_record(stream: BinaryIO) -> bool:
    """Return True only if the stream yields exactly `--haex-confirm: yes\\n`."""
    return stream.readline() == _CONFIRM_RECORD


class StdioMergeLLM:
    def __init__(self, in_stream: BinaryIO | None = None, out_stream: TextIO | None = None) -> None:
        self._in = in_stream if in_stream is not None else sys.stdin.buffer
        self._out = out_stream if out_stream is not None else sys.stdout

    def merge(
        self, contributions: Sequence[ResolvedConstitutionContribution], task_prompt: str
    ) -> MergeResult:
        for c in contributions:
            validate_no_plaintext_secrets(c.body, location=f"constitution source {c.source.id}")
            validate_terminal_safe_display(c.body)

        for c in contributions:
            self._out.write(
                f"--- {c.source.id} @ {c.source.revision[:7]} ({c.source.source}) ---\n"
            )
            self._out.write(c.body.decode("utf-8"))
            self._out.write("\n")
        self._out.write(task_prompt + "\n")
        self._out.flush()

        candidate = read_candidate_record(self._in)
        if candidate is None:
            return MergeResult(candidate=b"", confirmed=False)

        validate_no_plaintext_secrets(candidate, location="stdio merge candidate")
        validate_terminal_safe_display(candidate)

        self._out.write(candidate.decode("utf-8"))
        self._out.write("\nConfirm merge? Send `--haex-confirm: yes` to accept.\n")
        self._out.flush()

        confirmed = read_confirmation_record(self._in)
        return MergeResult(
            candidate=candidate,
            confirmed=confirmed,
            generation_inputs=generation_input_identities("stdio", task_prompt),
        )


class FileMergeLLM:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def merge(
        self, contributions: Sequence[ResolvedConstitutionContribution], task_prompt: str
    ) -> MergeResult:
        for c in contributions:
            validate_no_plaintext_secrets(c.body, location=f"constitution source {c.source.id}")
        pending_bytes = serialize_pending(list(contributions), task_prompt)
        validate_no_plaintext_secrets(pending_bytes, location="pending merge payload")
        atomic.write_replace(pending_path(self._repo_root), pending_bytes)
        raise PendingMergeWritten()


class NoneMergeLLM:
    def merge(
        self, contributions: Sequence[ResolvedConstitutionContribution], task_prompt: str
    ) -> MergeResult:
        raise LlmRequiredForMultiSourceError(
            message="--llm=none always refuses for multi-source install"
        )
