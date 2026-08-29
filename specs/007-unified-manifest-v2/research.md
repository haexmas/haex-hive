# Research: Unified Manifest v2 + Migration + Constitution Assemble

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-29

This document captures the Phase 0 research decisions. Each entry names one open question from the Technical Context, the resolution, the rationale, and the alternatives considered. All decisions here are load-bearing for the Phase 1 contract design and the Spec 008/009 handoffs.

## R1. JSON Schema validator library

**Decision**: `jsonschema>=4.18` from PyPI.

**Rationale**: Draft 2020-12 requires a validator that implements the 2020-12 dialect (with `$dynamicRef`, revised `unevaluatedProperties`, etc.). The `jsonschema` library's 4.18.0 release (2023) is the first with a stable, tested Draft 2020-12 validator; all subsequent 4.x releases maintain compatibility. It is pure-Python, has no C extensions, and installs cleanly on Linux/macOS/Windows without a compile step. It is battle-tested in the Python ecosystem (used by AWS, Ansible, OpenAPI tooling, etc.), which reduces the risk of validator bugs producing false diagnostics that would look like our bug.

**Alternatives considered**:

- **`fastjsonschema`** — faster, but its Draft 2020-12 support is incomplete (as of 2.19.x, `$dynamicRef` and `unevaluatedProperties` are known-broken). Trades correctness for speed we don't need at CLI startup.
- **`python-jsonschema-rs`** (Rust-backed via PyO3) — very fast, but adds a compiled dependency that breaks the "pip install pure-Python" story. Rules out easy on-Windows deployment where the operator has no C toolchain.
- **Hand-rolled validator** — too much surface for too little payoff; the tests would be validating our validator, not our schemas.

## R2. Deterministic JSON serialization

**Decision**: stdlib `json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)` followed by an explicit trailing `\n` and LF-only newlines. Wrap in `haex_hive.io.json_deterministic.dumps()` so every call-site goes through the same helper.

**Rationale**: FR-036 requires byte-identical output on identical inputs. `sort_keys=True` handles key-order determinism. `indent=2` produces canonical 2-space indent. `ensure_ascii=False` allows UTF-8 output for identity strings (reverse-DNS is ASCII, but adjacent free-text fields like `identity_note` may carry Unicode). The trailing `\n` is a POSIX-file-convention that most editors preserve; explicit append means we don't rely on `json.dumps`'s (absent) trailing newline. LF-only means we never write CRLF even on Windows — Python's `open(..., "w", newline="")` combined with writing bytes-with-`\n` guarantees this.

**Alternatives considered**:

- **`orjson`** — faster and has a `sort_keys` mode, but produces bytes not str; adds an external C-backed dependency. Determinism is stdlib-json's baseline; speed is not a bottleneck.
- **`rapidjson`** — similar tradeoff; rejected for the same reason.
- **Hand-rolled canonicalizer** — RFC 8785 (JCS) is stricter (numeric normalization, escape-sequence normalization). We don't need RFC 8785; our determinism target is "same inputs → same bytes on this system", which stdlib json already gives us when driven from stable Python data structures.

## R3. Git operations

**Decision**: `git` invoked via `subprocess.run(...)` from the stdlib. No `pygit2`, no `GitPython`.

**Rationale**: Spec 007 uses git for exactly three read operations:

1. `git remote get-url origin` (in the consumer repo, during migration to resolve `self`).
2. `git rev-parse <maybe-short-sha>^{commit}` (to expand a v1 7-39-char SHA to the full 40-char SHA).
3. `git show <sha>:<repo-relative-path>` (to read publisher-side content at pinned SHAs).

All three are one-shot reads, execute in <200ms, and require no long-lived state. `subprocess.run` with `check=True`, `capture_output=True`, `text=False` (bytes) is enough. The result carries a well-defined exit code; parsing is straightforward. Direct `subprocess` calls also avoid a whole class of "which libgit2 version" packaging pain on Windows — the operator already has `git` on PATH (Assumption in spec.md).

**Alternatives considered**:

- **`pygit2`** — libgit2 bindings; adds a compiled dependency; on Windows the wheel history has been intermittent (some Python-3.13 wheels missing at times). Overkill for three reads.
- **`GitPython`** — pure-Python wrapper over subprocess `git`. Adds a dependency that itself just shells out — no value over raw `subprocess`, plus slower cold-start.
- **`dulwich`** — pure-Python git implementation; interesting for offline-only worlds, but our reads want the exact bytes `git show` produces (which handles LFS, `.gitattributes`, filters). Diverging semantics would surprise the operator.

