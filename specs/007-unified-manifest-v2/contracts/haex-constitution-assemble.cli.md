# CLI Contract: `haex constitution assemble`

**Spec**: [spec.md](../spec.md) §US2, §US3, FR-024–FR-031
**Data model**: [data-model.md](../data-model.md) §ConsumerManifest, §ConstitutionLockSection, §ConstitutionSource
**Design**: [Spec 007 design doc](../../../docs/plans/2026-08-28-spec-007-unified-manifest-design.md) §D2, §D11
**Research**: [research.md](../research.md) §R7 (LLM invocation abstraction)

## Synopsis

```
haex constitution assemble [--llm=<method>] [--accept-merged <path>]
```

## Description

Resolve every `atoms[]` entry in `.haex-hive.json`, identify the atoms whose manifest declares `contributes.constitution`, load their contributed constitution content at the pinned SHAs, and produce the effective `.haex-hive/constitution.md` file. Record its content-hash and source-attribution in `.haex-hive/install.lock`.

Two paths, selected mechanically by the number of resolved constitution sources:

- **Single-source path** (exactly one resolved contribution): produce `.haex-hive/constitution.md` as a byte-for-byte copy of the source contribution file at the pinned SHA. No LLM invocation, always deterministic (FR-026, FR-031).
- **Multi-source path** (two or more resolved contributions): invoke the operator-attached LLM via the selected `--llm` method to merge the sources into a single reconciled `.haex-hive/constitution.md`. On a device where no LLM method succeeds, the command refuses (FR-027, FR-028).

In both paths, the same `.haex-hive/install.lock` write records provenance (FR-030): `constitution.sources[]` names every input atom, `constitution.content_integrity` records the SHA-256 of the produced file.

## Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--llm` | one of `stdio`, `file`, `none` | Auto-detect (see below) | Selects the merge-LLM method for the multi-source path. Ignored in the single-source path. See R7 for method descriptions. |
| `--accept-merged` | path | (none) | Two-phase completion for the `--llm=file` method. Reads the merged constitution content from the given path, validates against the pending state recorded in `.haex-hive/constitution.merge.pending.json`, and commits the assembled output. See "Two-phase file flow" below. |

`--llm` precedence (highest → lowest): explicit `--llm=<method>` flag → `HAEX_LLM=<method>` env var → auto-detect. Auto-detect chooses `stdio` if stdin is a TTY, otherwise `none`.

## Inputs

- **File on disk**: `<repo-root>/.haex-hive.json` v2 (FR-034 refuses non-v2 files at CLI startup). MUST exist.
- **Publisher clones on disk**: for each `source` in the resolved constitution atoms, a git clone containing the pinned revision at `$HAEX_HIVE_STATE/repos/<clone-hash>/`.
- **Publisher manifests at pinned SHAs**: read via `git show <sha>:manifest.json`. Must be well-formed against `publisher-manifest.v2.schema.json`.
- **Atom manifests at pinned SHAs**: read via `git show <sha>:<publisher_atom_entry.path>/manifest.json`. Must be well-formed against `atom-manifest.v2.schema.json` and declare `contributes.constitution`.
- **Constitution contribution files at pinned SHAs**: read via `git show <sha>:<publisher_atom_entry.path>/<atom_manifest.contributes.constitution>`. Must be regular files.
- **LLM access** (multi-source only): per the selected `--llm` method. Missing access refuses per FR-028.

## Outputs

Success creates or replaces two files atomically:

- `<repo-root>/.haex-hive/constitution.md` — the effective constitution content. In single-source: byte-identical to the source file at the pinned SHA. In multi-source: LLM-merged content, no prepended header (FR-029).
- `<repo-root>/.haex-hive/install.lock` — populated with the `constitution` section per data-model.md §ConstitutionLockSection. Existing top-level fields not owned by Spec 007 (e.g., future Spec-008 `atoms[]`) MUST be preserved (FR-030 forward-compat).

Both writes go through the atomic-replace pattern (R6). Either both files land or neither does (FR-035).

## Exit codes

