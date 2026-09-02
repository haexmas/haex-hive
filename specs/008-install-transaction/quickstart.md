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
- `.haex-hive/install.lock` — install manifest with resolved atom identities and generation metadata.
- `.haex-hive/visibility.json` — the publication marker.
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

*Not yet available.* `--verify-only` and the shared-read lock land in the US2 fenced-lease block (task T037). Until then, verification against a running install is done by reading `.haex-hive/visibility.json` and `.haex-hive/install.lock` directly and comparing their `generation_id` fields (see step 7).

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

Any tool reading the participating output roots should follow this pattern to avoid observing a mid-install state:

```python
import json
from pathlib import Path

def load_consistent_metadata(repo_root: Path, attempts: int = 3) -> tuple[dict, dict]:
    marker_path = repo_root / ".haex-hive" / "visibility.json"
    install_lock_path = repo_root / ".haex-hive" / "install.lock"
    for _ in range(attempts):
        try:
            marker_before = json.loads(marker_path.read_bytes())
            install_lock = json.loads(install_lock_path.read_bytes())
            marker_after = json.loads(marker_path.read_bytes())
        except (FileNotFoundError, json.JSONDecodeError):
            # The live tree can be absent briefly during the rename swap.
            continue
        if marker_before["generation_id"] != marker_after["generation_id"]:
            # A publication happened while the metadata was being read.
            continue
        if (
            marker_before["generation_id"]
            != install_lock["visibility_marker"]["generation_id"]
        ):
            raise RuntimeError("install.lock does not match visibility marker")
        return marker_after, install_lock
    raise RuntimeError("could not read a stable installation generation")

def verify_root(repo_root: Path, root_name: str, managed_paths: set[str]) -> None:
    # Enumerate paths per FR-005: for haex-owned roots, all files under root
    # except visibility.json; for mixed-ownership roots, only overlay_paths.
    # See research §R5 for exact normalisation.
    # For a mixed-ownership root, enumerate only managed_paths below root;
    # never include unowned siblings. For .haex-hive/, enumerate every file
    # except visibility.json and install.lock, per FR-005.
    # ...
    pass

project_checkout = Path.cwd()
marker, install_lock = load_consistent_metadata(project_checkout)
managed_paths = {
    path
    for atom in install_lock.get("atoms", [])
    for path in atom["contributed_paths"]
}
for root_name in marker["participating_roots"]:
    verify_root(project_checkout, root_name, managed_paths)
# All roots match: safe to proceed.
```

**Never** read `.haex-hive/constitution.md` (or any other participating-root file) without first loading and verifying the marker. A read without verification can observe a mid-transaction state during a concurrent install.

## 8. Where things live (recap)

- **In the repo checkout** (committed):
  - `.haex-hive.json` — adoption declarations (Spec 007).
  - `.haex-hive/constitution.md`, `install.lock`, `visibility.json` — install outputs.
  - `.claude/`, `.codex/`, other adapter roots — mixed-ownership; only overlay-owned paths are managed by `haex install`.
- **Under `$HAEX_HIVE_STATE`** (device-local, NEVER shared across satellites, MUST NOT contain secrets per FR-022):
  - `~/.local/share/haex-hive/repos/<clone-hash>/` — publisher bare clones (Spec 007).
  - `$HAEX_HIVE_STATE/locks/<repo-key>/install.mutex` — install lock (new in Spec 008).
  - No durable install journal — interrupted installs are detected from stale
    `.next`/`.prev` siblings beside the published root.
  - Override with `$HAEX_HIVE_STATE` env var.

## 9. Suspending automation for a session

`haex install` is deliberately not silent; it's meant to be invoked when the operator wants a change. If a session's tooling would normally invoke it automatically (e.g. a shell prompt hook, a wrapper script), the operator can defer it by declining the tooling's prompt — this spec adds no per-session opt-out flag because the CLI itself is already opt-in.
