# CLI Contract: `haex constitution assemble`

**Spec**: [spec.md](../spec.md) §US2, §US3, FR-024–FR-031
**Data model**: [data-model.md](../data-model.md) §ConsumerManifest, §ConstitutionLockSection, §ConstitutionSource
**Design**: [Spec 007 design doc](../../../docs/plans/2026-08-28-spec-007-unified-manifest-design.md) §D2, §D11
**Research**: [research.md](../research.md) §R7 (LLM invocation abstraction)

## Synopsis

```console
haex constitution assemble [--llm=<method>] [--accept-merged <path>]
```

## Description

Canonicalize every `atoms[]` entry's source by D3 before any clone, publisher-manifest, atom-manifest, or contribution lookup; this normalizes permitted SCP/SSH transport forms and refuses credentials or non-canonical sources. Then resolve every included atom, identify manifests declaring `contributes.constitution`, load their contributed content at the pinned SHAs, and produce the effective `.haex-hive/constitution.md` file. Record its content-hash and source-attribution in `.haex-hive/install.lock`.

Three paths, selected mechanically by the number of resolved constitution sources:

- **No-source path** (zero resolved contributions): report `no constitution sources declared`, exit 2, and leave both output files exactly as they were. It does not create, delete, or replace an existing constitution or lock.

- **Single-source path** (exactly one resolved contribution): produce `.haex-hive/constitution.md` as a byte-for-byte copy of the source contribution file at the pinned SHA. No LLM invocation, always deterministic (FR-026, FR-031).
- **Multi-source path** (two or more resolved contributions): `stdio` invokes the operator-attached LLM and requires operator review, edit, and confirmation; `file` writes pending merge state and exits 5 without output changes until a later `--accept-merged`; `none` refuses (FR-027, FR-028). Every `stdio` result and accepted file candidate must pass the Principle-VIII concealment-instruction guard before publication.

In both successful paths, the same `.haex-hive/install.lock` write records provenance (FR-030): `constitution.sources[]` records every input atom as `{id, revision, source}`, `constitution.assembled_by` records the tool/version, and `constitution.content_integrity` records the D15 one-file-tree SHA-256 of the produced file.

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

Both writes use the journaled generation protocol in FR-035. Its sole journal path is `<repo-root>/.haex-hive/constitution-transaction.json`; for each target it records staged data, the target path, generation, digest, and its prior state (a backup path if it existed or an explicit `absent` marker if it did not). On startup, `assemble` recovers a live journal before resolving sources; recovery restores backups or removes targets created from an absent prior state. `haex constitution show` checks this same path and refuses instead of reading a mixed pair.

## Exit codes

| Code | Meaning | Notes |
|---|---|---|
| 0 | Success | |
| 2 | Resolution refuse — zero constitution sources or one or more atoms could not be resolved | For zero sources: `no constitution sources declared`; existing output files are untouched. Other cases include missing publisher manifest, missing atom manifest, absent `contributes.constitution`, schema violation, or collision. See FR-025. |
| 3 | I/O refuse — publisher clone unavailable OR pinned SHA not in clone OR contribution file not found at SHA | See spec Edge Cases. |
| 4 | Multi-source LLM refuse — `--llm=none` was resolved and multi-source is required | FR-028. `.haex-hive/constitution.md` and `.haex-hive/install.lock` untouched. |
| 5 | Pending merge state | Emitted only under `--llm=file` after writing `.haex-hive/constitution.merge.pending.json`. Operator/agent produces the merged output out-of-process; re-invocation with `--accept-merged` completes the transaction. `.haex-hive/constitution.md` and `.haex-hive/install.lock` untouched. |
| 6 | Post-write validation refuse — the produced `constitution.md` failed a post-write integrity check | Should not happen; indicates a bug. Both output files rolled back to their pre-command state. |
| 7 | System refuse — `.haex-hive.json` missing or version mismatch (FR-034) | |
| 8 | Constitution safety refuse — a multi-source candidate violates Principle VIII | `key=constitution-concealment-instruction`; candidate is not staged and both output files are untouched. |

## Two-phase file flow (`--llm=file`)

1. First invocation: `haex constitution assemble --llm=file` in a repo with a multi-source constitution set.
2. CLI writes `.haex-hive/constitution.merge.pending.json` containing: `sources[]` (each with atom-id, revision, source URL, and the raw contribution content), `task_prompt` (the natural-language instruction for the LLM), and a `pending_id` (opaque token for validation on --accept-merged).
3. CLI exits with code 5. `.haex-hive/constitution.md` and `.haex-hive/install.lock` are NOT written.
4. Operator (or agent) reads the pending file, produces the merged content, writes it to some path (default suggested: `.haex-hive/constitution.md.candidate`).
5. Operator re-invokes `haex constitution assemble --accept-merged .haex-hive/constitution.md.candidate`.
6. CLI validates: (a) the candidate file exists and is UTF-8, (b) the pending file's `pending_id` still matches (no source drift between phase-1 and phase-2), (c) all sources in the pending file are still resolvable at the same SHAs, and (d) `validate_no_concealment_instructions` accepts it. The last check rejects invisible or bidirectional control characters, hidden markup, and instructions to a downstream agent to conceal or withhold relevant information from the operator; it exits 8 without staging or publication.
7. CLI publishes `.haex-hive/constitution.md` (byte-identical to the candidate) and `.haex-hive/install.lock` through the FR-035 journaled generation protocol. `constitution.content_integrity` is the D15 one-file-tree digest of the candidate bytes.
8. CLI deletes `.haex-hive/constitution.merge.pending.json` after publication. It never deletes the caller-supplied candidate path.
9. Exit 0.

## Diagnostics

Every refuse diagnostic includes exit code, machine-parseable key, affected atom-id (if applicable), and a remediation hint. Multi-source `--llm=none` refuse example:

```text
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

- A durable journal at `.haex-hive/constitution-transaction.json` records every output generation before either target is replaced. On the next assemble invocation, recovery completes or restores the pair so both targets have one generation; read-only commands refuse rather than expose a mixed state (FR-035).
- Before either target replacement, staged files and pre-generation backups are fsynced; the journal records every recovery path and phase, including each target's prior existing-or-absent state, then is fsynced with its parent directory on POSIX. Windows uses write-through replacement and flushed handles. Integration tests interrupt after durable journal creation and after each replacement with both existing and absent initial targets.
- Startup recovery establishes the stable paired-output baseline. After that baseline is reached, refuse codes 2/3/4/6/7/8 do not modify `.haex-hive/constitution.md` or `.haex-hive/install.lock`; recovery itself may replace either target before a later refusal.
- On refuse code 5, `.haex-hive/constitution.merge.pending.json` is written atomically; the two output files are untouched.

## Not in scope

- `haex constitution assemble` does NOT invoke any network fetches. Publisher clones must exist locally.
- `haex constitution assemble` does NOT populate Spec-008's `install.lock.atoms[]` or `install.lock.generated_content_integrity`. Only the `constitution` section is Spec-007's responsibility.
- `haex constitution assemble` does NOT install a git pre-commit hook or invoke `haex verify`. Both are Spec 008 concerns.
