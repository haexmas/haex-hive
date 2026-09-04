"""T066 — end-to-end quickstart.md Path 1-4 walkthrough (SC-001..SC-003)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _run_haex(
    repo_root: Path,
    *args: str,
    state_root: Path,
    stdin_bytes: bytes | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HAEX_HIVE_STATE"] = str(state_root)
    return subprocess.run(
        [sys.executable, "-m", "haex_hive", "--repo-root", str(repo_root), *args],
        input=stdin_bytes if stdin_bytes is not None else b"",
        capture_output=True,
        env=env,
    )


def test_path1_migrate_produces_schema_valid_v2(
    self_migration_fixture: dict, tmp_path: Path
) -> None:
    """quickstart.md Path 1 — SC-001."""
    consumer = tmp_path / "consumer"
    shutil.copytree(self_migration_fixture["publisher"], consumer)
    (consumer / ".haex-hive.json").write_text(
        json.dumps(
            {
                "haex_hive_version": "1",
                "identity": "github.com/haexmas/haex-hive",
                "harness_sources": [
                    {
                        "role": "constitution",
                        "repository": "self",
                        "revision": self_migration_fixture["commit_a"],
                        "path": ".specify/memory/constitution.md",
                    }
                ],
            },
            indent=2,
        )
    )

    dry_run = _run_haex(
        consumer, "migrate", "--dry-run", state_root=self_migration_fixture["state_root"]
    )
    assert dry_run.returncode == 0, dry_run.stderr.decode()
    assert b"@@" in dry_run.stdout

    write = _run_haex(consumer, "migrate", state_root=self_migration_fixture["state_root"])
    assert write.returncode == 0, write.stderr.decode()
    sidecar = consumer / ".haex-hive.json.migrated"
    assert sidecar.exists()

    data = json.loads(sidecar.read_text())
    # The v2 schema payload was retired by Spec 013 (v3-only tool); the
    # migrate_v1_to_v2 transform itself is unchanged and still targets v2.
    assert data["haex_hive_version"] == "2"

    sidecar.replace(consumer / ".haex-hive.json")
    rerun = _run_haex(consumer, "migrate", state_root=self_migration_fixture["state_root"])
    assert rerun.returncode == 0
    assert b"already migrated to v2" in rerun.stderr
    assert not sidecar.exists()


def test_path2_single_source_assemble_and_show(
    single_source_constitution_fixture: dict,
) -> None:
    """quickstart.md Path 2 + Path 4 — SC-002."""
    consumer = single_source_constitution_fixture["consumer"]
    state_root = single_source_constitution_fixture["state_root"]

    first = _run_haex(consumer, "install", state_root=state_root)
    assert first.returncode == 0, first.stderr.decode()

    source_body = (
        single_source_constitution_fixture["publisher"] / "constitution" / "constitution.md"
    ).read_bytes()
    constitution = (consumer / ".haex-hive" / "constitution.md").read_bytes()
    assert constitution == source_body
    lock_data_1 = json.loads((consumer / ".haex-hive" / "install.lock").read_bytes())

    second = _run_haex(consumer, "install", state_root=state_root)
    assert second.returncode == 0
    assert second.stdout.decode().strip() == "no changes"
    assert (consumer / ".haex-hive" / "constitution.md").read_bytes() == constitution
    lock_data_2 = json.loads((consumer / ".haex-hive" / "install.lock").read_bytes())
    assert lock_data_1 == lock_data_2, "no-op re-install must leave install.lock untouched"

    show = _run_haex(consumer, "constitution", "show", state_root=state_root)
    assert show.returncode == 0, show.stderr.decode()
    assert show.stdout.endswith(constitution)
    assert b"# Assembled from" in show.stdout

    no_preface = _run_haex(consumer, "constitution", "show", "--no-preface", state_root=state_root)
    assert no_preface.returncode == 0
    assert no_preface.stdout == constitution


def test_path3_multi_source_assemble_second_device_show(
    multi_source_constitution_fixture: dict, tmp_path: Path
) -> None:
    """quickstart.md Path 3 — SC-003: a second device verifies via `show` without re-assembling."""
    consumer = multi_source_constitution_fixture["consumer"]
    state_root = multi_source_constitution_fixture["state_root"]
    merged = b"# Merged Constitution\n\nBe kind.\nBe bold.\n"

    candidate = f"Content-Length: {len(merged)}\n".encode("ascii") + merged
    confirm = b"--haex-confirm: yes\n"
    proc = _run_haex(
        consumer,
        "install",
        "--llm=stdio",
        state_root=state_root,
        stdin_bytes=candidate + confirm,
    )
    assert proc.returncode == 0, proc.stderr.decode()

    # Simulate "git pull" on a second device: only the two output files travel.
    second_device = tmp_path / "second-device"
    (second_device / ".haex-hive").mkdir(parents=True)
    for name in ("constitution.md", "install.lock"):
        shutil.copy2(consumer / ".haex-hive" / name, second_device / ".haex-hive" / name)

    show = _run_haex(second_device, "constitution", "show", state_root=state_root)
    assert show.returncode == 0, show.stderr.decode()
    assert show.stdout.endswith(merged)


def test_path3_refuses_missing_llm(multi_source_constitution_fixture: dict) -> None:
    """quickstart.md Path 3 — SC-007 companion: no-LLM refuses cleanly, no files written."""
    consumer = multi_source_constitution_fixture["consumer"]
    state_root = multi_source_constitution_fixture["state_root"]

    proc = _run_haex(consumer, "install", "--llm=none", state_root=state_root)
    assert proc.returncode == 4
    assert b"key=llm-required-for-multi-source" in proc.stderr
    assert not (consumer / ".haex-hive" / "constitution.md").exists()
