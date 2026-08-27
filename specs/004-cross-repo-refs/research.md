# Phase 0 Research: Cross-Repo References

**Date**: 2026-08-27
**Feature**: 004-cross-repo-refs
**Purpose**: Resolve any remaining unknowns from `plan.md`'s Technical
Context and document the load-bearing implementation decisions.

## Status

The design doc + `/speckit.clarify` session already resolved the
major open questions. This document captures the remaining
implementation-level decisions that emerge from filling in the plan:
tool-distribution shape, cache-directory hashing, exact Git-fetch
strategy, edge-case handling around fixture-driven testing, and the
one new ADR needed to record the schema/config unification.

## Decision 1 — Tool file layout and shebang

**Decision**: `spec-resolve` is a single Python file installed at
`.specify/scripts/spec-resolve` with `#!/usr/bin/env python3` shebang
and executable bit set. No separate `spec-resolve.py` + wrapper; no
Python package structure; no `__init__.py`.

**Rationale**:
- Matches spec-kit's own script convention (`.specify/scripts/bash/*.sh`,
  `.specify/scripts/bash/create-new-feature.sh`).
- Single-file scripts are easier to symlink onto `$PATH` for direct CLI
  use during Phase-2/3 work when consuming repos want a globally
  available `spec-resolve`.
- Python 3.10+ tolerates the `python3` shebang on Linux, macOS, and
  WSL2 without additional wrappers.
- A separate `spec-resolve.py` + shell wrapper adds two files, one
  hop of indirection, and buys nothing measurable for a ~300 LOC tool.

**Alternatives considered**:
- Python package under `.specify/tools/spec_resolve/` with a
  `pyproject.toml` — rejected as YAGNI. If Phase 2+ needs shared code
  between multiple tools, a package can be extracted then.
- Bash wrapper delegating to Python — rejected as unnecessary
  indirection when `#!/usr/bin/env python3` already handles the invocation.
- Compiled binary (Go/Rust) — already rejected during brainstorming
  (see design doc); Python's stdlib + Git-CLI is the right level here.

## Decision 2 — Cache directory hashing

**Decision**: The `<repo-hash>` component of
`~/.cache/haex-hive/repos/<repo-hash>/` is
`hashlib.sha256(repository_string.encode("utf-8")).hexdigest()[:16]`
— the first 16 hex characters (64 bits) of the SHA-256 of the
byte-identical `repository` string.

**Rationale**:
- Byte-identical input matches Q1's clarification (string-exact
  matching). Two URL variants of the same underlying repo → two
  different hashes → two cache dirs; acceptable per FR-014's clarified
  comment.
- SHA-256 is stdlib (`hashlib`). No third-party crypto.
- 64 bits (16 hex chars) is enough entropy to make collision between
  distinct URL strings essentially impossible in practice, while
  keeping the directory name readable/tab-completable.
- The full SHA is deterministic across devices, satisfying Principle
  III's device-independence spirit (two operators pointing at the same
  URL from the same repo hit the same cache dir on their respective
  machines).

**Alternatives considered**:
- Base64/URL-encoded direct filename — rejected as unwieldy and
  case-sensitive-filesystem-hostile.
- MD5 — same length as truncated SHA-256; no reason to prefer weaker.
- Full SHA-256 (64 hex chars) — visually cluttered directory listings
  for zero practical gain over 16 chars.

## Decision 3 — Git fetch strategy

**Decision**: `spec-resolve prefetch` and cache-miss paths in `resolve`
run:

```
git init --bare <cache-dir>                  # if new
git -C <cache-dir> fetch --depth=1 <repo-url> <sha>
```

If the server refuses `--depth=1` for a specific SHA (some servers
require full refspec), fall back to:

```
git -C <cache-dir> fetch <repo-url> <sha>
```

