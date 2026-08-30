"""T057 — ASCII framing for the `stdio` merge-LLM adapter."""

from __future__ import annotations

import io

from haex_hive.constitution.llm import read_candidate_record, read_confirmation_record


def _stream(*chunks: bytes) -> io.BytesIO:
    return io.BytesIO(b"".join(chunks))


def test_reads_exact_candidate_record() -> None:
    body = "hello — café".encode()
    stream = _stream(f"Content-Length: {len(body)}\n".encode("ascii"), body)
    assert read_candidate_record(stream) == body


def test_candidate_boundary_unambiguous_when_body_ends_in_newline() -> None:
    body = b"line one\nline two\n"
    stream = _stream(f"Content-Length: {len(body)}\n".encode("ascii"), body, b"TRAILING")
    result = read_candidate_record(stream)
    assert result == body
    assert stream.read() == b"TRAILING"


def test_malformed_length_prefix_returns_none() -> None:
    stream = _stream(b"Content-Length: not-a-number\n", b"whatever")
    assert read_candidate_record(stream) is None


def test_missing_prefix_returns_none() -> None:
    stream = _stream(b"garbage header\n", b"whatever")
    assert read_candidate_record(stream) is None


def test_eof_before_header_returns_none() -> None:
    stream = _stream(b"")
    assert read_candidate_record(stream) is None


def test_eof_mid_body_returns_none() -> None:
    stream = _stream(b"Content-Length: 100\n", b"too short")
    assert read_candidate_record(stream) is None


def test_header_missing_trailing_newline_returns_none() -> None:
    stream = _stream(b"Content-Length: 5")  # no trailing \n, and no body follows
    assert read_candidate_record(stream) is None


def test_confirmation_exact_literal_accepted() -> None:
    stream = _stream(b"--haex-confirm: yes\n")
    assert read_confirmation_record(stream) is True


def test_confirmation_any_other_text_rejected() -> None:
    for payload in (b"--haex-confirm: no\n", b"yes\n", b"--haex-confirm: yes", b""):
        assert read_confirmation_record(_stream(payload)) is False


def test_confirmation_eof_rejected() -> None:
    assert read_confirmation_record(_stream(b"")) is False