## R4. Unified-diff generation

**Decision**: stdlib `difflib.unified_diff` for the `haex migrate` stdout diff (FR-017).

**Rationale**: The diff produced by `unified_diff` is standard `patch`-format. It is human-readable, tool-parseable, and requires zero external dependencies. Line-based diffing is the right resolution for JSON-shaped files (they're one JSON object per file); character-level diffing would produce visual noise for whitespace-only differences that come from deterministic re-formatting.

**Alternatives considered**:

- **`diff-match-patch`** — character-level diffing; wrong resolution.
- **`jsonpatch`** (RFC 6902) — semantic-JSON operations; useful for machine-consumable patches but harder for humans to read at a glance. Migration reviews are human-review-first.
- **External `diff -u`** — subprocess call to system `diff`; adds a runtime PATH dependency and produces the same output. Stay in-process.

## R5. CLI framework

**Decision**: stdlib `argparse` with `add_subparsers()` tree. Root parser at `haex`, subparsers at `migrate`, `constitution`, and (nested) `constitution assemble` / `constitution show`.

**Rationale**: Spec 007 defines four verbs in a tree with a max depth of 2 (`haex constitution assemble`). `argparse` handles this natively via nested subparsers. Stdlib means zero dependency, deterministic help output, and standard behavior on all three platforms. Type coercion needs are trivial (paths, boolean flags, no complex validators). The rest of the design (Spec 008/009/010) will add more verbs — but `argparse`'s subparser tree scales cleanly and there is no known feature ceiling relevant to `haex`.

**Alternatives considered**:

- **`click`** — friendlier decorator-based syntax; adds a dependency and a rich context object. We don't need context — subcommands share nothing but the project root, which is discovered fresh in each invocation. Not enough payoff.
- **`typer`** — pretty terminal output; more magic. Rejected for the same reason as click, plus type-annotation-driven parsers can obscure exactly-which-flags semantics that this spec's tests need to pin.

## R6. Atomic file publication on Windows

**Decision**: `haex_hive.io.atomic.write_replace(target: Path, data: bytes)` — writes to `target.parent / f".{target.name}.tmp"` (or a `mkstemp` in the same directory for the migration sidecar), fsyncs the file, then calls `os.replace(tmp, target)`, then fsyncs the parent directory (POSIX only — Windows silently ignores directory fsync).

**Rationale**: `os.replace` is Python's cross-platform wrapper: on POSIX it is `rename(2)` (atomic within a filesystem); on Windows it uses `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`, which is atomic within an NTFS volume. Same-directory constraint guarantees "same filesystem" on both. The tmp-file name pattern uses a leading `.` so partial writes are less visible to editors watching the directory. Directory fsync on POSIX ensures the metadata entry survives a power loss; Windows doesn't expose a direct equivalent, but `MoveFileEx` with a completing flush satisfies the operator's durability expectations. This is the pattern used by SQLite, dpkg, and Postgres for the same problem.

**Alternatives considered**:

- **Write-in-place** — non-atomic; a crash mid-write leaves a truncated file. FR-035 forbids this.
- **`tempfile.NamedTemporaryFile(dir=target.parent)` + rename** — same guarantee, but the `NamedTemporaryFile` context manager `close()`s and deletes the file on error, which conflicts with the intent of leaving the tmp file in place on failure (we then explicitly unlink it in an error handler). Wrapping in a try/finally with manual unlink is what we do anyway; use `mkstemp` directly.
- **`fcntl.flock` + write-in-place** — locking prevents concurrent writers but not partial writes; still not atomic on crash.

## R7. LLM invocation abstraction for multi-source `haex constitution assemble`

**Decision**: Deferred to Spec 007's implementation phase as a **plugin-style boundary interface**, not resolved here. The Spec 007 CLI defines an internal `haex_hive.constitution.llm.MergeLLM` protocol (single method: `merge(sources: list[ConstitutionSource], task_prompt: str) -> str`) with three registered implementations selected at command-time via a `--llm=<method>` flag or the `HAEX_LLM` environment variable (in the design's order of precedence: `--llm` > env > auto-detect):

