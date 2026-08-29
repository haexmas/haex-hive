# CLI Contract: `haex constitution show`

**Spec**: [spec.md](../spec.md) §US4, FR-032, FR-033
**Data model**: [data-model.md](../data-model.md) §InstallLock, §ConstitutionSource

## Synopsis

```
haex constitution show [--no-preface]
```

## Description

Print the current effective constitution to stdout. By default, a human-readable "Assembled from" preface synthesized from `.haex-hive/install.lock.constitution.sources[]` precedes the constitution content, separated by a `---` line. The preface is stdout-only; no file is modified. `--no-preface` suppresses the preface, printing only the byte-for-byte content of `.haex-hive/constitution.md`. The command is read-only — it never writes to any file.

## Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--no-preface` | boolean | false | Suppress the synthesized "Assembled from" preface. Useful for scripting (e.g., piping into a validator). |

## Inputs

- **File on disk**: `<repo-root>/.haex-hive/constitution.md`. MUST exist and be readable.
- **File on disk**: `<repo-root>/.haex-hive/install.lock`. MUST exist and validate against `install-lock.v2.schema.json`. Its `constitution.sources[]` MUST be non-empty.

## Outputs

- **Success (default)**: prints to stdout:

  ```
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

## Diagnostics

Refuse output (missing constitution):

```
error: exit=2 key=constitution-not-assembled
  .haex-hive/constitution.md does not exist
  hint: Run `haex constitution assemble` (on a device with LLM access if multi-source).
```

## Determinism guarantees

- Output is deterministic given the input files. Two invocations against the same on-disk state produce byte-identical stdout.

## Filesystem-atomicity guarantees

- N/A. This command performs no writes.

## Not in scope

- Colorized output, source-diff highlighting, or filtering to a subset of sources. Future extensions may add flags; `--no-preface` is the only Spec-007 flag beyond the default behavior.
