# Implementation Plan: v3 Vocabulary and `haex add` / `haex remove` CLI

**Branch**: `013-add-cli-and-molecule-rename` | **Date**: 2026-09-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/013-add-cli-and-molecule-rename/spec.md`
**Authoritative design input**: [docs/plans/2026-09-02-spec-013-add-cli-and-molecule-rename-design.md](../../docs/plans/2026-09-02-spec-013-add-cli-and-molecule-rename-design.md)

## Summary

Retire the v2 manifest vocabulary from the tool and replace it with v3 in one release. The consumer manifest gets `compounds[]` (renamed from `atoms[]`) with per-entry `molecules[]` (renamed from `includes[]`); per-molecule manifests replace the scalar `contributes` with the `atoms` category map (already specified in Spec 007 v3); publisher-root manifests rename their inner `atoms{}` to `molecules{}`. Two new CLI subcommands (`haex add` and `haex remove`) turn adoption into a one-line operation while keeping every publication going through the existing `haex install` transaction, and `haex migrate` grows a v2→v3 transform behind Principle VI's review gate so haex-hive itself and any downstream consumer can transition.

Technical approach: extend the existing Python 3.10+ CLI (`src/haex_hive/`) with a v3 schema payload under `src/haex_hive/schema/data/`, replace the v2 schemas rather than layering them (per operator decision 2026-09-04, no dual-vocabulary tolerance layer). Reshape the four model classes (`consumer_manifest.py`, `atom_manifest.py`, `publisher_manifest.py`, `install_lock.py`) around v3 field names. Add `src/haex_hive/cli/add.py` and `src/haex_hive/cli/remove.py` as thin wrappers over a new `write_and_reinstall(...)` helper that acquires a permanent advisory manifest lock on `.haex-hive.json.lock`, atomically rewrites `.haex-hive.json`, calls the existing install pipeline in-process (accepting the held-lock context), and rolls the manifest edit back under the still-held lock on downstream install failure — except when the install failure surfaces `constitution-review-pending`, in which case the manifest edit persists so the operator can follow up with `haex install --accept-merged <candidate>` (see D9 in [research.md](research.md)). Extend `src/haex_hive/migrate/transform.py` with a second v2→v3 transform that emits sibling `.migrated` proposals (`.haex-hive.json.migrated`, `manifest.json.migrated`) or state-directory proposals for remote publisher manifests, validates every proposal against the v3 schema, and cleans up every temporary file on failure. Publisher-manifest fetch during `haex add` uses a `git init` + `git fetch origin <sha> --depth 1` + detached-checkout sequence into a `tempfile.TemporaryDirectory()` (or into the existing `$HAEX_HIVE_STATE/repos/<clone-hash>/` clone when it exists); this pattern works on the git 2.30+ baseline documented for the project. The newer `git clone --revision` flag (git 2.49+) is NOT required. Bump the tool's own `pyproject.toml` version from `2.0.0.dev0` to `3.0.0.dev0` and migrate haex-hive's own root manifest and `.haex-hive.json` under the same PR so the repo continues to install itself after the change lands.

## Technical Context

**Language/Version**: Python 3.10+ (matches Spec 007's and Spec 008's baseline; `pyproject.toml` `requires-python = ">=3.10"`, `target-version = "py310"`).
**Primary Dependencies**: `jsonschema>=4.18` (already present, no new dependency). Python stdlib for everything else: `json`, `hashlib`, `pathlib`, `os` (`replace`, `fsync`), `fcntl` (POSIX advisory locks), `ctypes` (Windows `LockFileEx`/`UnlockFileEx`), `subprocess` (for `git ls-remote`, `git init`, `git fetch origin <sha> --depth 1`, `git checkout FETCH_HEAD`, already used elsewhere), `dataclasses`, `contextlib`, `tempfile`, `secrets`. Runtime **git version requirement**: 2.30+ (matches the project's existing documented baseline). The `git clone --revision <sha>` flag introduced in git 2.49 is deliberately NOT used; the `git fetch origin <sha> --depth 1` pattern below covers arbitrary SHAs on the 2.30 baseline. No new external Python dependency.
**Storage**: Filesystem only. Inputs/outputs: `.haex-hive.json` (consumer manifest, v3 shape after this feature), root `manifest.json` (publisher manifest, v3 shape), per-molecule `manifest.json` (v3 shape). Device-local: publisher clones under `$HAEX_HIVE_STATE/repos/<clone-hash>/` (unchanged from Spec 007), install locks under `$HAEX_HIVE_STATE/locks/<repo-key>/` (unchanged from Spec 008), and a new migration-proposal tree at `$HAEX_HIVE_STATE/migrations/<source-digest>/<revision>/<repo-relative-path>.migrated` for publisher-manifest proposals derived from immutable remote revisions. The permanent manifest lock file `.haex-hive.json.lock` lives at the repo root, is created once if absent, and is never renamed or deleted by the tool.
**Testing**: `pytest`. Contract tests cover the v3 schemas (consumer, molecule, publisher, install-lock). Unit tests cover the migrate transform (v1→v2 unchanged, new v2→v3, idempotency, cleanup on failure). Integration tests exercise `haex add`, `haex remove`, and `haex migrate` end-to-end against fixture repos on a real filesystem with `$HAEX_HIVE_STATE` redirected to a tmpdir, and against a fake remote publisher (a bare git repo in a tmpdir) for the `haex add` fetch path.
**Target Platform**: Linux, macOS, Windows (per Principle II). Manifest-lock acquisition uses `fcntl.flock` on POSIX and Win32 `LockFileEx`/`UnlockFileEx` on Windows, matching Spec 008's writer-lock pattern.
**Project Type**: Single-project Python CLI (unchanged). New subcommands and modules; no restructure.
**Performance Goals**: `haex add <source-url> <molecule-id>` completes in under 5 seconds on a warm satellite for a small publisher (≤10 molecules), including the shallow-clone-plus-manifest-read and the ensuing install pass on an unchanged state (Spec 008 SC-003 idempotent path). `haex remove` completes in under 3 seconds. `haex migrate` on a v2 repo with ≤10 files completes in under 2 seconds.
**Constraints**: Deterministic v3 schema shape (JSON Schema draft 2020-12, sorted keys, no trailing commas). Cross-platform correctness with no OS-specific primitives beyond `os.replace`, `os.fsync`, `fcntl.flock`/Win32 `LockFileEx`. Every intermediate file is either a `.tmp` sibling that renames into place atomically or a proposal under a well-defined `.migrated` or `$HAEX_HIVE_STATE/migrations/...` tree. No plaintext secrets in any manifest, proposal, or lockfile row (Principle I). No local absolute paths in any versioned config emitted (Principle II). All git revisions written to `.haex-hive.json` are full 40-hex SHAs (Principle IV).
**Scale/Scope**: Per-repo tool. A consumer's `.haex-hive.json` v3 typically declares 1–10 compounds; each compound holds 1–5 molecules. Publisher manifests declare 1–20 molecules. Migration touches ≤20 files per repository invocation. No hard limits imposed by design.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version at plan time: **1.4.0** (ratified 2026-08-26, last amended 2026-09-02).

| Principle | Status | Justification |
|---|---|---|
| I. No Secrets in Git (NON-NEGOTIABLE) | PASS | The feature manipulates manifest metadata (identifiers, revisions, filenames, priorities); no secret material is read, written, or transported. Migration proposals carry no secrets. |
| II. No Local Absolute Paths in Versioned Config (NON-NEGOTIABLE) | PASS | Every path emitted into versioned config is either a git-remote URL (in `.haex-hive.json.compounds[].source`), a full SHA (in `.haex-hive.json.compounds[].revision`), or a repo-relative POSIX path (in molecule-manifest `atoms{}` values and publisher-manifest `molecules{}.path`). Local absolute paths appear only under device-local `$HAEX_HIVE_STATE/...`, which is never versioned. |
| III. Project Identity Is Device-Independent (NON-NEGOTIABLE) | PASS | The consumer manifest continues to carry `identity` as a reverse-DNS string bound to the git remote URL or `.harness-id`, per Spec 007. No new identity derivation. Cross-device addressing is out of scope for this feature. |
| IV. Cross-Repo References Pin Immutable Revisions (NON-NEGOTIABLE) | PASS | FR-015 requires that `haex add` write full 40-hex SHAs verbatim into `.haex-hive.json`, whether the SHA came from `--revision=<SHA>` or from `git ls-remote HEAD` resolution. Branch or `HEAD` references are never written. Publisher-manifest fetch during `haex add` uses the resolved SHA end-to-end. |
| V. External Sources Are Opt-in Per Project (NON-NEGOTIABLE) | PASS | `compounds[]` (renamed from v2 `atoms[]`) remains the allowlist mechanism per Principle V's implementation guidance ("the concrete field name is bound to the `.haex-hive.json` schema version and MAY change across schema majors without altering this principle"). An empty or missing `compounds[]` still refuses external inheritance. Migration preserves entries; `haex add` extends only what the operator explicitly requested; `haex remove` retracts. No implicit inheritance path is introduced. |
| VI. Self-Modifying Instructions Are Always Review-Gated (NON-NEGOTIABLE) | PASS | Schema migrations flow through `haex migrate` per the amendment at Principle VI v1.3.0. FR-008 through FR-013 encode the `.migrated` sidecar rule, deterministic transforms, unified-diff review output, and `--dry-run`/`--check` support. The `haex install --accept-merged <candidate>` two-phase flow that `haex add` yields to for constitution merges is Principle VI's review gate; `haex add` never bypasses it (FR-020). Manifest edits by `haex add` and `haex remove` are direct writes to `.haex-hive.json` and are review-gated by PR flow rather than in-tool review, matching how any operator edit of `.haex-hive.json` today is reviewed. |
| VII. Relay Unavailability Never Blocks Local Work (NON-NEGOTIABLE) | PASS | The feature is fully offline aside from `haex add`'s outbound `git ls-remote`/`git clone --depth 1` calls, which are direct git operations against the operator-provided `<source-url>` and are not Nostr-relay operations. Existing behavior of `haex install`, `haex migrate --check`, and `haex remove` on already-populated publisher clones is unchanged and remains offline. |
| VIII. No Concealment Instructions in Agent Output (NON-NEGOTIABLE) | PASS | The tool produces operator-facing diagnostics (refusal keys with contextual detail, unified diffs, review candidate paths). None of that output is consumed by a downstream agent as instructions; no concealment surface exists. |

**Result**: Zero violations. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/013-add-cli-and-molecule-rename/
├── plan.md                              # This file (/speckit-plan output)
├── spec.md                              # /speckit-specify output
├── research.md                          # Phase 0 output (/speckit-plan)
├── data-model.md                        # Phase 1 output (/speckit-plan)
├── quickstart.md                        # Phase 1 output (/speckit-plan)
├── contracts/                           # Phase 1 output (/speckit-plan)
│   ├── consumer-manifest.v3.schema.json   # `.haex-hive.json` v3 shape
│   ├── molecule-manifest.v3.schema.json   # per-molecule `manifest.json` v3 shape (copied from Spec 007)
│   ├── publisher-manifest.v3.schema.json  # root `manifest.json` v3 shape
│   ├── install-lock.v3.schema.json        # `install.lock` v3 shape (renames only)
│   ├── haex-add.cli.md                    # `haex add` CLI surface
│   ├── haex-remove.cli.md                 # `haex remove` CLI surface
│   └── haex-migrate.v2-to-v3.md           # migrate transform contract
├── checklists/
│   └── requirements.md                  # /speckit-specify output (already present)
└── tasks.md                             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Single-project Python CLI extension. Reuses existing `src/haex_hive/` package; adds two subcommands and reshapes four model classes. No restructure of the landed layout from Specs 007 and 008.

```text
src/
└── haex_hive/
    ├── cli/
    │   ├── main.py                    # extend: register `add` and `remove` subcommands
    │   ├── add.py                     # NEW: `haex add` handler
    │   ├── remove.py                  # NEW: `haex remove` handler
    │   ├── install.py                 # extend: accept held-lock context from add/remove
    │   └── migrate.py                 # extend: expose v2→v3 as a second transform
    ├── model/
    │   ├── consumer_manifest.py       # REWORK: v3 fields (compounds, molecules)
    │   ├── atom_manifest.py           # RENAME to molecule_manifest.py; REWORK to atoms{}
    │   ├── publisher_manifest.py      # REWORK: molecules{} map
    │   └── install_lock.py            # REWORK: v3 field renames
    ├── migrate/
    │   └── transform.py               # extend: add v2→v3 transform
    ├── schema/
    │   └── data/
    │       ├── consumer-manifest.v3.schema.json    # NEW (v2 removed)
    │       ├── molecule-manifest.v3.schema.json    # NEW (renamed from atom-manifest.v2)
    │       ├── publisher-manifest.v3.schema.json   # NEW (v2 removed)
    │       ├── install-lock.v3.schema.json         # NEW (v2 removed)
    │       └── visibility-marker.v1.schema.json    # unchanged
    ├── constitution/
    │   └── resolve.py                 # extend: read molecule.atoms.constitution list
    ├── install/                       # extend: manifest-lock coordination for held-lock context
    │   └── lock.py                    # extend
    └── io/                            # unchanged

tests/
├── contract/                          # NEW subpackage or extended
│   └── test_v3_schemas.py             # v3 schema shape assertions
├── unit/
│   ├── test_migrate_v2_to_v3.py       # NEW: transform correctness, idempotency, cleanup
│   ├── test_manifest_lock.py          # NEW: `.haex-hive.json.lock` semantics
│   └── (existing unit tests updated)  # v2 references removed
├── cli/
│   ├── test_add.py                    # NEW: `haex add` end-to-end
│   └── test_remove.py                 # NEW: `haex remove` end-to-end
└── (existing test tree stays)         # updated to v3 fixtures
```

**Structure Decision**: Single-project Python CLI, extending the layout established by Specs 007 and 008. New CLI entry points live under `src/haex_hive/cli/`; model reshaping stays in `src/haex_hive/model/`; migration extends `src/haex_hive/migrate/`. The atom→molecule rename is a package-level rename (`atom_manifest.py` → `molecule_manifest.py`) applied in one sweep to keep import paths consistent with the vocabulary.

## Complexity Tracking

> No constitution-check violations to justify. This section is intentionally empty.
