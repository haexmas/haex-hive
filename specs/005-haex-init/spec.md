# Feature Specification: `haex-init` — CLI-Driven Project Initialization

> **Superseded by Spec 007 CLI surface (2026-08-29).** Per ADR 0008,
> the standalone `haex-init` binary retires in favour of `haex init` as
> a subcommand of the unified `haex` binary introduced by
> [Spec 007](../../docs/plans/2026-08-28-spec-007-unified-manifest-design.md).
> This spec remains the authoritative documentation for the shipped v1
> `haex-init` implementation (`.specify/scripts/haex-init`); v2
> initialization is chartered by Spec 007, not by editing this file.
> See [ADR 0008](../../docs/adr/0008-retire-haex-init-binary-for-haex-init-subcommand.md).

**Feature Branch**: `005-haex-init`
**Created**: 2026-08-27
**Status**: Draft
**Input**: Distilled from brainstorming session covering command surface,
operator-level setup, self-ref vs external-ref project modes, idempotency,
and testing strategy. Sits atop Spec 004 (`spec-resolve` + unified
`harness_sources` config shape).

## Clarifications

### Session 2026-08-27

- Q: How does the marker block's `v=<version>` attribute bump — every
  `haex-init` release, only on canonical instructions content changes,
  or via automated content hash?
  → A: Human-readable semver in the marker; bumps ONLY when the
  canonical session-instructions content changes. Tool-code-only
  releases (refactors, bug fixes, added tests) do not bump. A CI sync
  test additionally couples an `INSTRUCTIONS_SHA256` constant to the
  version so content drift without an explicit bump fails the test —
  mechanically preventing the "forgot to bump" failure mode while
  keeping the operator-visible version human-readable.