| Code | Meaning | Notes |
|---|---|---|
| 0 | Success | |
| 2 | Resolution refuse — one or more atoms could not be resolved | Missing publisher manifest, missing atom manifest, atom-manifest doesn't declare `contributes.constitution`, publisher/atom manifest schema violation, atom-ID collision across sources (D3 uniqueness). See FR-025. |
| 3 | I/O refuse — publisher clone unavailable OR pinned SHA not in clone OR contribution file not found at SHA | See spec Edge Cases. |
| 4 | Multi-source LLM refuse — `--llm=none` was resolved and multi-source is required | FR-028. `.haex-hive/constitution.md` and `.haex-hive/install.lock` untouched. |
| 5 | Pending merge state | Emitted only under `--llm=file` after writing `.haex-hive/constitution.merge.pending.json`. Operator/agent produces the merged output out-of-process; re-invocation with `--accept-merged` completes the transaction. `.haex-hive/constitution.md` and `.haex-hive/install.lock` untouched. |
| 6 | Post-write validation refuse — the produced `constitution.md` failed a post-write integrity check | Should not happen; indicates a bug. Both output files rolled back to their pre-command state. |
| 7 | System refuse — `.haex-hive.json` missing or version mismatch (FR-034) | |

## Two-phase file flow (`--llm=file`)

1. First invocation: `haex constitution assemble --llm=file` in a repo with a multi-source constitution set.
2. CLI writes `.haex-hive/constitution.merge.pending.json` containing: `sources[]` (each with atom-id, revision, source URL, and the raw contribution content), `task_prompt` (the natural-language instruction for the LLM), and a `pending_id` (opaque token for validation on --accept-merged).
3. CLI exits with code 5. `.haex-hive/constitution.md` and `.haex-hive/install.lock` are NOT written.
4. Operator (or agent) reads the pending file, produces the merged content, writes it to some path (default suggested: `.haex-hive/constitution.md.candidate`).
5. Operator re-invokes `haex constitution assemble --accept-merged .haex-hive/constitution.md.candidate`.
6. CLI validates: (a) the candidate file exists and is UTF-8, (b) the pending file's `pending_id` still matches (no source drift between phase-1 and phase-2), (c) all sources in the pending file are still resolvable at the same SHAs.
7. CLI writes `.haex-hive/constitution.md` (byte-identical to the candidate) and `.haex-hive/install.lock` (with `constitution.content_integrity` = SHA-256 of the candidate bytes).
8. CLI deletes `.haex-hive/constitution.merge.pending.json` and (optionally) the candidate file.
9. Exit 0.

## Diagnostics

Every refuse diagnostic includes exit code, machine-parseable key, affected atom-id (if applicable), and a remediation hint. Multi-source `--llm=none` refuse example:

```
error: exit=4 key=llm-required-for-multi-source
  resolved 3 constitution atoms:
    - com.github.haexmas.haex-hive.constitution @ b2f884...
    - com.github.itemis.company-overlay.constitution @ abc123...
    - com.github.example.legal-overlay.constitution @ def456...
  hint: Run on a device with LLM access, or pass --llm=file to use the two-phase completion flow.
```

## Determinism guarantees

- Single-source path: two invocations against the same input produce byte-identical `.haex-hive/constitution.md` AND byte-identical `.haex-hive/install.lock` (FR-031, FR-036).
- Multi-source path: the produced files are deterministic given the LLM's output. Byte-identity of the LLM output is NOT guaranteed by this command; determinism is achieved by committing the result and having other devices verify against `install.lock.constitution.content_integrity` (FR-030).

## Filesystem-atomicity guarantees

- Both output files land together, or neither does. Any partial state is cleaned up before the command exits, regardless of exit code (FR-035).
- On refuse codes 2/3/4/6/7, neither `.haex-hive/constitution.md` nor `.haex-hive/install.lock` is modified from its pre-command state.
- On refuse code 5, `.haex-hive/constitution.merge.pending.json` is written atomically; the two output files are untouched.

## Not in scope

- `haex constitution assemble` does NOT invoke any network fetches. Publisher clones must exist locally.
- `haex constitution assemble` does NOT populate Spec-008's `install.lock.atoms[]` or `install.lock.generated_content_integrity`. Only the `constitution` section is Spec-007's responsibility.
- `haex constitution assemble` does NOT install a git pre-commit hook or invoke `haex verify`. Both are Spec 008 concerns.
