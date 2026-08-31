"""Unit tests for the post-commit refresh logic (T011, FR-006).

Uses ``pytest-subprocess`` (already a ``dev`` extra of this repo) to simulate
graphify's behavior without invoking the real binary.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import _refresh  # noqa: E402
import pytest


@pytest.fixture
def graphify_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Place a dummy ``graphify`` executable on PATH so ``shutil.which`` finds it.

    Body of the stub is irrelevant — the real invocation is intercepted by
    ``pytest-subprocess`` in each test.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if os.name == "nt":
        stub = bin_dir / "graphify.cmd"
        stub.write_text("@echo off\r\nexit /b 0\r\n")
    else:
        stub = bin_dir / "graphify"
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return stub


def test_successful_refresh_returns_true(
    tmp_path: Path,
    fp,
    capsys: pytest.CaptureFixture[str],
    graphify_on_path: Path,
) -> None:
    resolved = _refresh.shutil.which("graphify")
    assert resolved is not None
    fp.register(
        [resolved, "update", str(tmp_path)],
        returncode=0,
        stdout="ok\n",
        callback=lambda _process: (
            (tmp_path / "graphify-out").mkdir(),
            (tmp_path / "graphify-out" / ".meta.json").write_text(
                '{"indexed_at_sha": "test-head"}\n'
            ),
        ),
    )
    assert _refresh.refresh(tmp_path) is True
    assert (tmp_path / "graphify-out" / ".meta.json").read_text() == (
        '{"indexed_at_sha": "test-head"}\n'
    )
    captured = capsys.readouterr()
    assert captured.err == ""


def test_nonzero_exit_warns_and_returns_false(
    tmp_path: Path,
    fp,
    capsys: pytest.CaptureFixture[str],
    graphify_on_path: Path,
) -> None:
    resolved = _refresh.shutil.which("graphify")
    assert resolved is not None
    fp.register(
        [resolved, "update", str(tmp_path)],
        returncode=2,
        stderr="graphify: corrupt graph\n",
    )
    assert _refresh.refresh(tmp_path) is False
    captured = capsys.readouterr()
    assert "exited 2" in captured.err
    assert "leaving graph stale" in captured.err


def test_missing_binary_warns_and_returns_false(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert _refresh.refresh(tmp_path) is False
    captured = capsys.readouterr()
    assert "'graphify' not on PATH" in captured.err


def test_timeout_warns_and_returns_false(
    tmp_path: Path,
    fp,
    capsys: pytest.CaptureFixture[str],
    graphify_on_path: Path,
) -> None:
    resolved = _refresh.shutil.which("graphify")
    assert resolved is not None
    fp.register(
        [resolved, "update", str(tmp_path)],
        callback=_raise_timeout,
    )
    assert _refresh.refresh(tmp_path) is False
    captured = capsys.readouterr()
    assert "timed out" in captured.err


def _raise_timeout(process):  # pragma: no cover - simple stub
    import subprocess as _sp

    raise _sp.TimeoutExpired(cmd=process.args, timeout=1)


def test_refresh_never_raises(
    tmp_path: Path,
    fp,
    graphify_on_path: Path,
) -> None:
    resolved = _refresh.shutil.which("graphify")
    assert resolved is not None
    fp.register(
        [resolved, "update", str(tmp_path)],
        returncode=99,
        stderr="boom",
    )
    _refresh.refresh(tmp_path)