- Q: What is the content of the self-ref constitution stub that
  `haex-init` writes at init time?
  → A: `haex-init` writes NO placeholder constitution file in self-ref
  mode. Instead, it creates `.haex-hive.json` with `harness_sources: []`
  (empty — constitutionally-consistent per Principle V's "opted in
  with no permissions" state), commits scaffolding once, and prints
  explicit next-step guidance: run `/speckit-constitution` to define
  the constitution, then `haex-init --pin-constitution` to add and
  pin the `role: constitution` entry in `.haex-hive.json`. This
  eliminates the placeholder file that could be misread as
  authoritative content, decouples mechanical scaffolding from
  intellectual constitution-authoring, and simplifies the commit
  sequence (single scaffolding commit instead of the T005/T009-style
  two-commit dance).
- Q: In external-ref mode, does `haex-init` handle multi-spec
  referencing (constitution + `specs/**` from a shared repo like
  secana-specs) or only the constitution reference?
  → A: Phase 1 (Spec 005) — constitution reference ONLY. The full
  "consumer of a shared multi-spec repo" pattern (permission-only
  `harness_sources` entries for `specs/**` paths + convention for
  which features apply to which consumer + spec-ref.json scaffolding)
  is deferred to Spec 006 to keep Spec 005 shippable. This matches
  the real-world adoption sequence: haex-init first lands to bootstrap
  the central spec repo itself in self-ref mode; consumer-repo setup
  follows once operators have hands-on experience with the mechanism.
- Q: What is `haex-init`'s behaviour when the operator has hand-edited
  content INSIDE an existing marker block?
  → A: The marker-wrapped block is `haex-init`'s auto-managed
  territory; operator content that must be preserved belongs OUTSIDE
  the markers (before or after the block). There is no legitimate
  reason for operator hand-edits inside the block. When `haex-init`
  updates a version-mismatched block, hand-edits inside appear as
  removals in the diff-preview mandated by FR-009; the operator
  can decline the update (block stays as-is with edits, but also
  keeps the older version) or confirm (edits lost, block updated).
  No separate "hand-edits detected, refuse-to-touch" mode.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fresh operator adopts haex-hive in a new project (Priority: P1) 🎯 MVP

A team member with a brand-new project directory and no prior haex-hive
setup on their machine wants their project to be haex-hive-managed. They
download a single file (`haex-init`), run it inside their project, answer
a handful of interactive prompts, and end up with a fully functional
haex-hive-managed project — `.haex-hive.json` in place and schema-valid,
constitution referenced, agent tools (Claude Code / Codex / Gemini) wired
up so future sessions automatically detect the project as haex-hive-managed,
and editor JSON-Schema validation active for the config file.

**Why this priority**: This is the primary adoption path. Without it,
haex-hive stays a single-operator artefact. Every other user story
extends this one; if only Story 1 ships, haex-hive has a viable
adoption story.

**Independent Test**: on a fresh Linux machine (or a synthetic
`HOME=$TMPDIR/fake-home` sandbox), delete `~/.haex-hive/` and any prior
per-tool reference blocks, `cd` into a fresh empty project directory,
run `haex-init`, answer the prompts choosing self-ref mode and at
least one detected LLM + IDE. After the run: `spec-resolve status`
prints `0 refs, 0 cached, last update-check: never` and exits 0.
After the operator then runs `/speckit-constitution` and
`haex-init --pin-constitution`, `spec-resolve status` prints
`1 ref, 1 cached, last update-check: never` and exits 0.

**Acceptance Scenarios**:

1. **Given** a fresh machine with `claude` on `$PATH` + `~/.claude/`
   present + `code` on `$PATH` + `~/.config/Code/` present and a fresh
   empty project directory,
   **When** the operator runs `haex-init` and picks self-ref mode with
   both detected tools,
   **Then** `~/.haex-hive/haex-hive.md` is created, `~/.claude/CLAUDE.md`
   gets a marker-wrapped reference block appended, `.haex-hive.json`
   (with `harness_sources: []`) + `.specify/schemas/haex-hive.schema.json`
   + `.vscode/settings.json` + `.gitignore` additions are placed in the
   project, and one commit lands with the scaffolding.
2. **Given** the state after scenario 1 completed successfully,
   **When** the operator runs `/speckit-constitution` in their agent
   session to define the constitution and commits the resulting
   `.specify/memory/constitution.md`, then runs `haex-init --pin-constitution`,
   **Then** `.haex-hive.json.harness_sources` gains the
   `{role: "constitution", repository: "self", revision: <HEAD SHA>,
   path: ".specify/memory/constitution.md"}` entry and a follow-up
   commit lands wiring it in.
3. **Given** a machine where the operator has `claude` installed but does
   not use it in this project,
   **When** the operator sees the multi-select prompt and picks only the
   IDE (not the LLM),
   **Then** `~/.claude/CLAUDE.md` is not touched at all; only the IDE
   mapping file is written, AND the selection is persisted to
   `.haex-hive.json.managed_tools` so a later prompt-free rerun (`--yes`)
   reconfigures only the tools the operator originally chose. A tool
   the operator deliberately excluded here MUST stay untouched by a
   subsequent `--yes` rerun even if new tool executables appear on
   PATH between runs. To re-open the selection, the operator either
   deletes `managed_tools` from `.haex-hive.json` or runs without
   `--yes`.
4. **Given** any run of Story 1,
   **When** the operator declines a specific prompt's Y/N,
   **Then** that specific action is skipped, subsequent independent
   actions still proceed, and the tool's final report accurately lists
   what was and was not done.

---

### User Story 2 — Wiring a project into a multi-repo family (Priority: P1)

A team already maintains a shared specs / constitution repository — for
example `secana-specs` that owns specifications for ten or more sibling
repos. When a new repo joins the family, the operator wants haex-init
to point that repo at the family constitution instead of creating a
standalone one, so all family repos stay in sync when the shared
constitution is bumped.

**Why this priority**: This is the second load-bearing use case from
brainstorming; it enables the "one central spec repo, many consuming
repos" pattern that Spec 004's `harness_sources` was specifically
designed to allow. Without external-ref support at init time, the
family-repo pattern requires the same hand-editing that Spec 004
already left in place.

**Independent Test**: given a synthetic bare-repo fixture at a
resolvable path acting as the "family spec repo", running `haex-init`
in external-ref mode against that fixture's URL + SHA + path produces
a `.haex-hive.json` whose `harness_sources[0]` points at the external
triple, and a subsequent `spec-resolve resolve --role constitution`
returns the exact bytes stored at that SHA in the external repo.

**Acceptance Scenarios**:

1. **Given** the operator has selected external-ref mode,
   **When** they enter a valid `https://` or `ssh://` or SCP-style URL,
   a full 40-character commit SHA, and a path that exists at that SHA
   in the remote,
   **Then** haex-init verifies the reference resolves before writing
   ANY project file, user-global file, schema, IDE mapping file, or
   `.gitignore` update, then writes `.haex-hive.json` with the
   external triple and does not create a local
   `.specify/memory/constitution.md`. Failed verification MUST leave
   both the project directory and `$HOME` byte-identical to their
   pre-invocation state — no `.haex-hive.json`, no schema, no
   marker-block updates, no `~/.haex-hive/` writes, AND no leftover
   verification cache. The verification cache under
   `$XDG_CACHE_HOME/haex-init/verify/<url-slug>/` (or
   `$HOME/.cache/haex-init/verify/<url-slug>/` when `$XDG_CACHE_HOME`
   is unset) is retained only when verification succeeds; a failing
   run removes any cache it created and leaves cache trees from prior
   successful runs untouched.
2. **Given** the operator enters a URL with a rejected scheme
   (`file://`, `git://`, `http://`, or a bare local path),
   **When** haex-init validates the input,
   **Then** the URL is rejected pre-network with an actionable message
   naming the offending scheme, and no files are written.
3. **Given** the operator enters a syntactically valid URL and SHA but
   the SHA is not reachable at the remote,
   **When** haex-init runs its pre-write git fetch,
   **Then** git's actual error is surfaced to the operator, no partial
   `.haex-hive.json` is written, and the operator can correct the
   values and retry within the same invocation.

---

### User Story 3 — Idempotent re-run + version-aware upgrade (Priority: P2)

An operator (or an automated housekeeping script) wants to re-run
`haex-init` in a project that was already initialised, either as a
sanity check ("is everything still set up correctly?") or after
downloading a newer `haex-init` that carries updated session
instructions.

**Why this priority**: idempotency is what makes the tool safe to
re-invoke without ceremony. Without it, operators avoid running the
tool a second time out of fear of double-patching or silent
overwrites. Version-aware upgrades keep the operator's canonical
instructions file (`~/.haex-hive/haex-hive.md`) in sync with the tool
that produced it.

**Independent Test**: run `haex-init` in a fresh project to
completion. Run it a second time, immediately, with no other changes.
The second run must print `"Everything in order. No actions needed."`,
produce zero prompts, and exit 0. Then bump the embedded version in a
scratch copy of `haex-init` and run it a third time — that run must
detect the version mismatch on the reference blocks and offer the
diff for the operator's approval.

**Acceptance Scenarios**:

1. **Given** a project where a previous `haex-init` invocation
   completed successfully and nothing else has changed,
   **When** the operator runs `haex-init` a second time,
   **Then** the tool prints `"Everything in order. No actions needed."`,
   emits zero prompts, and exits 0.
2. **Given** an up-to-date project,
   **When** the operator runs `haex-init --dry-run`,
   **Then** the tool prints its planned actions (none), makes zero
   writes verifiable by directory checksum before/after, and exits 0.
3. **Given** an up-to-date project on which the operator has manually
   deleted `.vscode/settings.json`,
   **When** the operator runs `haex-init` again,
   **Then** the tool detects the deletion, offers to recreate that
   single file, does not touch any other file, and after Y confirmation
   the project is back to a fully-up-to-date state.
4. **Given** a project set up by an older `haex-init` (e.g. `v=1.0`)
   whose marker block reads `<!-- haex-hive-block:begin v=1.0 -->`,
   **When** a newer `haex-init` (e.g. `v=1.1`) runs,
   **Then** the tool detects the version mismatch, shows a diff of
   the proposed block replacement, and applies it on Y confirmation.

---

### User Story 4 — Safety on the operator's existing user-global config (Priority: P2)

An operator's `~/.claude/CLAUDE.md` file is a live document — it
contains their own preferences, instructions for other tools, project
notes, and generally a mix of content accumulated over months of use.
Adding haex-hive integration must not disturb any of that.

**Why this priority**: A single accidental overwrite of the
operator's user-global config would be catastrophic and untrustworthy.
This story specifies the exact non-disruption guarantee, verifiable
by test.

**Independent Test**: prepare a fake `~/.claude/CLAUDE.md` with a
byte-known payload of unrelated content (e.g. the operator's own
coding-style preferences). Run `haex-init` and accept the reference
block prompt. Compute a SHA-256 of the file's content EXCLUDING the
added marker block; assert the SHA-256 equals the pre-run SHA-256.
Repeat: run `haex-init` a second time (idempotent path); assert the
file is unchanged byte-for-byte.

**Acceptance Scenarios**:

1. **Given** an existing `~/.claude/CLAUDE.md` with pre-existing
   operator content and no haex-hive block,
   **When** `haex-init` patches the file,
   **Then** the patch is confined to a marker-wrapped block appended
   at the end (or replacing an existing marker block); every byte
   outside those markers is unchanged.
2. **Given** an existing `~/.claude/CLAUDE.md` that already contains
   a haex-hive marker block at the same version as the current
   `haex-init`,
   **When** `haex-init` runs its detection,
   **Then** the file is not modified at all (idempotency at the
   file level, not just the block level).
3. **Given** a broken `~/.claude/CLAUDE.md` that has a marker-begin
   line but no matching marker-end line,
   **When** `haex-init` tries to patch,
   **Then** the tool refuses to touch the file, prints the specific
   inconsistency, and instructs the operator to fix it manually.

---

### Edge Cases

- **Operator has no home directory writable / `$HOME` unset**: refuse
  gracefully with a message naming the problem; touch nothing.
- **Operator declines every prompt**: run completes with zero writes
  and a summary listing what would have been done; exit 0.
- **Operator declines the auto-commit but files were written**:
  files stay on disk; tool prints the exact commit command the
  operator can run manually. For self-ref this is a single commit
  (no placeholder-revision awkwardness — `harness_sources` is
  empty until `--pin-constitution` runs later).
- **Project is not a git repo**: tool offers `git init` before the
  scaffolding commit; operator can decline (files stay on disk,
  git init + commit are on the operator).
- **Project already has a `.haex-hive.json` that is schema-invalid**:
  tool refuses to touch it, prints the specific schema violation and
  the entry it points to, tells the operator to fix and re-run.
- **`.idea/` is gitignored and the operator selected JetBrains**:
  tool warns before writing that the mapping file will be
  operator-local (not committed); operator can proceed or skip.
- **The embedded template in `haex-init` does not byte-match the
  repo's canonical `.md`**: not an operator-facing runtime state;
  this is a build/CI failure caught by the sync test in the
  haex-hive repo before `haex-init` is ever shipped.
- **Operator has multiple LLM tools installed but uses only one for
  the project**: multi-select prompt exposes only detected tools, and
  only touches per-tool config for the ones the operator picks.
- **Operator's OS has a case-insensitive filesystem (macOS)**: the
  spec-resolve URL string-exact match rule from Q1 clarification of
  Spec 004 already handles this; haex-init inherits the semantics.

## Requirements *(mandatory)*

### Functional Requirements

**Detection and selection**

- **FR-001**: `haex-init` MUST detect installed LLM tooling on the
  operator's system using a two-signal check (executable on `$PATH`
  AND presence of the tool's user-config directory) for at least
  Claude Code, Codex, and Gemini.
- **FR-002**: `haex-init` MUST detect installed IDE tooling using
  the same dual-signal approach for at least the VSCode family
  (VSCode / Cursor / Windsurf, distinguishable via their executable
  name and user-config directory) and the JetBrains family
  (IntelliJ / PyCharm / GoLand / WebStorm / … via any of their
  executable names or the JetBrains user-config directory).
- **FR-003**: `haex-init` MUST present a single numbered multi-select
  prompt listing all detected LLM tools and all detected IDEs, from
  which the operator picks the subset they actually want haex-hive
  wired into (comma-separated numbers, `all`, `none`, or per-item
  Y/N — implementation choice; the operator MUST be able to pick
  fewer than all detected items).
- **FR-004**: `haex-init` MUST support `--include <name>[,<name>...]`
  as an override that forces inclusion of tools not surfaced by
  detection (e.g. the tool exists but detection missed it).
- **FR-005**: `haex-init` MUST NOT offer a tool that failed detection
  and was not force-included via `--include`.

**Operator-level setup**

- **FR-006**: `haex-init` MUST create `~/.haex-hive/haex-hive.md`
  from an embedded canonical string constant when the file is
  missing or its byte content differs from the embedded constant.
- **FR-007**: `haex-init` MUST write `~/.haex-hive/VERSION` with the
  semantic version of the `haex-init` invocation that produced the
  current instructions file.
- **FR-008**: `haex-init` MUST patch the per-tool user-global config
  file for each selected LLM tool (Claude Code → `~/.claude/CLAUDE.md`;
  Codex → `~/.codex/AGENTS.md`; Gemini → `~/.gemini/GEMINI.md`) by
  appending or replacing a marker-wrapped block of the form:

  ```
  <!-- haex-hive-block:begin v=<version> -->
  ## haex-hive
  At session start, and in any repository containing `.haex-hive.json`
  at its root, read `~/.haex-hive/haex-hive.md` and follow the
  instructions there.
  <!-- haex-hive-block:end -->
  ```

- **FR-009**: `haex-init` MUST NEVER modify content outside the
  begin/end marker boundaries. Any change to the operator's
  user-global files MUST be confined to the marker-wrapped block.
  The block itself is treated as `haex-init`'s auto-managed
  territory — operator content that must survive updates belongs
  outside the markers (before or after the block). When updating a
  block, the diff-preview surfaces any operator hand-edits inside
  the block as removals, and the operator's Y/N decision applies:
  N preserves the existing block byte-for-byte, Y replaces the
  block with the new content (and hand-edits inside are lost).
- **FR-010**: `haex-init` MUST refuse to touch a user-global config
  file that contains a marker-begin line without a matching
  marker-end line, printing the specific inconsistency for the
  operator to fix.

**Project-level setup — common**

- **FR-011**: `haex-init` MUST place `.specify/schemas/haex-hive.schema.json`
  from an embedded constant that is byte-identical to the canonical
  schema shipped by the haex-hive repo itself.
- **FR-012**: `haex-init` MUST write project-local IDE
  schema-mapping files only for the IDEs the operator selected in
  the detection prompt (VSCode-family → `.vscode/settings.json` with
  `json.schemas`; JetBrains-family → `.idea/jsonSchemas.xml`).
- **FR-013**: `haex-init` MUST warn the operator before writing a
  JetBrains mapping file into a `.idea/` directory that is
  gitignored, since the mapping will not travel with the project.
- **FR-014**: `haex-init` MUST add missing haex-hive-relevant
  patterns (at minimum: `__pycache__/`) to `.gitignore`, without
  duplicating patterns that are already present.

**Project-level setup — self-ref mode**

- **FR-015**: When the operator selects self-ref, `haex-init` MUST
  NOT create `.specify/memory/constitution.md`. The constitution
  is defined later by the operator running `/speckit-constitution`
  in their agent session; `haex-init`'s role is mechanical
  scaffolding, not constitutional authoring.
- **FR-016**: When the operator selects self-ref, `haex-init` MUST
  create `.haex-hive.json` with `harness_sources: []` (empty array).
  This is the constitutionally-consistent "opted in but no
  permissions granted yet" state per Principle V. `spec-resolve
  status` on this state correctly reports `0 refs, 0 cached`.
- **FR-017**: When self-ref is chosen, `haex-init` MUST offer a
  single commit for the scaffolding (`.haex-hive.json` +
  `.specify/schemas/haex-hive.schema.json` + IDE mapping files +
  `.gitignore` additions). No two-commit dance is needed because
  no constitution SHA is being pinned at this stage.
- **FR-018**: `haex-init` MUST print explicit next-step guidance to
  the operator on completion of self-ref init, naming the two
  follow-up actions: (a) run `/speckit-constitution` in the agent
  session to define the constitution content, then (b) run
  `haex-init --pin-constitution` to add the constitution reference
  to `.haex-hive.json` and pin it to `HEAD`.
- **FR-019**: `haex-init --pin-constitution` MUST (a) verify
  `.specify/memory/constitution.md` exists in the project, (b) verify
  `.haex-hive.json.harness_sources` does not already contain a
  `role: "constitution"` entry (idempotency: refuse with clear
  message if already pinned), (c) add a new role-carrying entry
  `{role: "constitution", repository: "self", revision: <HEAD-SHA>,
  path: ".specify/memory/constitution.md"}` to `harness_sources`,
  and (d) offer a follow-up commit ("`haex-init: pin constitution to
  HEAD`"). If the operator declines the commit, files stay on disk
  and the tool prints the manual finalisation command.

**Project-level setup — external-ref mode**

- **FR-020**: When the operator selects external-ref, `haex-init`
  MUST NOT create `.specify/memory/constitution.md` (the constitution
  lives in the external repo).
- **FR-021**: `haex-init` MUST prompt for and validate the repository
  URL against the accepted schemes (`https://`, `ssh://`, SCP-style
  `user@host:path`) before any network activity; `file://`, `git://`,
  `http://`, and bare local paths MUST be rejected with an actionable
  scheme-specific message.
