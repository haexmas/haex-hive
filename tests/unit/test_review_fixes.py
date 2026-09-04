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
from haex_hive.io import json_deterministic
from haex_hive.migrate import detect
from haex_hive.migrate.transform import (
    _glob_matches,
    _select_atom_for_path,
    migrate_v1_to_v2,
)
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.model.install_lock import InstallLock
from haex_hive.model.molecule_manifest import MoleculeManifest
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
    # _select_atom_for_path reads the raw v2-era publisher shape directly
    # (research.md D6): the migrate-only v1->v2 path never goes through the
    # (now v3-only) PublisherManifest runtime model.
    publisher = json.loads(
        '{"haex_hive_version":"2","publisher":"com.example", "atoms": {'
        '"com.example.atom":{"path":"atom","version":"1.0.0"}}}'
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
    # `additionalProperties: false` at install-lock.v3's root (T023) means no
    # unknown top-level key can reach `from_json` anymore; construct the
    # dataclass directly to exercise `unknown_top_level`'s freeze invariant.
    lock = InstallLock(
        haex_hive_version="3",
        generated_by="haex 3.0.0",
        unknown_top_level={"future": {"nested": [1]}},
    )
    with pytest.raises(TypeError):
        lock.unknown_top_level["future"]["nested"][0] = 2


def test_install_lock_migrates_pre_amendment_shape() -> None:
    """Read a stale lock so interrupted installs can resume after the amendment."""
    data = {
        "haex_hive_version": "3",
        "generated_by": "haex 3.0.0",
        "constitution": {
            "sources": [
                {
                    "id": "com.example.constitution",
                    "revision": "0" * 40,
                    "source": "https://example.com/publisher",
                }
            ],
            "assembled_by": {"tool": "haex", "version": "3.0.0"},
            "content_integrity": "sha256-" + "A" * 43,
        },
        "molecules": [
            {
                "id": "com.example.constitution",
                "source": "https://example.com/publisher",
                "revision": "0" * 40,
                "content_integrity": "sha256-" + "B" * 43,
                "contributed_paths": [".haex-hive/constitution.md"],
            }
        ],
        "participating_roots": [
            {"root": ".haex-hive/", "content_integrity": "sha256-" + "C" * 43}
        ],
        "visibility_marker": {
            "generation_id": "g_20260901T120000Z_abcd",
            "content_integrity": "sha256-" + "D" * 43,
        },
        "ownership": {"version": 1, "paths": []},
    }

    lock = InstallLock.from_json(json.dumps(data).encode())
    migrated = json.loads(lock.to_json_bytes())

    assert lock.participating_roots == (".haex-hive/",)
    assert "ownership" not in migrated
    assert "content_integrity" not in migrated["constitution"]
    assert "content_integrity" not in migrated["molecules"][0]
    assert "content_integrity" not in migrated["visibility_marker"]


def test_install_lock_parse_failures_are_typed() -> None:
    with pytest.raises(InstallLockSchemaInvalidError) as exc_info:
        InstallLock.from_json(b"{")
    assert exc_info.value.__cause__ is not None


def test_models_freeze_nested_json_values() -> None:
    molecule = MoleculeManifest.from_json(
        b'{"haex_hive_version":"3","id":"com.example.atom","version":"1.0.0",'
        b'"priority":100,"atoms":{"constitution":["constitution.md"]},'
        b'"defaults":{"nested":{"x":1}}}'
    )
    with pytest.raises(TypeError):
        molecule.defaults["nested"]["x"] = 2

    consumer = ConsumerManifest.from_json(
        b'{"haex_hive_version":"3","identity":"com.example.project","compounds":['
        b'{"source":"https://example.com/publisher","revision":"' + b"0" * 40
        + b'","molecules":["com.example.atom"],"config":{"com.example.atom":'
        b'{"values":{"nested":{"x":1}}}}}]}'
    )
    with pytest.raises(TypeError):
        consumer.compounds[0].config["com.example.atom"].values["nested"]["x"] = 2
    before = consumer.to_json_bytes()
    assert consumer.to_json_bytes() == before

    publisher = PublisherManifest.from_json(
        b'{"haex_hive_version":"3","publisher":"com.example","molecules":{'
        b'"com.example.atom":{"path":"atom","version":"1.0.0"}}}'
    )
    with pytest.raises(TypeError):
        publisher.molecules["com.example.other"] = publisher.molecules["com.example.atom"]


def test_json_pointer_escapes_tokens() -> None:
    assert _json_pointer(["bad/key~name"]) == "/bad~1key~0name"


# NOTE: The two `test_recovery_*` tests were retired by the R1/R7 amendment
# (2026-09-01). They exercised the bespoke JSON transaction journal's path
# validation and completeness checks; both have no counterpart under the
# rename-swap contract, which encodes state entirely in directory names.
# See tests/unit/test_transaction.py for the replacement in-flight coverage.