- **`stdio`**: prints the sources plus a natural-language prompt to stdout and reads the merged result from stdin (terminates on EOF). Works in any TTY-attached shell where the operator (human or agent-in-the-loop) can shuttle text. The default for `--llm=stdio` and the default when `HAEX_LLM=stdio`.
- **`file`**: writes a "merge-pending" JSON file to `.haex-hive/constitution.merge.pending.json` with sources + prompt, exits with a distinct exit code (defined in Phase 1 contracts); the operator/agent produces the merged result out-of-process and re-invokes `haex constitution assemble --accept-merged <path>` to commit. Testable in isolation; agent-runtime-agnostic.
- **`none`**: refuses immediately in the multi-source case with the FR-028 diagnostic. Selected explicitly by the operator (or auto-detected in a non-TTY, non-file environment) to fail fast.

Multi-source without any `--llm`/`HAEX_LLM`/attached-TTY → default to `none` (fails fast, matches FR-028 semantic).

**Rationale**: The clarification round (Q3 of speckit-clarify was deferred here at plan-phase) established the semantic — a multi-source merge either succeeds via some in-loop LLM invocation, or refuses fast. The three-implementation abstraction covers every real interaction pattern without embedding a specific agent-runtime protocol into Spec 007's binary. `stdio` handles the common case (human in front of a terminal); `file` handles the agent-mediated case (agent invokes haex, gets a pending file, produces the merged output, re-invokes to commit); `none` is the honest refusal path for CI and for devices that pull-and-verify only. Later specs can add adapters (native MCP calls, Claude Code API, etc.) without breaking the internal protocol.

**Alternatives considered**:

- **Auto-detect via env vars** (`CLAUDE_CODE_SESSION_ID` and similar) — fragile heuristic that ties us to specific agent-runtime naming. Rejected as spec-external state.
- **Refuse for multi-source, always** — usable but forces every consumer to pre-assemble on some blessed device. Too restrictive.
- **Two-phase mandatory** — force everyone into the file-based `--accept-merged` flow even for TTY users. Worse DX.

## R8. Reverse-DNS atom-ID grammar validation

**Decision**: Regex `^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$` compiled once at module import. Length cap 253 characters (same as DNS max), individual-segment cap 63 characters. Reject empty and 254+ character strings before applying the regex to short-circuit.

**Rationale**: The regex matches D3 exactly (at least two segments joined by dots, each segment starting with `[a-z0-9]` and continuing with `[a-z0-9-]`). DNS length caps are the natural reference point since we borrow the naming convention. Length pre-check keeps regex engine work bounded even against pathological inputs.

**Alternatives considered**:

- **Uppercase allowed** — reverse-DNS convention in some ecosystems (Java packages) permits mixed case, but `.haex-hive.json`'s ID surface is committed to git across case-sensitive/case-insensitive filesystems (D15's case-fold rule). Lowercase-only prevents an entire class of macOS-versus-Linux collisions.
- **Underscores allowed** — D3 forbids underscores; consistency with the design doc.
- **JSON Schema `pattern` alone** — pattern-only lacks the length pre-check; combining regex+length in Python gives cleaner error messages ("id is 260 chars; max 253" vs. "did not match pattern"), improving operator diagnostics.

## R9. Canonical source URL normalization

**Decision**: Implement `haex_hive.model.source_url.canonicalize(url: str) -> str` following D3 exactly: (1) lowercase the scheme and host, (2) strip trailing `/` from the path, (3) strip a single terminal `.git`, (4) reject any URL that carries userinfo (`user[:token]@host`), (5) reject any scheme not in `{"https", "ssh", "git"}`. Use stdlib `urllib.parse.urlsplit` for parsing.

**Rationale**: `urlsplit` handles the three schemes we accept without doing anything surprising. The rejection rules land as raised `ValueError` subclasses (`CredentialInUrlError`, `UnsupportedSchemeError`) that the CLI catches and formats into the operator-facing diagnostic. Applying every rule at every entry point (`haex migrate`, `haex constitution assemble`, future `haex add`) ensures uniform behavior — publisher URLs never round-trip as-typed through the manifest.

**Alternatives considered**:

- **Accept userinfo** — Spec 007 explicitly rejects credential-URL storage in committed files (design D3). Non-negotiable.
- **`furl` library** — dependency-only value: a fluent URL builder. We don't need building, just parse-and-normalize.

## R10. Version constraint grammar

**Decision**: Implement `haex_hive.model.version_constraint.VersionConstraint.parse(s: str) -> VersionConstraint` where `VersionConstraint` is a small dataclass with `operator: Literal["==", ">="]` and `version: tuple[int, int, int]`. Grammar per FR-006: match against `^(?:>=)?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$` (leading-zero rejection is explicit in the character class). Reject everything else with a diagnostic that quotes the input and lists both accepted forms.