- **FR-022**: `haex-init` MUST validate the SHA against
  `^[0-9a-f]{7,40}$` (lowercase hex, 7-40 characters) before any
  network activity.
- **FR-023**: `haex-init` MAY offer an optional convenience prompt
  "Fetch latest HEAD SHA from the remote?" that runs `git ls-remote
  <url> HEAD` and offers the returned SHA as the default answer; the
  operator MUST be able to override with any other SHA.
- **FR-024**: Before writing `.haex-hive.json` in external-ref mode,
  `haex-init` MUST verify via an internal git fetch (into a scratch
  cache directory the tool manages, not the operator's cache) that
  (a) the SHA is reachable at the URL, (b) the path exists at that
  SHA, (c) the content at that path is non-empty.
- **FR-025**: If verification fails in external-ref mode, `haex-init`
  MUST NOT write `.haex-hive.json`, MUST surface git's actual error
  to the operator, and MUST allow the operator to correct one or
  more of the URL / SHA / path within the same invocation and retry.

**Idempotency**

- **FR-026**: A re-run of `haex-init` on a project whose operator-
  level and project-level state matches the current tool's expected
  output MUST print `"Everything in order. No actions needed."`,
  produce zero prompts, make zero writes, and exit 0.
- **FR-027**: A re-run of `haex-init` on a partially-modified state
  (some pieces up-to-date, others missing or version-mismatched)
  MUST offer prompts only for the missing or mismatched pieces and
  leave the up-to-date pieces alone.
- **FR-028**: `haex-init` MUST detect a marker block whose version
  differs from the current tool's version and offer to replace it
  with a diff preview.
- **FR-029**: `haex-init --dry-run` MUST run the full detection and
  planning flow, print the planned actions to stdout, make zero
  writes to any filesystem location, exit 0 if no actions would run,
  and exit 1 if any action would run.
- **FR-030**: `haex-init --yes` MUST auto-confirm every Y/N prompt.
- **FR-031**: `haex-init` MUST NOT provide a `--force` flag. Fully
  re-running specific steps requires the operator to delete the
  relevant on-disk state first.

**Content, location, and constraints**

- **FR-032**: All content written by `haex-init` (session
  instructions, reference blocks, IDE mapping configs,
  `.gitignore` additions, commit messages, stderr/stdout strings,
  interactive-prompt strings) MUST be in English.
- **FR-033**: The embedded canonical session instructions content
  MUST byte-match `.specify/templates/haex-hive-session-instructions.md`
  in the haex-hive repo. The version string used in the marker block
  `v=<version>` and in `~/.haex-hive/VERSION` MUST be a human-readable
  semantic version (e.g. `1.0`, `1.1`) that bumps ONLY when this
  canonical content changes; tool-code-only releases (bug fixes,
  refactors, added tests) MUST NOT bump it. To enforce both invariants
  mechanically, the tool source carries adjacent constants
  `INSTRUCTIONS_VERSION` and `INSTRUCTIONS_SHA256` (SHA-256 of the
  embedded template bytes), and a sync test in the test suite verifies
  (a) `SHA-256(embedded_template) == INSTRUCTIONS_SHA256` and (b) the
  marker written by the tool actually uses `INSTRUCTIONS_VERSION`. A
  content change without matching updates to both constants fails the
  test.
- **FR-034**: `haex-init` MUST live at `.specify/scripts/haex-init`
  in the haex-hive repo, executable, with `#!/usr/bin/env python3`
  shebang.
- **FR-035**: `haex-init` MUST use only the Python 3.10+ standard
  library plus git (invoked via `subprocess`). No third-party
  packages.

**Testing**

- **FR-036**: The `haex-init` test suite MUST run in complete
  isolation from the developer's real `~/.claude/`, `~/.codex/`,
  `~/.haex-hive/`, or any other user-global config path — every
  filesystem access under `$HOME` MUST resolve into a
  test-controlled temporary directory (via `HOME=$TMPDIR/fake-home`).
- **FR-037**: Test-time LLM/IDE detection MUST be controllable via
  fake binaries on a test-controlled `PATH` prefix, so tests can
  simulate "claude is installed" / "code is NOT installed" without
  reflecting the developer's actual setup.
- **FR-038**: The test suite MUST include: fresh-operator end-to-end,
  idempotent re-run, partial-state, marker-safety (byte-identical
  outside markers), version-upgrade (block-replacement), dry-run
  (zero writes verifiable), self-ref-mode (single scaffolding
  commit + verifiable `harness_sources: []` shape),
  `--pin-constitution` mode (adds the `role: constitution` entry
  once, refuses when already present), external-ref-mode
  (against a synthetic bare-repo fixture, no network), and
  embedded-content-sync (byte-compare template `.md` vs embedded
  string constant).
- **FR-039**: A manual smoke test against a real external remote
  (e.g. github.com/octocat/Hello-World) MUST be documented in the
  `.validation-runs/` directory but MUST NOT be part of the
  automated `run-all.sh` (network dependency).

### Key Entities

- **`~/.haex-hive/` directory** — user-global (per operator, per
  machine) storage location for the canonical session instructions
  and a version marker; created by `haex-init` on first run.
- **`~/.haex-hive/haex-hive.md`** — canonical session-start
  instructions text; read by the LLM agent at session start; content
  originates from `.specify/templates/haex-hive-session-instructions.md`
  in the haex-hive repo and is byte-identical to it via the sync
  test.
- **`~/.haex-hive/VERSION`** — plain text file containing the
  semantic version of the `haex-init` that last wrote
  `haex-hive.md`; used for upgrade detection on re-run.
- **Marker-wrapped reference block** — a short well-formed Markdown
  block, enclosed by `<!-- haex-hive-block:begin v=<version> -->`
  and `<!-- haex-hive-block:end -->`, that gets inserted into the
  operator's per-tool user-global config file (`~/.claude/CLAUDE.md`,
  `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`); versioned so
  future upgrades can safely replace it.
