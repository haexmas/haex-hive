# Implementation Plan: Unified Manifest v2 + Migration + Constitution Assemble

**Branch**: `007-unified-manifest-v2` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/007-unified-manifest-v2/spec.md`
**Design source of truth**: [docs/plans/2026-08-28-spec-007-unified-manifest-design.md](../../docs/plans/2026-08-28-spec-007-unified-manifest-design.md)

## Summary

Deliver the CLI-level surface for the unified-manifest v2 architecture: the `.haex-hive.json` v2 schema, publisher-side root and per-atom `manifest.json` schemas, the review-gated `haex migrate` command that rewrites v1 files into v2 via a `.migrated` sidecar with unified-diff output, and the `haex constitution assemble` + `haex constitution show` commands that produce a byte-deterministic (single-source) or LLM-merged (multi-source) `.haex-hive/constitution.md` with content-hash recording in `.haex-hive/install.lock`. Haex-hive migrates itself as the reference case.

Technical approach (from research): Python 3.10+ stdlib-first with three targeted external dependencies (`jsonschema` for Draft 2020-12 validation, `PyYAML` with `safe_load` + custom serializer for deterministic YAML I/O when needed, `Jinja2` reserved for Spec 010 hydration but not used in Spec 007). CLI structure via stdlib `argparse` with subparser tree (`haex migrate`, `haex constitution {assemble,show}`). Git operations via `git` subprocess (bare `git show <sha>:<path>`, `git rev-parse`, `git remote get-url`) — no `pygit2`/`GitPython` dependency. Deterministic JSON serialization via stdlib `json` (`sort_keys=True`, LF endings, trailing newline). Unified-diff generation via stdlib `difflib.unified_diff`. Atomic file publication via write-to-temp + `os.replace` in same directory + parent-directory fsync (POSIX) / `MoveFileExW(MOVEFILE_REPLACE_EXISTING)` (Windows-portable via `os.replace` which uses that API).

## Technical Context

**Language/Version**: Python 3.10+ (matches D8's pip-installable distribution decision; 3.10 chosen as the lowest that supports every `match`/PEP-604-`X | Y` union / `dataclasses` feature we lean on)
**Primary Dependencies**: `jsonschema>=4.18` (Draft 2020-12 support required — 4.18 is the first release with a stable Draft 2020-12 validator); Python stdlib only for everything else in Spec 007's scope (`json`, `argparse`, `difflib`, `hashlib`, `pathlib`, `subprocess`, `re`, `base64`, `dataclasses`). PyYAML and Jinja2 are Spec-008/010 dependencies — Spec 007 does not import them.
**Storage**: Filesystem-only. Spec 007 reads and writes files under the consumer repo: `.haex-hive.json`, `.haex-hive.json.migrated`, `.haex-hive/constitution.md`, `.haex-hive/install.lock`. It reads publisher-repo git objects via `git show <sha>:<path>` against pre-cloned publisher repos under `$HAEX_HIVE_STATE/repos/<clone-hash>/` (D15). No network in the hot path — clones are pre-existing on the operator's device (created by future `haex add`, out of scope for Spec 007).
**Testing**: `pytest` with fixture repos on disk. Contract tests validate every JSON Schema against positive/negative fixtures under `tests/fixtures/`. Integration tests exercise the CLI end-to-end via `subprocess.run(["haex", ...])`. Migration tests use frozen v1 fixtures and assert byte-identical v2 sidecar output. Test-only helpers may set `$HAEX_HIVE_STATE` to a temporary path for isolation.
**Target Platform**: Linux, macOS, Windows (Windows-portability is a Spec-007 correctness requirement per D15; no symlinks, no junctions, no bind mounts).
**Project Type**: Single-project CLI. Python package `haex_hive/` published to PyPI as `haex-hive`; `haex` console script defined in `pyproject.toml`.
**Performance Goals**: `haex migrate --dry-run` completes in under 5 seconds on a well-formed v1 file (SC-004). `haex constitution assemble` refuses on missing-LLM in multi-source case in under 1 second (SC-007). No per-request throughput targets — this is a one-shot CLI.
**Constraints**: Deterministic output (byte-identical across runs on identical inputs — FR-036, D9). Cross-platform correctness with no OS-specific filesystem primitives outside `os.replace` and `fsync`. No plaintext secrets in any committed content (FR-029 explicit; no schema-level secret surface). Every pathname replacement is atomic; constitution + lock publication uses the FR-035 durable journal and startup recovery protocol.
**Scale/Scope**: Per-repo tool. A consumer's `.haex-hive.json` v2 typically declares 1-10 atom entries; a project constitution is a few KB to tens of KB; `install.lock` for Spec-007 scope is under 1 KB. Publisher-side registries in scope for Spec 007 read: haex-hive's own root + atom manifest (one atom entry, `constitution` type).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version at plan time: **1.3.0** (ratified 2026-08-26, last amended 2026-08-29 via PR #9).

| Principle | Status | Justification |
|---|---|---|
| I. No Secrets in Git (NON-NEGOTIABLE) | PASS | FR-029 explicitly forbids any secret surface in `constitution.md` and `install.lock`; publisher schemas cannot declare secret fields (design D7). All committed content is public. |
| II. No Local Absolute Paths in Versioned Config (NON-NEGOTIABLE) | PASS | Every path in `.haex-hive.json` v2, publisher `manifest.json`, atom `manifest.json`, and `install.lock` is repo-relative (POSIX with `/`, no `.`/`..` segments). `$HAEX_HIVE_STATE` resolves per-OS at runtime and is device-local, never versioned. |
| III. Project Identity Is Device-Independent (NON-NEGOTIABLE) | PASS | `identity` is reverse-DNS (D3), derived deterministically from the git remote URL by `haex migrate` (lowercase + reverse-DNS conversion). Same across every device. |
| IV. Cross-Repo References Pin Immutable Revisions (NON-NEGOTIABLE) | PASS | Every `atoms[]` entry carries `source + revision` with the full 40-char SHA (FR-002). Track is optional and non-authoritative. Extension in v1.3.0 to allow directory-shaped `path` is honored: publisher root manifest and atom `manifest.json` both live at pinned SHAs. |
| V. External Sources Are Opt-in Per Project (NON-NEGOTIABLE) | PASS | `.haex-hive.json`'s `atoms[]` is the explicit allowlist. An empty array grants no external inheritance. Migration refuses to widen v1 permission-only entries into v2 atom grants (FR-019). |
| VI. Self-Modifying Instructions Are Always Review-Gated (NON-NEGOTIABLE) | PASS | `haex migrate` writes a `.migrated` sidecar plus stdout diff (FR-014–FR-018), never overwrites the original. Constitution v1.3.0's Principle-VI clarification (from PR #9) codifies this pattern; Spec 007 implements it. |
| VII. Relay Unavailability Never Blocks Local Work (NON-NEGOTIABLE) | PASS | Spec 007 has zero Nostr-relay code path. Constitution merge sync (design D2) uses git as primary channel; Nostr notify is optional and out of Spec 007's scope. |
| VIII. No Concealment Instructions in Agent Output (NON-NEGOTIABLE) | PASS | Spec 007's commands emit only diagnostic text, JSON schemas, and unified diffs — no natural-language content that could embed concealment instructions to a downstream agent. |

**Result**: Zero violations. No entries needed in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/007-unified-manifest-v2/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # /speckit-specify + /speckit-clarify output
├── research.md          # Phase 0 output (/speckit-plan)
├── data-model.md        # Phase 1 output (/speckit-plan)
├── quickstart.md        # Phase 1 output (/speckit-plan)
├── contracts/           # Phase 1 output (/speckit-plan)
│   ├── haex-hive.v2.schema.json
│   ├── publisher-manifest.v2.schema.json
│   ├── atom-manifest.v2.schema.json
│   ├── install-lock.v2.schema.json
│   ├── haex-migrate.cli.md
│   ├── haex-constitution-assemble.cli.md
│   └── haex-constitution-show.cli.md
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Single-project Python CLI. Package layout targeting a PyPI-installable distribution with the `haex` console script.

```text
src/
└── haex_hive/
    ├── __init__.py
    ├── __main__.py                    # `python -m haex_hive` entry
    ├── cli/
    │   ├── __init__.py
    │   ├── main.py                    # argparse root + subcommand dispatch
    │   ├── migrate.py                 # `haex migrate`
    │   ├── constitution.py            # `haex constitution {assemble,show}`
    │   └── diagnostics.py             # unified error-emit helpers
    ├── schema/
    │   ├── __init__.py
    │   ├── loader.py                  # loads JSON Schemas from packaged data
    │   ├── validator.py               # jsonschema Draft 2020-12 wrapper
    │   └── data/                      # packaged schemas (installed with wheel)
    │       ├── haex-hive.v2.schema.json
    │       ├── publisher-manifest.v2.schema.json
    │       ├── atom-manifest.v2.schema.json
    │       └── install-lock.v2.schema.json
    ├── model/
    │   ├── __init__.py
    │   ├── consumer_manifest.py       # ConsumerManifest, AtomEntry, ConfigEntry
    │   ├── publisher_manifest.py      # PublisherManifest, PublisherAtomEntry
    │   ├── atom_manifest.py           # AtomManifest, ContributesBlock
    │   ├── install_lock.py            # InstallLock, ConstitutionSection
    │   ├── source_url.py              # canonical normalization (D3)
    │   ├── atom_id.py                 # reverse-DNS grammar
    │   └── version_constraint.py      # `X.Y.Z` and `>=X.Y.Z` grammar (FR-006)
    ├── git/
    │   ├── __init__.py
    │   ├── show.py                    # git show <sha>:<path>
    │   ├── remote.py                  # git remote get-url origin
    │   └── revparse.py                # git rev-parse (short→full SHA)
    ├── migrate/
    │   ├── __init__.py
    │   ├── detect.py                  # v1-vs-v2 detection
    │   ├── transform.py               # deterministic v1→v2 rewrite
    │   └── sidecar.py                 # sidecar+diff atomic publication
    ├── constitution/
    │   ├── __init__.py
    │   ├── resolve.py                 # atoms[]→ContributionFile resolution (D11)
    │   ├── assemble.py                # single-source straight-copy + LLM path stub
    │   ├── llm.py                     # LLM invocation abstraction (research-topic)
    │   └── show.py                    # synthesized preface + body print
    ├── io/
    │   ├── __init__.py
    │   ├── atomic.py                  # write-to-temp + os.replace + fsync
    │   ├── transaction.py             # journaled constitution + lock pair publication/recovery
    │   ├── json_deterministic.py      # sort_keys=True, LF, trailing newline
    │   └── file_hash.py               # D15 tree serialization + sha256-<base64> encoding
    └── util/
        ├── __init__.py
        ├── errors.py                  # typed exception hierarchy
        └── exit_codes.py              # canonical exit codes (Spec 007 scope)

