# Quickstart: `haex install`

**Feature**: Spec 008 — Install Transaction Contract
**Audience**: satellite operators running `haex install` for the first time, and adapter authors verifying reader consistency.

## Prerequisites

- `haex` CLI installed (from Spec 007). `haex --help` should list the `install` subcommand once Spec 008 lands.
- A project checkout with a valid `.haex-hive.json` (Spec 007 v2 shape) declaring at least one adopted atom.
- On Windows: Developer Mode enabled if any adopted atom's Spec 010 adapter emits **file-scoped** overlays into `.claude/` or `.codex/`. Directory-scoped overlays work without elevation via junctions.

## 1. First install

From the project checkout root:

```console
haex install
installed generation g_20260831T142011Z_a4c2
```

On success, the following files exist:

- `.haex-hive/constitution.md` — assembled constitution (from Spec 007's flow, now under the install transaction).
- `.haex-hive/install.lock` — the sole publication record, with the generation ID and resolved molecule paths.
- Additional per-adapter outputs under `.claude/`, `.codex/`, etc. as Spec 010 adapters land.

`$HAEX_HIVE_STATE/locks/<repo-key>/` on the same satellite now contains. The
`repo-key` is the lowercase hexadecimal SHA-256 of the canonical project
identity; the full identity is kept separately in `repo-identity.v1.json` and
never appears in the directory name:

- `install.mutex` (device-local, not shared across satellites) — was held during the install and released on exit. The heartbeat thread + stale-lease reclaim protocol are deferred to T034.
- `repos/<clone-hash>/` — device-local pinned publisher clones used during
  source resolution.

## 2. Idempotent re-install

Running `haex install` again with no changes to `.haex-hive.json`:

```console
haex install
no changes
```

No files in `.haex-hive/` are rewritten and their timestamps remain unchanged.
The device-local `$HAEX_HIVE_STATE/locks/<repo-key>/install.mutex` may still be
rewritten or fsynced. This is the SC-003 idempotence guarantee.

## 3. Verify without installing

*Not yet available.* `--verify-only` and the shared-read lock land in the US2 fenced-lease block (task T037). Until then, verification against a running install is done by reading `.haex-hive/install.lock`, passing its schema/migration gate, and checking its recorded paths (see step 7).

## 4. Concurrent install attempt

If a second `haex install` runs while the first is in flight:

```console
haex install
error: exit=9 key=constitution-writer-busy
  another `haex install` is running
  hint: another `haex install` is running; retry after it releases the lock.
```

Non-blocking by design (per FR-001) — the operator gets a busy diagnostic and
a retry hint immediately.

## 5. Recovering from an interrupted install

If a previous `haex install` was killed (SIGKILL, power loss, host reboot),
retry the same command. It removes stale `.haex-hive.next/`, retains a
`.haex-hive.prev/` pre-image until the replacement is successfully published,
and regenerates the deterministic generation from the pinned inputs:

```console
haex install
installed generation g_20260831T142011Z_a4c2
```

If manifest or source resolution fails during the retry, the command refuses
without claiming a new generation and retains `.prev/` when it is the only
published generation. Fix the input and retry `haex install` again.

## 6. Removing an atom

Edit `.haex-hive.json` to drop an atom, then reinstall:

```console
$ haex install
installed generation g_20260831T160532Z_bb18
```

The transaction stages the reduced generation into `.haex-hive.next/` and swaps it in atomically. Under the R1 rename-swap the whole `.haex-hive/` is replaced in one step, so any file only the removed atom would have contributed is absent from the new generation by construction. If interrupted mid-way, recovery leaves the tree either fully at the old state or fully at the new state; a subsequent `haex install` converges deterministically.

## 7. Reader consistency (for adapter authors)

Any tool reading the participating output roots should follow this pattern to avoid observing a mid-install state. The real reader MUST use the current install-lock schema/migration gate before treating the lock as authoritative:

```python
import json
from pathlib import Path

def load_consistent_metadata(repo_root: Path, consume, attempts: int = 3):
    install_lock_path = repo_root / ".haex-hive" / "install.lock"
    for _ in range(attempts):
        with acquire_shared_read_lock(repo_root):
            try:
                install_lock = json.loads(install_lock_path.read_bytes())
                validate_against_current_schema(install_lock)
                for molecule in install_lock["molecules"]:
                    for recorded_path in molecule["paths"]:
                        if not (repo_root / recorded_path).exists():
                            raise RuntimeError("install.lock records a missing path")
                generation_id = install_lock["generation_id"]
                generation_record = json.loads(
                    (repo_root / ".specify" / ".haex-hive-generation.json").read_bytes()
                )
                if generation_record["generation_id"] != generation_id:
                    raise RuntimeError(".specify generation does not match install.lock")
                for pointer_path in active_adapter_pointer_paths(repo_root):
                    pointer_record = json.loads(pointer_path.read_bytes())
                    if pointer_record["generation_id"] != generation_id:
                        raise RuntimeError("adapter pointer does not match install.lock")
                # The callback consumes constitution, generated files, and adapter
                # overlays before this block releases the shared lock.
                return consume(install_lock, generation_record)
            except (FileNotFoundError, ValueError, RuntimeError):
                # Missing, malformed, or mixed-generation metadata is unavailable;
                # retry while retaining the shared-lock boundary for each attempt.
                continue
    raise RuntimeError("could not read a stable installation generation")

def validate_against_current_schema(install_lock: dict) -> None:
    # Call the implementation's FR-005 schema/migration gate here.
    # Unsupported versions, retired fields, and required migrations are
    # unavailable and must not be silently rewritten.
    pass

def acquire_shared_read_lock(repo_root: Path):
    # Use the implementation's shared/read lock for the whole reader operation.
    # It must cover the initial lock read, validation, and file consumption.
    pass

project_checkout = Path.cwd()
result = load_consistent_metadata(project_checkout, consume=consume_validated_files)
# `consume_validated_files` reads every validated file and overlay while the
# shared lock is still held; no post-return lock reread is used.
```

**Never** read `.haex-hive/constitution.md` (or any other participating-root file) without first acquiring the shared/read lock, then loading and verifying `install.lock`. Release the lock only after all validated files and overlay pointers have been consumed.

## 8. Where things live (recap)

- **In the repo checkout** (committed):
  - `.haex-hive.json` — adoption declarations (Spec 007).
  - `.haex-hive/constitution.md`, `install.lock` — install outputs; `install.lock` is the publication record.
  - `.claude/`, `.codex/`, other adapter roots — mixed-ownership; only overlay-owned paths are managed by `haex install`.
- **Under `$HAEX_HIVE_STATE`** (device-local, NEVER shared across satellites, MUST NOT contain secrets per FR-022):
  - `~/.local/share/haex-hive/repos/<clone-hash>/` — publisher bare clones (Spec 007).
  - `$HAEX_HIVE_STATE/locks/<repo-key>/install.mutex` — install lock (new in Spec 008).
  - No durable install journal — interrupted installs are detected from stale
    `.next`/`.prev` siblings beside the published root.
  - Override with `$HAEX_HIVE_STATE` env var.

## 9. Suspending automation for a session

`haex install` is deliberately not silent; it's meant to be invoked when the operator wants a change. If a session's tooling would normally invoke it automatically (e.g. a shell prompt hook, a wrapper script), the operator can defer it by declining the tooling's prompt — this spec adds no per-session opt-out flag because the CLI itself is already opt-in.
