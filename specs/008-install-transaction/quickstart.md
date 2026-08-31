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
installed generation g_20260831T142011Z_a4c2 (2 atoms, 12 files)
```

On success, the following files exist:

- `.haex-hive/constitution.md` — assembled constitution (from Spec 007's flow, now under the install transaction).
- `.haex-hive/install.lock` — install manifest with per-atom `content_integrity` and per-root digests.
- `.haex-hive/visibility.json` — the publication marker.
- Additional per-adapter outputs under `.claude/`, `.codex/`, etc. as Spec 010 adapters land.

`$HAEX_HIVE_STATE/locks/<repo-key>/` on the same satellite now contains. The
`repo-key` is the lowercase hexadecimal SHA-256 of the canonical project
identity; the full identity is kept separately in `repo-identity.v1.json` and
never appears in the directory name:

- `install.mutex` (device-local, not shared across satellites) — was held during the install; heartbeat thread stops on exit.
- `checkouts/<checkout-key>/install.journal` — removed atomically after the
  successful cleanup step; an existing journal always means recovery is
  required (FR-002).

## 2. Idempotent re-install

Running `haex install` again with no changes to `.haex-hive.json`:

```console
haex install
no changes; generation g_20260831T142011Z_a4c2 is up to date
```

Zero files rewritten. Zero timestamps updated. This is the SC-003 idempotence guarantee.

## 3. Verify without installing

For CI or a scripted check:

```console
haex install --verify-only
generation g_20260831T142011Z_a4c2 verified
```

Acquires the shared read lock only. Concurrent `haex install` (exclusive) blocks it until the install completes.

## 4. Concurrent install attempt

If a second `haex install` runs while the first is in flight:

```console
haex install
error: exit=9 key=install-lock-busy
  lock held by 31245@laptop-hex.local since 2026-08-31T14:20:11Z
  (heartbeat 3s ago, ttl 60s)
  hint: wait or investigate PID 31245; if the process is dead, run `haex install --recover`
```

Non-blocking by design (per FR-001) — the operator sees ownership detail immediately.

## 5. Recovering from an interrupted install

If a previous `haex install` was killed (SIGKILL, power loss, host reboot), the next invocation detects it:

```console
haex install
error: exit=7 key=incomplete-transaction (FR-002)
  install.journal contains uncommitted entries from a prior invocation
  hint: run `haex install --recover` to complete or roll back
```

Recover:

```console
haex install --recover
recovered generation g_20260831T142011Z_a4c2 (completed; 12 files sealed)
```

Or if recovery determined the safe path was rollback:

```console
haex install --recover
recovered previous generation g_20260828T093345Z_7f21 (rolled back; 8 files restored)
```

Either outcome is a valid FR-011 result: complete-new OR rollback-to-previous. Never a mixed state. If the marker was already published when the crash occurred, recovery keeps that verified generation and performs cleanup only.

## 6. Removing an atom

Edit `.haex-hive.json` to drop an atom, then reinstall:

```console
$ haex install
installed generation g_20260831T160532Z_bb18 (1 atom, 4 files; removed 8 files owned by com.example.old-atom)
```

The transaction stages new writes AND deletions atomically per FR-008. If interrupted mid-way, recovery leaves the tree either fully at the old state (both atoms, all files) or fully at the new state (one atom, its files only). No partial delete.

## 7. Reader consistency (for adapter authors)

Any tool reading the participating output roots should follow this pattern to avoid observing a mid-install state:

```python
import json, hashlib, base64
from pathlib import Path

def sri(digest_bytes: bytes) -> str:
    return "sha256-" + base64.urlsafe_b64encode(digest_bytes).rstrip(b"=").decode()

def load_visibility_marker(repo_root: Path) -> dict:
    marker = repo_root / ".haex-hive" / "visibility.json"
    if not marker.exists():
        raise RuntimeError("no installation available")
    return json.loads(marker.read_bytes())

def verify_root(repo_root: Path, root_record: dict, managed_paths: set[str]) -> None:
    # Enumerate paths per FR-005: for haex-owned roots, all files under root
    # except visibility.json; for mixed-ownership roots, only overlay_paths.
    # See research §R5 for exact normalisation.
    # For a mixed-ownership root, enumerate only managed_paths below root;
    # never include unowned siblings. For .haex-hive/, enumerate every file
    # except visibility.json and install.lock, per FR-005.
    # ...
    pass

project_checkout = Path.cwd()
marker = load_visibility_marker(project_checkout)
install_lock_path = project_checkout / ".haex-hive" / "install.lock"
install_lock_bytes = install_lock_path.read_bytes()
expected_lock_digest = sri(hashlib.sha256(install_lock_bytes).digest())
if marker["install_lock_content_integrity"] != expected_lock_digest:
    raise RuntimeError("install.lock does not match visibility marker")
install_lock = json.loads(install_lock_bytes)
managed_paths = {
    record["path"]
    for record in install_lock.get("ownership", {}).get("paths", [])
}
for root_record in marker["participating_roots"]:
    verify_root(project_checkout, root_record, managed_paths)
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
  - `$HAEX_HIVE_STATE/locks/<repo-key>/checkouts/<checkout-key>/install.journal` — checkout-scoped durable journal (new in Spec 008).
  - Override with `$HAEX_HIVE_STATE` env var.

## 9. Suspending automation for a session

`haex install` is deliberately not silent; it's meant to be invoked when the operator wants a change. If a session's tooling would normally invoke it automatically (e.g. a shell prompt hook, a wrapper script), the operator can defer it by declining the tooling's prompt — this spec adds no per-session opt-out flag because the CLI itself is already opt-in.