- **`.haex-hive.json` project marker** — from Spec 004; `haex-init`
  is the tool that writes it correctly for the operator instead of
  requiring hand-editing.
- **Constitution reference** — the `harness_sources` entry with
  `role: "constitution"`; either self-referential (project has its
  own `.specify/memory/constitution.md`) or external (points at
  another repo's URL + SHA + path).
- **Project-local IDE schema-mapping file** — a file the specific
  IDE reads to know that `.haex-hive.json` should be validated
  against `.specify/schemas/haex-hive.schema.json`
  (`.vscode/settings.json` for the VSCode family;
  `.idea/jsonSchemas.xml` for the JetBrains family).
- **Embedded string constant in `haex-init`** — the tool's own copy
  of the canonical session instructions text, baked in at ship time
  so `haex-init` needs no external file to work; kept in sync with
  the repo's `.md` template by the sync test.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001a**: An operator with zero prior haex-hive setup on their
  machine and a fresh empty project directory can, in a single
  `haex-init` invocation (self-ref mode), reach a state where
  `spec-resolve status` reports `0 refs, 0 cached` and exits 0.
  Time budget: under 3 minutes wall-clock.
- **SC-001b**: Following SC-001a, after the operator has run
  `/speckit-constitution` in their agent session to define the
  constitution and committed the result, a single
  `haex-init --pin-constitution` invocation reaches a state where
  `spec-resolve status` reports `1 ref, 1 cached` and exits 0.
  Time budget: under 30 seconds wall-clock.
- **SC-001c**: An operator setting up a consumer of an external
  constitution can, in a single `haex-init` invocation (external-ref
  mode), reach a state where `spec-resolve status` reports
  `1 ref, 1 cached (or missing if offline)` and exits 0. Time budget:
  under 3 minutes wall-clock excluding network fetch time.
- **SC-002**: On any `haex-init` invocation that patches the
  operator's user-global config file, every byte of that file
  outside the marker-wrapped block is byte-identical before and
  after the run, verifiable by SHA-256 of the file's marker-
  excluded content.
- **SC-003**: A second `haex-init` invocation on a project that was
  already fully initialised produces zero prompts, zero writes, and
  exit 0.
- **SC-004**: In external-ref mode, any invalid input (rejected URL
  scheme, malformed SHA, unreachable SHA at the remote, missing path
  at the SHA, empty content at the path) causes the tool to abort
  without writing `.haex-hive.json` at all — verifiable by
  directory-checksum before/after equality.
- **SC-005**: `haex-init --dry-run` produces zero writes verifiable
  by directory-checksum before/after equality across every
  filesystem location the tool would touch (project directory and
  every relevant location under `$HOME`).
- **SC-006**: Every test in `tests/haex-init/run-all.sh` runs
  successfully against a fake `HOME=$TMPDIR/fake-home` sandbox
  without ever accessing the developer's real `~/.claude/`,
  `~/.codex/`, `~/.gemini/`, or `~/.haex-hive/`, verifiable by
  auditing the developer's actual home directory before and after
  the test run and finding no relevant modifications.
- **SC-007**: The embedded string constant carrying the canonical
  session instructions is byte-identical to
  `.specify/templates/haex-hive-session-instructions.md` in the
  haex-hive repo, enforced by a dedicated sync test in the test
  suite that would fail CI on any drift.
- **SC-008**: Every Y/N prompt `haex-init` emits during an
  interactive self-ref initialisation names its default in bracket
  form (`[Y/n]` or `[y/N]`); every prompt for a free-form value with
  a suggested default names that default in bracket form
  (`[default: <value>]`); every prompt string is under 200 characters
  and uses no acronym or term that requires operator lookup outside
  the tool's own action-report or the docs shipped as part of Phase
  1 (`docs/haex-init.md`). Mechanically verifiable by a smoke assertion
  in the test suite that scans captured stdout during T030's
  interactive sub-case and asserts every prompt line matches the
  above shape.

## Assumptions

- The operator has Python 3.10 or newer available on `$PATH` (matches
  the constraint already carried by `spec-resolve`).
- The operator has Git 2.30 or newer available on `$PATH`.
- The operator has write access to `$HOME` and to the target project
  directory. `$HOME` is set to a valid directory.
- The operator's shell handles UTF-8 correctly for the interactive
  prompts.
- The operator either downloaded `haex-init` as a standalone Python
  file (recommended path) or is running it from a haex-hive clone;
  the tool self-contains everything it needs at runtime and does not
  read from the haex-hive repo at runtime for Phase 1.
- The operator understands that patching user-global config files is
  a per-machine action they will do once; running `haex-init` inside
  a project directory triggers both per-machine setup (first time)
  and per-project setup (every time).
- Cross-OS validation is deferred: `haex-init` is written to be
  portable but only Linux is validated in this spec. macOS and
  WSL2 validation follows the same pattern Spec 004 established —
  deferred to when a second-OS satellite is real.
- Additional LLM tools beyond Claude Code / Codex / Gemini and
  additional IDE families beyond VSCode-family / JetBrains-family
  are documented as manual setup in `docs/haex-init.md`; the
  detection + patching path in Phase 1 covers the enumerated set
  only.

## Non-Goals *(explicitly deferred)*

- **`--fetch-latest` mode**: a runtime option that would replace the
  embedded session-instructions content by fetching the current
  `.specify/templates/haex-hive-session-instructions.md` from the
  haex-hive repo's canonical URL. Requires haex-hive to have a
  public git remote — deferred to Spec 006.
- **`haex-init add-source`**: a sub-mode for adding additional
  external harness sources (beyond the constitution) to an
  existing `.haex-hive.json`. Deferred; operators can hand-edit
  `.haex-hive.json` or wait for Spec 006.
- **Multi-spec external referencing / shared-spec-repo consumer
  setup**: the pattern where a repo (like the individual consumers
  of a central `secana-specs`-style repo) references not just the
  constitution but the entire `specs/**` tree from a third repo,
  including scaffolding of `specs/*/spec-ref.json` files and
  conventions for which features apply to which consumer. Deferred
  to Spec 006 to keep Spec 005 shippable — real-world adoption
  sequence lands haex-init in self-ref mode inside a
  spec-hub-repo (like a new `secana-specs`) first, then Spec 006
  enables individual consumer repos to opt in.
- **LLM-tool skill file wrappers**: e.g. dropping
  `~/.claude/skills/haex-init/` or a Codex equivalent so operators
  could invoke a session-native `/haex-init` slash command instead
  of running the CLI. The reference block in the user-global config
  file is sufficient for Phase 1 adoption.
- **Editors beyond VSCode-family and JetBrains-family in
  auto-mapping**: Neovim/Emacs LSP setups, Sublime Text, Zed, and
  others remain documented as manual mapping in `docs/haex-init.md`.
- **Cross-OS validation**: macOS and WSL2 remain deferred (matches
  Spec 004 Assumptions).