**Rationale**: FR-006's grammar (Q3 clarification) is exactly two forms. A hand-rolled regex + parser is <30 lines of code. Uses no third-party version library (which would drag in either PEP-440 semantics or npm-semver semantics — both wider than we accept). At-startup version check compares tuples with `<=`/`==`, no special-case logic.

**Alternatives considered**:

- **`packaging.version.SpecifierSet` (PEP 440)** — full PEP 440 range grammar. Not what we want; rejects our simpler surface as "unsupported" and imports a wider dependency.
- **`semver` package** — npm-flavored ranges; even wider surface than we need.

## R11. SHA-256 canonical serialization for `install.lock`'s `content_integrity`

**Decision**: `install.lock`'s `constitution.content_integrity` value is the string `"sha256-" + base64.b64encode(hashlib.sha256(constitution_bytes).digest()).decode("ascii")`. Base64 uses standard alphabet with `=` padding. This matches the design doc D15 canonical serialization format (already fixed for Spec 008; Spec 007 uses only the constitution-file case, which is a one-file tree per D15).

**Rationale**: Consistent format with Spec 008's install-transaction contract; forward-compatible when Spec 008 extends `install.lock` with `atoms[].content_integrity` and `generated_content_integrity`. Standard alphabet is universally decodable; padding is preserved (Python's `b64encode` includes it). The `sha256-` prefix is the same subresource-integrity format the wider Web ecosystem uses, making the value copy-paste-verifiable via off-the-shelf tools.

**Alternatives considered**:

- **Hex-encoded SHA-256** — 64 chars vs. 44 for base64; wastes space. Design doc's canonical format is base64, so hex would drift from Spec 008.
- **SHA-512** — no meaningful additional collision resistance for the file size we hash; SHA-256 is standard and 32 bytes vs. 64 in the encoded value.

## R12. Migration self-migration approach for haex-hive

**Decision**: The v2 file that `haex migrate` produces for haex-hive itself is generated by the same code path that any external consumer would exercise. The migration commits do not embed hand-written v2 content; instead, the migration is run once during Spec-007 implementation, the sidecar is reviewed, and the result becomes the committed `.haex-hive.json`. The commit that lands v2 also introduces the root and atom `manifest.json` files (FR-021, FR-022) at the SAME `revision` SHA the migrated `.haex-hive.json` pins, so that after landing, the consumer's own pin resolves against its own committed publisher manifest at the same commit.

**Rationale**: This is what US1 exists to prove — the migration table produces the correct v2 output for haex-hive's own real v1 file. Using the same code path (rather than authoring the v2 file by hand) guarantees the FR-021–FR-023 outputs are exactly what any external consumer would receive on their first `haex migrate` run. It also gives the Spec-007 conformance suite a real fixture: this repo's v1 file at commit `<pre-landing-sha>` MUST migrate to the committed v2 file at commit `<landing-sha>` byte-for-byte on every future run.

**Alternatives considered**:

- **Hand-author the v2 file** — faster to write, but decouples the file from the migration code; a bug in the migration would land unnoticed against this reference case.
- **Migrate at CI time only** — leaves the repo in a self-inconsistent state (committed file predates its own migration).

## Deferred / open technical questions

- **Publisher-clone prep for Spec 007 tests** — Spec 007's `haex constitution assemble` reads publisher content via `git show <sha>:<path>`. In tests, this requires a publisher repo present under `$HAEX_HIVE_STATE/repos/<clone-hash>/`. Spec 008 will land `haex add` which handles the clone; for Spec 007 tests, we prepare fixtures manually via `git clone --bare` in test setup. This is a test-fixture concern, not a runtime one.
- **Windows CI environment for cross-platform tests** — Spec 007 targets three OSes. CI matrix (github-actions) needs Linux + macOS + Windows runners. Setup is trivial (matrix strategy) but the concrete `.github/workflows/` config lives with the Spec 007 implementation task, not this research doc.
- **Constitution v1.3.0 in this repo's `.specify/memory/constitution.md`** — the current file predates the manifest-atom `manifest.json` (FR-022) that Spec 007 lands. Landing FR-022 adds `manifest.json` alongside `constitution.md` under `.specify/memory/`; this is a documentation change to that directory, not a change to the constitution text.
