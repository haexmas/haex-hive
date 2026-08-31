# CLI Contract: `haex install`

**Spec**: [Spec 008 — Install Transaction Contract](../spec.md)
**Referenced by**: FR-001–FR-022

## Usage

```console
$ haex install [--repo-root PATH] [--verify-only] [--recover]
```

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--repo-root PATH` | current working directory | Path to the project checkout. Inherited from the top-level `haex --repo-root` per Spec 007. |
| `--verify-only` | off | Acquire the SHARED read lock, verify `install.lock` + `visibility.json` consistency, exit. Never mutates. Same shape as `haex verify` today. |
| `--recover` | off | Acquire the EXCLUSIVE lock, replay or roll back an incomplete journal, exit. No new install is built. Same shape as `haex verify --recover` today. |

## Behaviour matrix

| Invocation | Lock class | On success | On failure |
|---|---|---|---|
| `haex install` | Exclusive | Prints "installed generation `<gen>`", exit 0 | Prints refusal reason + exit code per matrix below |
| `haex install --verify-only` | Shared | Prints "generation `<gen>` verified", exit 0 | Prints mismatch detail, exit per matrix |
| `haex install --recover` | Exclusive | Prints "recovered generation `<gen>`" (either completed or rolled back), exit 0 | Prints diagnostic |

## Exit codes

Uses the canonical set defined in [src/haex_hive/util/exit_codes.py](../../../src/haex_hive/util/exit_codes.py).

| Code | Trigger | Example diagnostic |
|---|---|---|
| 0 | Success | `installed generation g_20260831T142011Z_a4c2 (2 atoms, 12 files)` |
| 2 | Input refuse | `.haex-hive.json not found` / `.haex-hive.json.atoms is empty (Principle V opt-in required)` |
| 3 | I/O refuse | `publisher clone for <source> not found under $HAEX_HIVE_STATE/repos/` |
| 4 | Validation refuse | `plan snapshot digest does not match commit snapshot; source mutated during install` |
| 5 | System refuse | `platform does not support required overlay primitive for <path> (Windows requires Developer Mode for file-scoped symlinks)` |
| 6 | Post-write validation | `sealed .haex-hive/constitution.md digest does not match install.lock` |
| 7 | Incomplete transaction | `install.journal contains uncommitted entries; run with --recover` |
| 8 | Constitution concealment | (from Spec 007's guard; unchanged) |
| 9 | Writer busy | `lock held by <pid>@<hostname> since <acquired_at> (heartbeat <n>s ago, ttl <t>s)` |
| 10 | Plaintext secret | (from Spec 007's guard; unchanged) |

## Refusal semantics

Every refusal MUST cite the specific requirement (FR-###) or Principle it enforces, and identify the offending file/entry, so the operator can locate and fix it without guesswork (FR-019).

Examples:

```text
$ haex install
error: exit=9 key=install-lock-busy
  lock held by 31245@laptop-hex.local since 2026-08-31T14:20:11Z
  (heartbeat 3s ago, ttl 60s)
  hint: wait or investigate PID 31245; if the process is dead, run `haex install --recover`

$ haex install
error: exit=4 key=commit-snapshot-mismatch
  .haex-hive.json digest changed during install
  plan snapshot: sha256-QK+AUjCuNhHjAJap8cbgk6VkyZipJm3f1ZIH4oOqigg
  commit snapshot: sha256-abc123...
  hint: another editor rewrote .haex-hive.json during the install; retry
```

## Reader consistency (informational)

Third-party readers (agent CLIs, editors) do not invoke this CLI — they read the participating output roots directly. Per FR-005, correct readers:

1. Load `.haex-hive/visibility.json` first.
2. Verify each participating root's on-disk digest matches `visibility.json.participating_roots[].content_integrity`.
3. Treat a missing marker or mismatched digest as an unavailable installation, never as a partially-valid one.

The Spec 008 landing includes a reference reader-guide in [quickstart.md](../quickstart.md) for adapter authors.

## Deferred to later specs

- **Publisher-hook invocations** (Spec 009 territory) — will surface as a new `entry_type` in the journal and matching CLI diagnostic; no change to this contract.
- **Adapter-emitted outputs** (Spec 010 territory) — will surface as additional participating roots and per-atom `contributed_paths`; the CLI schema of THIS spec already accommodates them without change.

## Backward compatibility

The current `haex constitution assemble` and `haex constitution show` commands continue to work unchanged as narrow-scope shortcuts. Internally they invoke the install-transaction machinery scoped to constitution steps only.
