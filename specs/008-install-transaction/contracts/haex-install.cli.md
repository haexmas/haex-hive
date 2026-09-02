# CLI Contract: `haex install`

**Spec**: [Spec 008 — Install Transaction Contract](../spec.md)
**Referenced by**: FR-001–FR-022

## Usage

```console
haex install [--repo-root PATH] [--verify-only]
            [--llm {stdio,file,none}] [--accept-merged PATH]
```

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--repo-root PATH` | current working directory | Path to the project checkout. Inherited from the top-level `haex --repo-root` per Spec 007. |
| `--verify-only` | off | Acquire the SHARED read lock, verify `install.lock` + `visibility.json` consistency, exit. Never mutates. Same shape as `haex verify` today. |
| `--llm {stdio,file,none}` | default | Select the multi-source constitution merge workflow. `stdio` reads a framed candidate from the attached LLM and requires operator confirmation; `file` writes the pending merge inputs for an external editor/LLM and exits; `none` refuses because a multi-source constitution requires a merge method. |
| `--accept-merged PATH` | unset | Accept a reviewed merged constitution candidate from `PATH` and publish it after validating it against the pending merge inputs. It is mutually exclusive with `--llm`. |

The `--llm` and `--accept-merged` options apply to multi-source constitution
installation. Single-source installations use the deterministic fast path when
neither option is supplied.

Recovery is explicit through `haex verify --recover`, which acquires the EXCLUSIVE lock, replays or rolls back an incomplete journal, and builds no new install.

## Behaviour matrix

| Invocation | Lock class | On success | On failure |
|---|---|---|---|
| `haex install` | Exclusive | Prints "installed generation `<gen>`", exit 0 | Prints refusal reason + exit code per matrix below |
| `haex install --verify-only` | Shared | Prints "generation `<gen>` verified", exit 0 | Prints mismatch detail, exit per matrix |
| `haex verify --recover` | Exclusive | Prints "recovered generation `<gen>`" (either completed or rolled back), exit 0 | Prints diagnostic |

## Exit codes

Uses the canonical set defined in [src/haex_hive/util/exit_codes.py](../../../src/haex_hive/util/exit_codes.py).

| Code | Trigger | Example diagnostic |
|---|---|---|
| 0 | Success | `installed generation g_20260831T142011Z_a4c2 (2 atoms, 12 files)` |
| 2 | Input refuse (FR-006 / Principle V) | `.haex-hive.json not found` / `.haex-hive.json.atoms is empty (Principle V opt-in required)` |
| 3 | I/O refuse (FR-006) | `publisher clone for <source> not found under $HAEX_HIVE_STATE/repos/` |
| 4 | Validation refuse (FR-006) | `plan snapshot digest does not match commit snapshot; source mutated during install` |
| 5 | System refuse (FR-003) | `platform does not support required overlay primitive for <path> (Windows requires Developer Mode for file-scoped symlinks)` |
| 6 | Post-write validation (FR-005 / FR-009) | `sealed .haex-hive/constitution.md digest does not match install.lock` |
| 7 | Incomplete transaction (FR-002) | `install.journal contains uncommitted entries; run with --recover` |
| 8 | Constitution concealment (Principle VIII) | (from Spec 007's guard; unchanged) |
| 9 | Writer busy (FR-001 / FR-010) | `lock held by <pid>@<hostname> since <acquired_at> (heartbeat <n>s ago, ttl <t>s)` |
| 10 | Plaintext secret (Principle I) | (from Spec 007's guard; unchanged) |

## Refusal semantics

Every refusal MUST cite the specific requirement (FR-###) or Principle it enforces, and identify the offending file/entry, so the operator can locate and fix it without guesswork (FR-019).

Examples:

```text
haex install
error: exit=9 key=install-lock-busy (FR-001 / FR-010)
  lock held by 31245@laptop-hex.local since 2026-08-31T14:20:11Z
  (heartbeat 3s ago, ttl 60s)
  hint: wait or investigate PID 31245; if the process is dead, run `haex verify --recover`

haex install
error: exit=4 key=commit-snapshot-mismatch (FR-006)
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

## Sibling subcommands

`haex constitution show` remains as the read-only inverse of `haex install`: it prints the byte-for-byte effective constitution from the currently published generation. It does not resolve, assemble, or write.

The former `haex constitution assemble` shortcut was retired in favour of `haex install` (which now owns the `--llm` and `--accept-merged` flags directly). Under the pre-user policy, keeping two commands doing the same work carried UX cost without adoption benefit.
