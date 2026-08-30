"""Regression coverage for the PR #12 review fixes."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from haex_hive.cli.diagnostics import emit_refuse
from haex_hive.cli.main import main
from haex_hive.constitution.safety import (
    validate_no_plaintext_secrets,
    validate_terminal_safe_display,
)
from haex_hive.io import json_deterministic, transaction
from haex_hive.migrate import detect
from haex_hive.migrate.transform import (
    _glob_matches,
    _select_atom_for_path,
    migrate_v1_to_v2,
)
from haex_hive.model.atom_manifest import AtomManifest
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.model.install_lock import InstallLock
from haex_hive.model.publisher_manifest import PublisherManifest
from haex_hive.schema.validator import _json_pointer
from haex_hive.util.errors import (
    HaexError,
    IdentityMismatchError,
    InstallLockSchemaInvalidError,
    MissingAtomManifestError,
    PlaintextSecretDetectedError,
    TerminalUnsafeContributionError,
)


def test_constitution_commands_refuse_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--repo-root", str(tmp_path), "constitution", "show"]) == 2
    assert "key=constitution-not-assembled" in capsys.readouterr().err


def test_migrate_invalid_manifest_is_typed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".haex-hive.json").write_bytes(b"{")
    assert main(["--repo-root", str(tmp_path), "migrate", "--dry-run"]) == 2
    assert "key=haex-hive-json-invalid" in capsys.readouterr().err


def test_migrate_invalid_manifest_shape_is_typed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".haex-hive.json").write_text(
        '{"haex_hive_version":"1","identity":"com.example.project",'
        '"harness_sources":null}'
    )
    assert main(["--repo-root", str(tmp_path), "migrate", "--dry-run"]) == 2
    assert "key=haex-hive-json-invalid" in capsys.readouterr().err


def test_detect_non_object_manifest_is_shape_error() -> None:
    with pytest.raises(detect.InvalidHaexHiveManifestError):
        detect.detect_version(b"[]")


def test_missing_identity_is_an_identity_refusal() -> None:
    raw = json.dumps({"haex_hive_version": "1", "harness_sources": []}).encode()
    with pytest.raises(IdentityMismatchError):
        migrate_v1_to_v2(raw, Path("."), Path("."))


def test_invalid_atom_manifest_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = PublisherManifest.from_json(
        b'{"haex_hive_version":"2","publisher":"com.example", "atoms": {'
        b'"com.example.atom":{"path":"atom","version":"1.0.0"}}}'
    )
    monkeypatch.setattr(
        "haex_hive.migrate.transform.git_show.show_bytes", lambda *args, **kwargs: b"{"
    )
    with pytest.raises(MissingAtomManifestError):
        _select_atom_for_path(
            publisher, tmp_path, "0" * 40, "constitution", "atom/constitution.md"
        )


def test_glob_contributions_use_segment_aware_matching() -> None:
    assert _glob_matches("rules/*.md", "rules/main.md")
    assert not _glob_matches("rules/*.md", "rules/nested/main.md")
    assert _glob_matches("rules/**/*.md", "rules/nested/main.md")
    assert _glob_matches("rules/**/*.md", "rules/main.md")


@pytest.mark.parametrize("codepoint", [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF])
def test_rejects_invisible_format_controls(codepoint: int) -> None:
    with pytest.raises(TerminalUnsafeContributionError):
        validate_terminal_safe_display(f"safe{chr(codepoint)}text".encode())


def test_rejects_openpgp_private_key() -> None:
    with pytest.raises(PlaintextSecretDetectedError):
        validate_no_plaintext_secrets(
            b"-----BEGIN PGP PRIVATE KEY BLOCK-----\nsecret\n", location="test"
        )


def test_deterministic_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        json_deterministic.dumps({"value": float("nan")})


def test_diagnostics_quote_control_characters() -> None:
    stream = StringIO()
    emit_refuse(HaexError(message="bad", context={"value": "a\x00\x1bb"}), stream=stream)
    assert 'value="a\\u0000\\u001bb"' in stream.getvalue()


def test_install_lock_freezes_unknown_nested_values() -> None:
    lock = InstallLock.from_json(
        json.dumps(
            {
                "haex_hive_version": "2",
                "generated_by": "haex 2.0.0",
                "future": {"nested": [1]},
            }
        ).encode()
    )
    with pytest.raises(TypeError):
        lock.unknown_top_level["future"]["nested"][0] = 2


def test_install_lock_parse_failures_are_typed() -> None:
    with pytest.raises(InstallLockSchemaInvalidError) as exc_info:
        InstallLock.from_json(b"{")
    assert exc_info.value.__cause__ is not None


def test_models_freeze_nested_json_values() -> None:
    atom = AtomManifest.from_json(
        b'{"haex_hive_version":"2","id":"com.example.atom","version":"1.0.0",'
        b'"contributes":{"constitution":"constitution.md"},"defaults":{"nested":{"x":1}}}'
    )
    with pytest.raises(TypeError):
        atom.defaults["nested"]["x"] = 2

    consumer = ConsumerManifest.from_json(
        b'{"haex_hive_version":"2","identity":"com.example.project","atoms":['
        b'{"source":"https://example.com/publisher","revision":"' + b"0" * 40
        + b'","includes":["com.example.atom"],"config":{"com.example.atom":'
        b'{"values":{"nested":{"x":1}}}}}]}'
    )
    with pytest.raises(TypeError):
        consumer.atoms[0].config["com.example.atom"].values["nested"]["x"] = 2
    before = consumer.to_json_bytes()
    assert consumer.to_json_bytes() == before

    publisher = PublisherManifest.from_json(
        b'{"haex_hive_version":"2","publisher":"com.example","atoms":{'
        b'"com.example.atom":{"path":"atom","version":"1.0.0"}}}'
    )
    with pytest.raises(TypeError):
        publisher.atoms["com.example.other"] = publisher.atoms["com.example.atom"]


def test_json_pointer_escapes_tokens() -> None:
    assert _json_pointer(["bad/key~name"]) == "/bad~1key~0name"


def test_recovery_validates_all_paths_before_mutating(tmp_path: Path) -> None:
    hive = tmp_path / transaction.HAEX_HIVE_DIR
    hive.mkdir()
    constitution = hive / transaction.CONSTITUTION_NAME
    outside = tmp_path / "outside.txt"
    constitution.write_bytes(b"keep")
    outside.write_bytes(b"do not touch")
    journal = hive / transaction.JOURNAL_NAME
    journal.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "logical": "constitution",
                        "target": ".haex-hive/constitution.md",
                        "staged": ".haex-hive/constitution.staged.tmp",
                        "prior_state": "absent",
                        "backup": None,
                    },
                    {
                        "logical": "install_lock",
                        "target": "../outside.txt",
                        "staged": ".haex-hive/install_lock.staged.tmp",
                        "prior_state": "absent",
                        "backup": None,
                    },
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        transaction.recover_if_journaled(tmp_path)
    assert constitution.read_bytes() == b"keep"
    assert outside.read_bytes() == b"do not touch"
    assert journal.exists()


def test_recovery_rejects_incomplete_journal_before_mutating(tmp_path: Path) -> None:
    hive = tmp_path / transaction.HAEX_HIVE_DIR
    hive.mkdir()
    constitution = hive / transaction.CONSTITUTION_NAME
    constitution.write_bytes(b"keep")
    journal = hive / transaction.JOURNAL_NAME
    journal.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "logical": "constitution",
                        "target": ".haex-hive/constitution.md",
                        "staged": ".haex-hive/constitution.staged.tmp",
                        "prior_state": "absent",
                        "backup": None,
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        transaction.recover_if_journaled(tmp_path)
    assert constitution.read_bytes() == b"keep"
    assert journal.exists()
