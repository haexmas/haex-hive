# CLI Contract: `haex constitution show`

**Spec**: [spec.md](../spec.md) §US4, FR-032, FR-033
**Data model**: [data-model.md](../data-model.md) §InstallLock, §ConstitutionSource

## Synopsis

```console
haex constitution show [--no-preface]
```

## Description

Print the current effective constitution to stdout. Before emitting any stdout, recompute the D15 `haex-hive-tree-v1` digest of the one-file `constitution.md` tree and compare it with `.haex-hive/install.lock.constitution.content_integrity`. A mismatch refuses without output. On a match, a human-readable "Assembled from" preface synthesized from `.haex-hive/install.lock.constitution.sources[]` precedes the constitution content, separated by a `---` line. The preface is stdout-only; no file is modified. `--no-preface` suppresses the preface after successful verification, printing only the byte-for-byte content of `.haex-hive/constitution.md`. The command is read-only — it never writes to any file.

## Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--no-preface` | boolean | false | Suppress the synthesized "Assembled from" preface. Useful for scripting (e.g., piping into a validator). |

## Inputs

- **File on disk**: `<repo-root>/.haex-hive/constitution.md`. MUST exist and be readable.
- **File on disk**: `<repo-root>/.haex-hive/install.lock`. MUST exist and validate against `install-lock.v2.schema.json`. Its `constitution.sources[]` MUST be non-empty.
- **Transaction state**: `<repo-root>/.haex-hive/constitution-transaction.json` MUST be absent. Its presence means an interrupted assembly is awaiting recovery; this read-only command refuses without modifying it.

## Outputs

- **Success (default)**: prints to stdout:

  ```text
  # Assembled from
  - <atom-id-1> @ <revision-short-sha> (<canonical-source-url>)
  - <atom-id-2> @ <revision-short-sha> (<canonical-source-url>)
  
  ---
  
  <byte-for-byte content of .haex-hive/constitution.md>
  ```

  The preface enumerates every source in `constitution.sources[]` in alphabetical atom-ID order. Revision is displayed as the first 7 characters of the SHA for readability; the full SHA is available in `install.lock`.

  Exit 0.

- **Success (`--no-preface`)**: prints only the byte-for-byte content of `.haex-hive/constitution.md`. Exit 0.

## Exit codes

| Code | Meaning | Notes |
|---|---|---|
| 0 | Success | |
| 2 | Missing constitution — `.haex-hive/constitution.md` does not exist | FR-033. Points at `haex constitution assemble`. |
| 3 | Missing install.lock — `.haex-hive/install.lock` does not exist or lacks a `constitution` section | Suggests running `haex constitution assemble`. |
| 4 | Corrupt install.lock — `.haex-hive/install.lock` failed schema validation | Reports the specific validator failure. |
| 5 | System refuse — `.haex-hive.json` version mismatch (FR-034) | Only checked if the file exists; missing `.haex-hive.json` is not a refuse condition for this read-only command. |
| 6 | Constitution integrity mismatch — `constitution.md` does not match `constitution.content_integrity` | Emits no stdout; suggests `git pull` or `haex constitution assemble`. |
| 7 | Incomplete assembly transaction — a constitution journal is present | Emits no stdout; suggests `haex constitution assemble` to perform recovery. |

## Diagnostics

Refuse output (missing constitution):

```text
error: exit=2 key=constitution-not-assembled
  .haex-hive/constitution.md does not exist
  hint: Run `haex constitution assemble` (on a device with LLM access if multi-source).
```

Integrity-mismatch refuse output:

```text
error: exit=6 key=constitution-integrity-mismatch
  .haex-hive/constitution.md does not match install.lock constitution.content_integrity
  hint: Run `git pull` or `haex constitution assemble` to restore a matched generation.
```

Incomplete-transaction refuse output:

```text
error: exit=7 key=constitution-transaction-incomplete
  .haex-hive/constitution-transaction.json is present
  hint: Run `haex constitution assemble` to recover the paired output generation.
```

## Determinism guarantees

- Output is deterministic given the input files. Two invocations against the same on-disk state produce byte-identical stdout.

## Filesystem-atomicity guarantees

- N/A. This command performs no writes.

## Not in scope

- Colorized output, source-diff highlighting, or filtering to a subset of sources. Future extensions may add flags; `--no-preface` is the only Spec-007 flag beyond the default behavior.
