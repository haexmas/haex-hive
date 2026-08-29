# CLI Contract: `haex migrate`

**Spec**: [spec.md](../spec.md) §US1, FR-012–FR-020
**Data model**: [data-model.md](../data-model.md) §MigrationSidecar, §ConsumerManifest
**Design**: [Spec 007 design doc](../../../docs/plans/2026-08-28-spec-007-unified-manifest-design.md) §D10, §"Migration path v1 → v2"

## Synopsis

```console
haex migrate [--dry-run | --check]
```

## Description

Rewrite the current repository's `.haex-hive.json` v1 file into the v2 shape defined by the design doc's migration table. In write mode, any transient `.migrated` sidecar from a prior run is invalidated before evaluating the current proposal. Before printing a diff or writing a new sidecar, both the complete original v1 bytes and the proposed sidecar's complete serialized bytes pass the FR-038 plaintext-secret guard, including secrets in a source-only field omitted from the v2 proposal and preserved free-text fields such as `identity_note`. The v2 proposal is written to a same-directory `.haex-hive.json.migrated` sidecar; the original file is left untouched. A unified diff between the original and the proposal is printed to stdout for human review. The operator moves the sidecar over the original manually (`mv .haex-hive.json.migrated .haex-hive.json`) and commits the result in a reviewable PR. Preview modes leave any existing sidecar untouched.

If the input file is already v2 (`haex_hive_version: "2"`), the command reports `already migrated to v2` and exits 0 without writing anything.

## Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | boolean | false | Do not write the sidecar; only print the diff to stdout. Exit 0 if a real run would succeed, non-zero otherwise. |
| `--check` | boolean | false | Alias for `--dry-run`. |

`--dry-run` and `--check` are mutually exclusive. Passing both is a usage error (exit 64) and performs no filesystem mutation.

## Inputs

- **File on disk**: `<repo-root>/.haex-hive.json` (v1 or v2). MUST exist and be readable, or the command refuses.
- **Git state**: `<repo-root>` MUST be a git repository with a resolvable `remote.origin.url` if the v1 file's `harness_sources[i].repository == "self"`.
- **Publisher clones on disk** (for each `source` referenced by v1 entries after `self`-resolution): a git clone containing the pinned revision. Location: `$HAEX_HIVE_STATE/repos/<clone-hash>/`. If a required clone is missing or the pinned revision is unavailable, the command refuses.

## Outputs

- **Success (write mode)**: writes `<repo-root>/.haex-hive.json.migrated` with the v2 proposal (deterministic serialization per FR-036), then prints the unified diff to stdout. Exit 0.
- **Success (dry-run or check)**: prints only the unified diff to stdout. Exit 0. A pre-existing `.haex-hive.json.migrated` is preserved byte-for-byte.
- **Already-v2**: prints `already migrated to v2 (haex_hive_version: 2)` to stderr, exits 0. No file writes.
- **Refuse**: prints one or more diagnostic lines to stderr per the exit-code table below. Non-zero exit. Any temporary file created during evaluation is unlinked. `.haex-hive.json` and any pre-existing `.haex-hive.json.migrated` sidecar are left untouched OR deleted per FR-016 (see exit codes 2 and 3 below).

## Exit codes

| Code | Meaning | Notes |
|---|---|---|
| 0 | Success (write, dry-run, or already-v2) | |
| 2 | Input refuse — the v1 file's shape cannot be deterministically migrated | See FR-013, FR-019, FR-020. In write mode, `.haex-hive.json` is untouched and any sidecar is deleted; in preview mode, an existing sidecar is preserved. |
| 3 | I/O refuse — missing publisher clone, unresolvable `self` remote, unavailable pinned revision | See "Inputs" above. In write mode, `.haex-hive.json` is untouched and any sidecar is deleted; in preview mode, an existing sidecar is preserved. |
| 4 | Post-migration validation refuse — the produced v2 sidecar failed the v2 JSON Schema | Should not happen in practice; indicates a bug in the migration table. In write mode, the temporary file and sidecar are removed; in preview mode, no temporary file is created and an existing sidecar is preserved. |
| 5 | System refuse — the repo has no `.haex-hive.json`, or the CLI's version does not satisfy `.haex-hive.json`'s `haex_hive_min_version` | See FR-034 also. |
| 10 | Plaintext-secret safety refuse | `key=plaintext-secret-detected`; the original input or proposed serialized sidecar contains a plaintext-secret signature. The diagnostic does not echo the matched value; no diff or new sidecar is written. In write mode, a pre-existing sidecar was invalidated before evaluation and remains absent; preview mode preserves it. |
| 64 | Usage error — both `--dry-run` and `--check` supplied | No filesystem mutation. |

## Diagnostics

Every refuse diagnostic includes:

- The exit code.
- A machine-parseable diagnostic key (e.g., `credential-in-source-url`, `permission-only-entry`, `identity-not-github-nor-reverse-dns`).
- The `.haex-hive.json` entry index (for `harness_sources[]`-scoped errors) or the affected field path.
- The offending value (with credential material redacted if applicable). For exit 10, omit the matched value entirely and report only a non-sensitive field path.
- A single-sentence remediation hint.

Example refuse output:

```text
error: exit=2 key=credential-in-source-url entry=harness_sources[1]
  offending source: https://***REDACTED***@github.com/example/repo.git
  hint: Remove credentials from the URL. Configure git to use a credential helper instead.
```

## Determinism guarantees

- Two invocations of `haex migrate` in write mode against the same input `.haex-hive.json`, the same publisher-clone state, and the same `remote.origin.url` MUST produce byte-identical `.haex-hive.json.migrated` output (FR-013, FR-036).
- `--dry-run` and `--check` output MUST be byte-identical to the diff that a real run would print.

## Filesystem-atomicity guarantees

- No partial-write state ever exists for the `.migrated` sidecar. It is written to a same-directory `.haex-hive.json.migrated.<random>.tmp` and atomically renamed via `os.replace()` (FR-015, R6).
- On write-mode refuse codes 2/3/4/5/10, the temporary file is unlinked when present and no `.migrated` sidecar remains. On preview-mode refusal or usage error, neither a temporary file nor a sidecar mutation occurs.

## Not in scope

- `haex migrate` does NOT invoke any network fetches. It reads from local publisher clones only. Fetching is out of scope until Spec 008's `haex install` / `haex add` land.
- `haex migrate` does NOT write into `.haex-hive/` (constitution.md / install.lock). Those are Spec 008 outputs and require the operator to run `haex constitution assemble` (Spec 007's separate command) after moving the migrated file over the original.
