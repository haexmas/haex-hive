# `haex migrate` v2 → v3 — Transform Contract

**Spec**: 013
**Extends**: existing v1 → v2 migrator (Spec 007's `haex migrate`)
**Purpose**: turn every v2 manifest in a repository into a v3 proposal without touching originals, behind Principle VI's review gate.

## Command surface (unchanged)

```
haex migrate [--dry-run|--check]
```

`--dry-run` and `--check` are read-only. Absence of either flag is write mode, which materializes proposals per the placement rules below.

## Chained transforms

- **v1 → v2**: unchanged; runs first when the input is v1.
- **v2 → v3**: NEW; runs on any v2 input (originally v2, or v1 promoted to v2 in the same invocation).
- **v3 → v3**: no-op; proposals are not emitted on already-adopted v3 inputs (idempotency, FR-011).

## Files affected per invocation

- `.haex-hive.json` (consumer manifest at repo root).
- `manifest.json` at repo root (publisher-root manifest, if the current repo is a publisher).
- Every per-molecule `manifest.json` under repo paths declared by the publisher-root manifest.
- Publisher-root and per-molecule manifests read from immutable remote revisions (via `$HAEX_HIVE_STATE/repos/<source-digest>/`), when their v3 shape has not yet been adopted upstream.

## Proposal placement

| Input file | Proposal path |
|---|---|
| `.haex-hive.json` (repo-local) | `.haex-hive.json.migrated` (sibling) |
| Repo-local publisher-root `manifest.json` | `manifest.json.migrated` (sibling) |
| Repo-local per-molecule `manifest.json` | `<molecule-dir>/manifest.json.migrated` (sibling) |
| Publisher-root `manifest.json` at immutable remote SHA | `$HAEX_HIVE_STATE/migrations/<source-digest>/<revision>/manifest.json.migrated` |
| Per-molecule `manifest.json` at immutable remote SHA | `$HAEX_HIVE_STATE/migrations/<source-digest>/<revision>/<molecule-dir>/manifest.json.migrated` |

## Transforms

### Consumer manifest (`.haex-hive.json`)

- `haex_hive_version`: `"2"` → `"3"`.
- Top-level `atoms` list → renamed to `compounds`.
- Each compound entry: `includes` list → renamed to `molecules`.
- All other fields (`identity`, `haex_hive_min_version`, `groups`, `active_feature`, `identity_note`, per-compound `source`, `revision`, `track`, `config`) preserved byte-identically where names are unchanged.
- `haex_hive_min_version` rewriting:
  - Exact `2.x.y` → exact `3.x.y` (major replaced; minor and patch preserved).
  - Lower bound `>=2.x.y` → `>=3.0.0`.
  - Any other major on the constraint refuses as unsupported (`unsupported-min-version-constraint`).

### Per-molecule manifest

- `haex_hive_version`: `"2"` → `"3"`.
- `contributes` scalar map → `atoms` category map with list values.
  - Each scalar `contributes.<category> = "<path>"` becomes `atoms.<category> = ["<path>"]`.
  - A directory-form contribution (`contributes.<category> = "<dir>/"`) expands deterministically to the list of regular files within that directory, sorted lexically.
- `priority` missing → default to `100`. Existing integer priorities preserved unchanged.
- Other fields (`id`, `version`, `config_schema`, `defaults`) preserved.
- No profile-composition list is emitted.

### Publisher-root manifest

- `haex_hive_version`: `"2"` → `"3"`.
- Top-level `atoms` map → renamed to `molecules`.
- Each entry preserves `path`, `version`, and optional `description` byte-identically.
- `publisher` (the reverse-DNS namespace) preserved byte-identically.

## Determinism

- The transform is a pure function of the input bytes. Same input yields byte-identical proposals across satellites and OSes.
- Sort order in expanded directory listings is Unicode code-point lexicographic on POSIX-normalized paths.

## Idempotency (FR-011)

- Input at `haex_hive_version: "3"`: no proposal emitted; the transform detects the shape at read time and short-circuits.
- Running `haex migrate` a second time on a repository that already applied the proposals is a no-op.

## Failure cleanup (FR-010)

- Every temporary file and every proposal produced by a single invocation is registered in a per-invocation registry.
- On any transform, validation, or write failure inside the invocation, the registry removes every registered file before propagating the error. Originals are never touched.
- `--dry-run` and `--check` mutate no filesystem state.

## Review-gate discipline (Principle VI)

- The transform NEVER writes to the original file. Every output is a `.migrated` sibling or a state-directory proposal.
- The command prints a unified diff for every input/proposal pair, including the target path and adoption instructions:
  - Local files: manual `mv <file>.migrated <file>` after review.
  - Remote publisher files: manual copy of the proposal into a publisher checkout, PR, and consumer-side pin update.
- v3 readers do not accept files until the operator has adopted the proposals; no automatic adoption path exists.

## Refusal keys

| Key | Meaning |
|---|---|
| `unsupported-min-version-constraint` | `haex_hive_min_version` has a major other than `2.x.y` or `>=2.x.y`. Nothing written. |
| `directory-expansion-empty` | A directory-form v2 `contributes` entry names an empty directory. Nothing written. |
| `proposal-validation-failed` | A produced proposal did not validate against the corresponding v3 schema. All proposals from the invocation are removed. |
| `proposal-target-conflict` | A proposal target path already exists and its content differs from the freshly computed proposal. Nothing new is written; the operator resolves the conflict manually. |

## Exit codes

- `0`: transform complete; proposals emitted (write mode) or would be emitted (`--dry-run`/`--check`).
- `1`: transform ran, but at least one input was already v3 (no proposal) and at least one refusal-key case triggered on another input.
- `2`: hard refusal per a refusal key above; no proposals kept.