tests/
├── contract/                          # JSON Schema validation fixtures
│   ├── haex_hive/
│   │   ├── valid/
│   │   └── invalid/
│   ├── publisher_manifest/
│   ├── atom_manifest/
│   └── install_lock/
├── integration/                       # subprocess-invoked CLI end-to-end
│   ├── test_migrate.py                # US1 acceptance scenarios
│   ├── test_assemble_single_source.py # US2
│   ├── test_assemble_multi_source.py  # US3 (LLM path — see research)
│   └── test_show.py                   # US4
└── unit/                              # per-module unit tests
    ├── test_source_url.py             # D3 canonicalization
    ├── test_atom_id.py                # reverse-DNS grammar
    ├── test_version_constraint.py     # FR-006 grammar
    ├── test_json_deterministic.py     # FR-036 byte-identity
    ├── test_transaction.py            # FR-035 journal recovery and mixed-pair refusal
    ├── test_transform.py              # migration table rules
    └── test_resolve.py                # D11 two-step lookup

pyproject.toml                         # PyPI package metadata + console_scripts
README.md
```

**Structure Decision**: Single-project Python CLI. All source under `src/haex_hive/`, mirroring the domain vocabulary (schema, model, git, migrate, constitution, io, util). Test layout parallels: contract tests validate the JSON Schemas against fixtures; integration tests invoke the CLI via subprocess; unit tests exercise pure logic (grammars, canonicalization, deterministic serialization). This is the smallest structure that separates the CLI dispatch (`cli/`) from the domain (`model/`, `migrate/`, `constitution/`) and the boundary adapters (`git/`, `io/`, `schema/`). No frameworks; stdlib + `jsonschema` only.

## Complexity Tracking

*No violations — Constitution Check passed cleanly. This table intentionally left empty.*