If that also fails (server won't accept SHA refspec directly), fall
back to:

```
git -C <cache-dir> fetch <repo-url>          # full fetch of default branch
```

Followed by presence-check via `git cat-file -e <sha>^{commit}` and,
if still absent, a final `git fetch <repo-url> '+refs/*:refs/*'` full
mirror fetch as last resort.

Content extraction is `git -C <cache-dir> show <sha>:<path>`.

**Rationale**:
- Depth-1 SHA-refspec fetch is the cheapest happy path and works
  against GitLab/GitHub servers with modern protocol v2 support.
- The fallback ladder mirrors what tools like `go mod download` do
  under similar constraints — practical experience shows most
  self-hosted GitLab instances need at least the tier-3 fallback.
- Bare directories avoid an extra worktree and remain safe to `rm -rf`.

**Alternatives considered**:
- `git archive --remote=<url>` — rejected: many self-hosted GitLab
  instances disable `upload-archive`, and the tool would fail silently
  on those.
- `git clone --filter=blob:none` (partial clone) — attractive but
  requires the server to advertise `filter` capability; not universal
  enough for a Phase-1 tool. The bare-fetch approach avoids that
  dependency.
- Full clone up-front — rejected: expensive for large external repos
  (secana-specs will be a candidate), overkill when only one SHA/path
  pair is consumed per session.

## Decision 4 — SHA-hex canonicalization on input

**Decision**: When validating `revision` values, the resolver lower-cases
the input before applying the `^[0-9a-f]{7,40}$` regex — so
`"REVISION": "406FC78..."` and `"revision": "406fc78..."` are treated
as the same value. But the schema's regex is `^[0-9a-f]{7,40}$`
(lowercase only) — so mixed-case revisions are rejected by the schema,
and the resolver's normalizing behavior is a **defense-in-depth** for
config files hand-edited without schema help.

**Rationale**:
- Git itself accepts mixed-case SHA on the CLI. Rejecting mixed-case
  in the schema (strict) while normalizing in the tool (lenient)
  gives the operator a clear "your config is technically valid but
  the schema will warn you" middle path.
- No user-visible ambiguity — the SHA points at the same commit
  regardless of case.

**Alternatives considered**:
- Case-insensitive regex in the schema — rejected as inconsistent
  with `Git`'s own docs (uses lowercase everywhere).
- Strict lowercase in the tool too — would refuse a valid Git ref
  and surprise the operator.

## Decision 5 — URL scheme validation

**Decision**: The resolver's URL-scheme check (per Q3 clarification)
applies these rules to any `repository` value that is not the literal
string `"self"`:

- Accept if matches `^https://` (any host).
- Accept if matches `^ssh://` (any user, any host, any port).
- Accept if matches SCP-style pattern `^[^/@:\s]+@[^/@:\s]+:.+$`
  (user@host:path) — no scheme prefix, but a required `@` and `:`
  separating segments.
- Reject everything else, including:
  - `^file://`
  - `^git://` (unencrypted Git protocol)
  - `^http://` (unencrypted HTTP)
  - Bare paths (`/absolute/path`, `./relative`, `../parent`, plain names)
  - Any URL missing `://` that doesn't match the SCP pattern.

**Rationale**:
- Q3's answer explicitly listed `https://`, `ssh://`, and SCP-style.
- Adding `http://` to the reject list was implicit but making it
  explicit prevents accidental degradation to unencrypted transport
  (defense against a downgrade attack on the allowlist).
- The SCP-pattern regex is intentionally strict (no whitespace, single
  `@`, single `:` before path) to avoid matching accidents like
  `nothing@`.

**Alternatives considered**:
- Relaxed SCP pattern — rejected: too easy to mis-parse; better to
  refuse ambiguous input than accept it silently.
- No `http://` in the reject list (treated as "unmatched, therefore
  reject") — same outcome, but explicit reject with a specific message
  is friendlier to the operator.

## Decision 6 — Fixture-driven testing setup

**Decision**: Test fixtures are built at test-runtime by
`tests/spec-resolve/fixtures/build-fixtures.sh` using `git init` +
`git commit` in ephemeral directories, produced fresh each run and
cleaned up on teardown. Fixture repos are NOT committed to
`haex-hive` itself.

**Rationale**:
- Committing fixture repos would bloat the parent repo's history
  and require awkward path handling (submodules? subtrees?).
- Building fixtures fresh guarantees they always match the tests'
  expectations; no drift between fixture content and test scripts.
- Deterministic fixture-building requires deterministic committer
  identity and dates; `build-fixtures.sh` sets
  `GIT_AUTHOR_DATE`, `GIT_COMMITTER_DATE`,
  `GIT_AUTHOR_NAME`, and `GIT_COMMITTER_EMAIL` explicitly so SHAs
  are reproducible run-to-run.

**Alternatives considered**:
- Committed fixture directories with pre-computed SHAs — rejected
  as brittle (any minor rebuild changes the SHA).
- Git submodules pointing at synthetic fixture repos — over-engineered
  for ~5 small fixtures.

## Decision 7 — New ADR to record the shape unification

**Decision**: A new ADR `docs/adr/0005-unify-harness-sources-and-drop-system-yaml.md`
records:
- The rename `external_sources` → `harness_sources`.
- The collapse of the split `constitution` slot + `external_sources.allowed`
  into one unified array.
- The removal of `.specify/system.yaml`.
- The rationale: single source of truth per repo, role-tagged entries
  make the constitution ref just one entry-shape, and the JSON Schema
  becomes the canonical vocabulary.

**Rationale**:
- Constitution's Governance section requires an ADR + amendment for
  wording changes that touch a principle's citation.
- Principle V's wording change (citing `.haex-hive.json` instead of
  `.specify/system.yaml`) is a PATCH-level change per the version-bump
  rules, but still deserves ADR documentation for traceability.
- Future readers grepping for "external_sources" or "system.yaml"
  should find this ADR as the pointer explaining the rename.

**Alternatives considered**:
- Amending ADR 0002 in place (which introduced the `system.yaml`
  concept) — rejected: ADRs are append-only history; new decisions
  get new ADRs, superseding is documented, not overwritten.

## Decision 8 — Snippet extension mechanism

**Decision**: The Spec 003 global instruction snippet gains one new
step (Step 8) that calls `spec-resolve status`. The snippet is
delivered per-operator (per Spec 003), so the update is documented
in `docs/spec-resolve.md` under a "Snippet extension" section;
operators who installed the older snippet copy-paste-replace Step 8
into their user-level config. No committed snippet file exists in
this repo to auto-update.

**Rationale**:
- Spec 003 established that the snippet lives in each operator's
  private CLI config (Claude's `CLAUDE.md`, Codex's `AGENTS.md`),
  not in the repo. Spec 004 respects that boundary — we can't
  auto-update someone else's private config.
- The `docs/spec-resolve.md` file becomes the canonical source of
  the snippet's current text, so any operator opening the doc sees
  the latest version.

**Alternatives considered**:
- Auto-generating/committing the snippet in the repo — rejected: would
  re-introduce the Spec 003 anti-pattern (repo commandeering operator's
  personal config).
- Providing an `install-snippet` subcommand on `spec-resolve` that
  edits the operator's config file — rejected as intrusive and error-
  prone (which operator config? which CLI? multiple installs?).

## Open items (deferred, not blocking Spec 004)

- **Cache eviction policy** — deferred to when the cache actually
  grows enough to matter. Design-doc notes cover this.
- **Structured JSON output mode for `spec-resolve`** — potentially
  useful for Phase 2 compiler consumers; not needed by Phase 1's
  snippet integration. Deferred.
- **Non-Linux validation** — deferred per spec Assumptions.
- **Nix flake wrapper** — deferred to Phase 3.

## Summary

All Technical Context fields in `plan.md` are resolved. No NEEDS
CLARIFICATION remains. The tool's implementation shape is well-defined
enough to move to Phase 1 design artifacts.
