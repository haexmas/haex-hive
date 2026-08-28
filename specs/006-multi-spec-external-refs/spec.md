# Feature Specification: Multi-Spec External-Ref (Multi-Item Cross-Repo References)

**Feature Branch**: `006-multi-spec-external-refs`
**Created**: 2026-08-28
**Status**: Draft
**Input**: Distilled from the 2026-08-28 brainstorming session, captured
in [`docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md`](../../docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md).
Builds on Spec 004 (single-item cross-repo references) and Spec 005
(`haex-init` CLI). Closes Phase 1 of the roadmap.

## Clarifications

### Session 2026-08-28

- Q: Welches Exit-Code-Schema soll `haex-init sync` nutzen? → A: Spec 005's 0–4 Schema wiederverwenden, semantisch für Sync-Fälle interpretiert. Kein neues Schema. Granulare Programmatic-Differenzierung kommt erst bei realer Anforderung (nicht spekulativ).
- Q: Welche Grammatik gilt für den `as:`-Alias in `items[]`? → A: Kebab-case ASCII slug `[a-z0-9][a-z0-9-]*` — kleinbuchstaben, ziffern, bindestriche; muss mit Buchstaben/Ziffer beginnen. Kein `path:`, kein `:`, kein `/`, kein Unicode, kein Whitespace. Case-Fold-Konflikte über Filesystems hinweg werden per Konstruktion vermieden.
- Q: Welche Permission-Policy soll `haex-init sync` für den Extract-Subtree auf Unix-Systems anwenden? → A: Owner-only (`0700` Directories, `0600` Files). Content aus privaten Producer-Repos leaked so nicht an andere lokale User auf demselben System, ohne dass der Operator etwas konfigurieren muss. Windows-Semantik: äquivalente ACL-Restriktion (nur der aktuelle User hat Read/Write) oder der Default falls ACL-Setting nicht portable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fresh consumer inherits Constitution from a producer (Priority: P1) 🎯 MVP

An operator has a project (`secure-web-frontend`) that is not yet
haex-hive-managed. Their team also maintains a shared producer
repository (`secana-specs`) that contains a governing Constitution and
other project-independent content. The operator wants their project to
adopt the shared Constitution: agent sessions started inside the
consumer project should see the producer's Constitution as their
governing rules, without the operator hand-editing configuration
files, and without any content being copied into the consumer's own
repository.

**Why this priority**: This is Phase 1's real acceptance test — the
mechanism that unblocks any project beyond haex-hive itself from
adopting haex-hive-managed governance. Without US1, the multi-repo
value proposition of haex-hive remains theoretical. Every other user
story extends this one.

**Independent Test**: On a Linux machine, checkout a fresh copy of
`secure-web-frontend`. Run `haex-init` to bootstrap the project, then
`haex-init add-source` to add `secana-specs` as an external harness
source declaring one Constitution item pinned to a specific revision,
then `haex-init sync`. Open a Claude Code session in the project. The
session-start snippet reads the Constitution content via the
device-local resolution table and injects it into the session. The
agent, when asked, can quote a specific Principle from the producer's
Constitution unprompted.

**Acceptance Scenarios**:

1. **Given** a fresh consumer project with no `.haex-hive.json`,
   **When** the operator runs `haex-init` + `haex-init add-source` +
   `haex-init sync` targeting a producer repository at a pinned
   revision with an explicit `role: "constitution"` item,
   **Then** the consumer project has a schema-valid `.haex-hive.json`,
   a device-local `.haex-hive.local.json` mapping the constitution ref
   to an absolute path in the device-local haex-hive state area, and
   the local ignore file entry for `.haex-hive.local.json` is in place.
2. **Given** the state above, **When** an agent session starts in the
   consumer project, **Then** the session context includes the
   producer's Constitution content byte-for-byte.
3. **Given** the state above, **When** the operator's machine has the
   producer repository already cloned under another consumer's setup,
   **Then** `haex-init sync` reuses the existing device-local clone
   after verifying its origin URL, rather than cloning again.
4. **Given** the state above, **When** the operator inspects
   `.haex-hive.local.json`, **Then** every resolved path points into
   a per-pinned-revision extract directory (not the working tree of
   the local clone).

---

### User Story 2 — Consumer inherits additional content (Priority: P2)

The same operator wants to inherit more than just the Constitution:
selected skills, docs, or specific specs from the producer that agents
should be able to read during work sessions. They add these either as
part of the coarse `auto_include` preset (for the speckit-conventional
subtree in the producer) or as explicit paths / globs via
`additional_include`.

**Why this priority**: Extends US1 from "Constitution-only" to "arbitrary
producer content", which is the realistic long-term shape. Not
blocking the MVP verdict — US1 alone proves the mechanism — but
required before the feature is useful in practice.

**Independent Test**: Starting from the US1 state, extend the
producer entry with `auto_include: "speckit-defaults"` and
`additional_include: ["tools/harness-evaluator/"]`. Run `haex-init
sync`. Verify (a) `.haex-hive.local.json` contains entries for every
file under the speckit-defaults set in the producer at the pinned
revision, (b) it contains entries for every regular file under
`tools/harness-evaluator/`, (c) agents can read those files via the
resolved absolute paths.

**Acceptance Scenarios**:

1. **Given** an external-harness entry with `auto_include:
   "speckit-defaults"`, **When** `haex-init sync` runs, **Then** every
   regular file matching the documented preset paths at the pinned
   revision appears in `.haex-hive.local.json` under a deterministic
   key.
2. **Given** an external-harness entry with `additional_include`
   containing a directory path, **When** `haex-init sync` runs,
   **Then** every regular file recursively under that directory at
   the pinned revision appears in `.haex-hive.local.json`, sorted
   lexicographically and deduplicated.
3. **Given** an `additional_include` entry that matches nothing at
   the pinned revision, **When** `haex-init sync` runs, **Then** it
   refuses with a structured error naming the unmatched pattern and
   leaves the previous state intact.
4. **Given** an `additional_include` entry that points to a
   symbolic link or non-regular file entry in the pinned tree,
   **When** `haex-init sync` runs, **Then** it refuses with a
   structured error rather than silently following or omitting.

---

### User Story 3 — SHA-bump update flow (Priority: P2)

The producer moves forward and publishes new content at a new commit.
The operator wants to bump the pinned revision in their consumer,
re-run `haex-init sync`, and have the resolved paths and extracted
content update accordingly. If the new revision has renamed or removed
a path that the consumer explicitly listed, the operator wants a clear
failure with the specific unresolvable path named — not a silent
partial update.

**Why this priority**: Every long-lived multi-repo setup will bump
revisions. This story defines the operator experience for that flow
and ensures state cannot drift silently. Testable independently from
US2.

**Independent Test**: Starting from the US1 state, change the
`revision:` field in `.haex-hive.json` to a newer commit SHA. Run
`haex-init sync`. Verify (a) the local clone fetches new objects,
(b) `.haex-hive.local.json` is regenerated with paths under the new
revision's extract directory, (c) the previous extract directory
remains (not deleted). Then bump to a revision where an explicit
item's path has been renamed — verify `haex-init sync` refuses, names
the unresolvable path, and leaves `.haex-hive.local.json` at its
prior state.

**Acceptance Scenarios**:

1. **Given** a consumer with pinned revision A and a synced state,
   **When** the operator changes the pin to revision B and runs
   `haex-init sync`, **Then** the resolution table's absolute paths
   move to `.extracts/@<B>/…` and byte-identical content is exposed.
2. **Given** the state above where an explicit `items[]` entry's
   `path:` is missing at revision B, **When** `haex-init sync` runs,
   **Then** it exits with a non-zero code, prints a structured
   diagnostic naming the unresolvable path, does not overwrite
   `.haex-hive.local.json`, and does not write partial extracts.
3. **Given** any failure during sync, **When** the operator inspects
   `.haex-hive.local.json`, **Then** it either reflects the prior
   fully-successful state or is absent (never partially written).

---

### User Story 4 — `haex-init add-source` CLI including `--from-repo` bootstrap (Priority: P3)

The operator wants to add an external-harness entry to a consumer's
config without hand-editing `.haex-hive.json`. They also want, when
onboarding a second consumer that will use the same producer, to copy
the producer entry from a neighbor consumer that is already
configured — rather than re-typing it.

**Why this priority**: Hand-editing `.haex-hive.json` is error-prone
(schema violations, invalid SHAs, credential-embedded URLs). The
`add-source` command puts the CLI in the operator's path for these
edits. The `--from-repo` bootstrap solves the config-propagation DX
across consumers on the same device. Not blocking US1–3, but strongly
requested to make the feature usable at scale.

**Independent Test**: On a device with a working configured consumer
(`secure-web-frontend`), initialise a second consumer
(`fresh-consumer`) with `haex-init`. Run `haex-init add-source
--from-repo <path-to-secure-web-frontend>`. Verify the interactive
prompt offers to copy the `secana-specs` external-harness entry with
its repository, revision, `auto_include`, `additional_include`, and
`items[]`. On accept, `.haex-hive.json` in the fresh consumer holds
the copied entry, and a subsequent `haex-init sync` succeeds.

**Acceptance Scenarios**:

1. **Given** the operator runs `haex-init add-source` in from-scratch
   mode, **When** they enter repository URL, revision, `name`, and
   include preferences, **Then** the CLI validates each field
   (rejects HTTPS URLs with embedded credentials, rejects invalid
   SHAs, rejects unsafe storage names), then writes a schema-valid
   external-harness entry to `.haex-hive.json`.
2. **Given** the operator runs `haex-init add-source --from-repo
   <neighbor>`, **When** the neighbor consumer's `.haex-hive.json`
   contains one or more external-harness entries, **Then** the CLI
   lists them, prompts for which to copy, and applies the copy.
3. **Given** the neighbor consumer's `.haex-hive.json` is schema-
   invalid, **When** `haex-init add-source --from-repo <neighbor>`
   runs, **Then** it refuses without attempting a partial copy and
   surfaces the validation error.
4. **Given** an add-source flow completes successfully, **When**
   `--no-sync` was not passed, **Then** `haex-init sync` is triggered
   automatically to bring the consumer into the resolved state.

---

### Edge Cases

- **Multiple consumers on the same device pin different revisions of
  the same producer**: both revisions must resolve correctly through
  their respective extract directories. The producer's device-local
  clone is reused; each pinned revision has its own extract subtree.
- **The device-local haex-hive state area is missing (never created
  or manually deleted)**: `haex-init sync` regenerates it from
  scratch, clones each referenced producer, and rebuilds
  `.haex-hive.local.json` end-to-end.
- **The producer repository is behind authentication that has
  expired**: `haex-init sync` fails with a message naming the
  offending repository and pointing at the resolution path (SSH agent
  check, credential manager check, or the platform equivalent).
- **A file matched by an `auto_include` preset at pinned revision A
  is renamed at revision B**: after SHA-bump the file appears under
  its new path in the resolved table with a new deterministic key;
  the old key disappears. Consumer-side wiring using aliases (`as:`)
  survives; wiring using raw path keys must be updated.
- **The same file is matched by both an `auto_include` preset and by
  an `additional_include` entry**: it is extracted once and appears
  under exactly one resolved key.
- **The operator declares two producer entries whose storage names
  collide but whose canonical repository URLs differ**: `haex-init
  sync` refuses without side effects and names both entries.
- **The producer clone directory exists but its `remote.origin.url`
  does not match the declared repository URL**: `haex-init sync`
  refuses to reuse it. The operator resolves manually (rename storage
  name, or move the local clone aside).
- **Two `haex-init sync` invocations run concurrently on the same
  consumer**: the second acquires a directory-scoped lock, waits for
  the first to complete (or fail), then proceeds.
- **The consumer's local `.gitignore` already contains
  `.haex-hive.local.json` outside of the tool-managed marker block**:
  `haex-init sync` recognises the duplicate and does not add a second
  entry inside its marker block.

## Requirements *(mandatory)*

### Functional Requirements

#### Configuration shape

- **FR-001**: `.haex-hive.json`'s `harness_sources[]` array MUST
  support a new entry role `external-harness` alongside the existing
  `constitution` role and the existing permission-only (role-less)
  shape. All three shapes co-exist within a single array.
- **FR-002**: An `external-harness` entry MUST identify one producer
  repository at one pinned immutable revision. Every reference format
  established by Principle IV of the constitution applies unchanged.
- **FR-003**: An `external-harness` entry MUST support declaring
  inheritance via either or both of two mechanisms: (a) a coarse
  `auto_include` preset naming a producer-shape convention, (b) an
  explicit `additional_include` list of producer-relative paths and
  globs, and MUST additionally support (c) an `items[]` array of
  explicit item declarations each carrying its own item-level role
  and a required alias.
- **FR-004**: The `auto_include` preset `speckit-defaults` MUST
  expand to a fixed, documented set of paths under the producer's
  `.specify/` subtree — specifically `.specify/memory/**`,
  `.specify/workflows/**`, `.specify/templates/**`, and
  `.specify/schemas/**`.
- **FR-005**: The `additional_include` list MUST be resolved from
  the pinned Git tree (not any working tree), enumerating regular
  files under directories or matches under globs. Results MUST be
  lexicographically sorted, deduplicated, non-empty, and MUST reject
  symbolic-link or non-regular-file entries with a structured error.
- **FR-006**: An `external-harness` entry's `items[]` MUST require
  every explicit item to carry an `as: "<alias>"` field, forming the
  stable consumer-facing key `<name>:<alias>`. The alias grammar
  MUST match the regular expression `^[a-z0-9][a-z0-9-]*$` (ASCII
  kebab-case slug: lowercase letters, digits, and hyphens; first
  character alphanumeric). This grammar is strictly a subset of what
  is safe in any path component or JSON key on Linux, macOS, and
  Windows, and eliminates case-fold ambiguity across
  case-insensitive filesystems. The reserved prefix `path:` cannot
  form under this grammar (colon excluded), so no additional
  reserved-word exclusion is needed.
- **FR-007**: An entry's `repository` field MUST reject HTTPS URLs
  that carry embedded userinfo (username, password, or token) before
  writing the config, so that no credential material enters
  version-controlled state.
- **FR-008**: An entry's storage `name` field MUST be validated as a
  single platform-safe path component (no separators, no `.` or
  `..`, no absolute or Windows-drive-qualified path, no reserved
  Windows device name), defaulting to the repository URL basename
  with a `.git` suffix stripped.

#### Selection semantics and Constitution scope

- **FR-009**: The system MUST treat the consumer's `harness_sources[]`
  as the sole trust boundary. Producer-side manifests and
  producer-declared bundle lists MUST NOT influence what content is
  inherited.
- **FR-010**: For governing-Constitution injection at session start,
  the system MUST honour only concrete Constitution declarations: a
  top-level `role: "constitution"` entry, or a nested `items[]` entry
  with item-level `role: "constitution"` inside an `external-harness`.
  A Constitution file merely matched by `auto_include` or
  `additional_include` MUST be available as agent-readable content
  but MUST NOT implicitly govern the session.
- **FR-011**: When multiple Constitution sources are declared, the
  system MUST record their emission order deterministically (top-level
  entry first, then nested items in `harness_sources[]` order and
  `items[]` order) and MUST emit each source's raw bytes in that
  sequence with a fixed source label between documents.
- **FR-012**: The system MUST NOT override the consumer's own
  speckit-managed files under `.specify/templates/**` and
  `.specify/workflows/**` with producer content. Producer content in
  those paths remains inheritable as agent-readable content only.

#### Local storage and content addressing

- **FR-013**: The system MUST clone producer repositories in full
  (no shallow / depth-limited clone) into a device-local
  haex-hive state area, distinct from the platform cache location.
- **FR-014**: For every declared consumer entry that shares a storage
  `name` with an existing local clone, the system MUST verify the
  clone's `remote.origin.url` matches the declared repository URL
  before reuse. On mismatch, `haex-init sync` MUST refuse and preserve
  all consumer-visible state.
- **FR-015**: The system MUST expose each pinned item's content
  under a per-pinned-revision extract directory of the form
  `<state-area>/repos/<name>/.extracts/@<sha>/…`, so that multiple
  consumers pinning different revisions of the same producer coexist
  without conflict.
- **FR-016**: The system MUST regenerate the extract subtree from
  Git objects (not from a working tree checkout), leaving the
  producer clone's working tree untouched for operator browsing.

#### Path-Return via device-local table

- **FR-017**: Each consumer project MUST have a device-local file
  `.haex-hive.local.json` that maps every deterministic key produced
  by the entry expansion to an absolute filesystem path into the
  extract subtree.
- **FR-018**: `.haex-hive.local.json` MUST NOT be committed to
  version control. `haex-init` MUST manage a marker-block entry
  inside the consumer's local ignore file (using the Spec 005 marker
  conventions) so that the ignore entry is durable across
  regeneration.
- **FR-019**: The existing `spec-resolve resolve` command MUST
  continue to write raw file bytes to stdout byte-for-byte, with no
  behavioural change from Spec 004. Path-Return is a new capability
  exposed exclusively via `.haex-hive.local.json`, not by mutating
  `resolve`.
- **FR-020**: Every resolved key MUST be deterministic and unique:
  `<name>:<alias>` for explicit items, `<name>:path:<repo-relative-
  path>` for include-expansion matches. Where an alias resolves to
  the same source file as a path-key match, exactly one key MUST
  appear (with a documented tie-break). The system MUST refuse any
  configuration that would produce a duplicate final key.

#### `haex-init sync` command

- **FR-021**: `haex-init sync` MUST be idempotent when
  `.haex-hive.json` and the pinned producer state are unchanged.
- **FR-022**: `haex-init sync` MUST perform all validation and
  extraction as a preflight before publishing any consumer-visible
  state. If any step fails, the previous `.haex-hive.local.json`
  MUST remain intact and no partial extract MUST be exposed under a
  finalised name.
- **FR-023**: `haex-init sync` MUST write extract files to unique
  temporary siblings inside the target directory, verify integrity,
  then atomically rename to their final path.
- **FR-024**: `haex-init sync` MUST write the new
  `.haex-hive.local.json` to a same-directory temporary file, then
  atomically replace the target. On any preflight or extraction
  failure the temporary file MUST be removed best-effort.
- **FR-025**: `haex-init sync` MUST serialise concurrent invocations
  on the same consumer via a directory-scoped lock, so that a second
  invocation waits for the first to complete rather than corrupting
  either state.
- **FR-026**: `haex-init sync` MUST refuse and exit non-zero with a
  structured diagnostic in each of these cases: (a) the pinned
  revision is unreachable from the local clone after fetch,
  (b) an explicit `items[]` path is absent at the pinned revision,
  (c) an `additional_include` glob matches nothing at the pinned
  revision, (d) any include match is a symbolic link or non-regular
  entry, (e) the local clone's origin URL disagrees with the
  declared repository URL, (f) two entries share a storage name but
  resolve to different canonical URLs, (g) any final resolved key
  would collide.
- **FR-027**: `haex-init sync` MUST accept a `--dry-run` flag that
  computes and prints the action plan (planned clones, fetches, and
  extract paths) without touching disk beyond read operations, and
  MUST exit with an exit code discriminating between "nothing to do"
  and "action would be taken".
- **FR-027a**: `haex-init sync` MUST use the same exit-code scheme as
  the parent `haex-init` CLI (established in Spec 005): **0** =
  success (everything applied cleanly, or `--dry-run` had no pending
  actions); **1** = `--dry-run` found pending actions; **2** =
  refused (bad CLI, malformed marker block, schema-invalid config,
  or preconditions unmet — includes FR-026 cases b, c, d, e, f, g);
  **3** = external-ref verification failed (FR-026 case a: pinned
  revision unreachable, or any auth/reachability failure per FR-037);
  **4** = git subprocess failed unexpectedly. The structured
  diagnostic on stderr identifies the specific sub-case within the
  code. No sub-command-specific exit codes are introduced; `sync`
  reuses `haex-init`'s established contract.

#### `haex-init add-source` command

- **FR-028**: `haex-init add-source` MUST support two modes:
  from-scratch interactive entry, and `--from-repo <path>`
  bootstrap from a neighbor consumer's `.haex-hive.json`.
- **FR-029**: In from-scratch mode, `haex-init add-source` MUST
  prompt the operator for repository URL, revision (validated as a
  full 40-character SHA), storage name (defaulted and validated per
  FR-008), include preferences (`auto_include`, `additional_include`),
  and any initial `items[]` (alias + role + path), MUST run all
  applicable validations (FR-005, FR-007, FR-008, FR-020), and MUST
  write the resulting entry to `.haex-hive.json`.
- **FR-030**: In `--from-repo` mode, `haex-init add-source` MUST
  read the neighbor consumer's `.haex-hive.json`, refuse without
  side effects if it is schema-invalid, present the neighbor's
  external-harness entries for selection, and on accept apply the
  selected entry to the current consumer's `.haex-hive.json` after
  re-validating it against the current consumer's context.
- **FR-031**: `haex-init add-source` MUST refuse to add an entry
  when a schema violation or field validation fails (unsafe name,
  HTTPS with userinfo, invalid SHA, unresolvable pinned revision,
  storage-name collision with a different URL, duplicate resolved
  keys). Refusal MUST leave `.haex-hive.json` unchanged.
- **FR-032**: `haex-init add-source` MUST, by default, trigger
  `haex-init sync` after a successful entry addition, and MUST
  accept a `--no-sync` flag to opt out.

#### Backwards compatibility and non-regression

- **FR-033**: A consumer whose `harness_sources[]` contains only
  Spec-004-shaped entries (single `role: "constitution"` entry and/or
  permission-only entries) MUST continue to function without
  modification. `spec-resolve resolve`, `spec-resolve prefetch`
  (including its `--dry-run` `OK`/`MISSING` output), and existing
  session-start flows for such consumers MUST behave exactly as
  before Spec 006.
- **FR-034**: The Spec-004 object cache at the platform cache
  location MUST remain the authoritative store for legacy
  role-carrying and permission-only references and for
  `specs/*/spec-ref.json`-discovered references. The new
  device-local state area MUST be used exclusively for
  `external-harness` expansion and its extracts.
- **FR-035**: `haex-init sync` in a consumer that declares no
  `external-harness` entries MUST be a legal no-op that does not
  create the device-local state area and does not write
  `.haex-hive.local.json`.

#### Cross-platform

- **FR-036**: The system MUST NOT use symbolic links, junctions,
  bind mounts, or any other platform-specific link mechanism for
  content delivery. Portability across Linux, macOS, and Windows
  (under WSL2 for the mechanical target) MUST hold by using only
  regular files and absolute paths.

#### Auth diagnostics

- **FR-037**: On authentication or reachability failure against a
  producer repository, the system MUST surface a structured
  diagnostic identifying the repository URL and pointing at the
  operator's likely remediation (SSH key configuration, credential
  manager state, network / VPN). The system MUST NOT attempt any
  automated credential provisioning.

#### File permissions and privacy

- **FR-038**: On Unix-like systems (Linux, macOS, WSL2), `haex-init
  sync` MUST create the device-local state area root, per-producer
  clone directories, and every extract file with owner-only
  permissions: `0700` for directories, `0600` for regular files.
  This prevents content extracted from private producer repositories
  from being readable by other local users on the same machine
  without any operator configuration. On native Windows (out of the
  Spec 006 mechanical target but supported in principle), the
  equivalent posture is an ACL granting read/write only to the
  current user; where a portable equivalent is not available, the
  system MUST fall back to the platform default and MUST NOT fail
  the sync on that basis. Existing directories and files whose
  permissions are already tighter than the required minimum MUST be
  left unchanged.

### Key Entities *(include if feature involves data)*

- **External-Harness Entry**: One producer repository's inheritance
  declaration in the consumer's `.haex-hive.json`. Carries a
  repository URL, a pinned revision, a storage name, an
  `auto_include` preset selection, an `additional_include` list, and
  an `items[]` list. The unit of trust — one entry = "consumer opts
  into this producer at this revision, under these selection
  criteria."
- **Item Declaration** (`items[]` element): An explicit inheritance
  request for one path (or one directory) inside a producer, carrying
  an item-level role (`constitution`, `workflow`, `skill`, or others
  applicable at Spec-plan time) and a required stable `as: "<alias>"`.
- **Include Match**: A file, resolved from a pinned Git tree, that
  the entry's `auto_include` preset or `additional_include` list
  selected. Every include match becomes a resolved key of the form
  `<name>:path:<repo-relative-path>`.
- **Resolved Key**: The deterministic consumer-facing identifier for
  one file (`<name>:<alias>` for explicit items, `<name>:path:<repo-
  relative-path>` for include matches). Unique across every entry in
  the consumer's `.haex-hive.local.json`.
- **Producer Clone**: The device-local full clone of one producer
  repository at `<state-area>/repos/<name>/`. Reused across all
  consumers on the device that reference the same producer under the
  same storage name. Its `remote.origin.url` is the identity
  verifier before every reuse.
- **Extract Subtree**: The per-pinned-revision content extraction
  at `<state-area>/repos/<name>/.extracts/@<sha>/…`. Populated on
  demand by `haex-init sync`; multiple pinned revisions coexist
  without conflict.
- **Device-Local Resolution Table** (`.haex-hive.local.json`): The
  gitignored file inside the consumer project that maps every
  resolved key to the absolute path of its extract. Regenerated
  atomically by `haex-init sync`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a Linux machine with SSH credentials pre-configured
  for the producer host, an operator can bootstrap a fresh consumer
  project to inherit a producer Constitution in **under three
  minutes** from `git clone` to a working agent session that quotes
  the Constitution unprompted.
- **SC-002**: `haex-init sync` on a consumer with an unchanged
  configuration and unchanged pinned state completes in **under one
  second** on typical developer hardware (no network round-trip, no
  file rewrites).
- **SC-003**: For any failure detected during `haex-init sync`,
  **100%** of runs leave the previously-published `.haex-hive.local.json`
  intact (or absent if it never existed), with no partial resolution
  table observable to any consumer of that file.
- **SC-004**: For any failure in `haex-init add-source`,
  **100%** of runs leave `.haex-hive.json` in the state that
  existed before the command was invoked.
- **SC-005**: **Zero** cases in which the same file matched by
  multiple selection mechanisms (e.g., both `auto_include` and an
  explicit `items[]` entry) appears under two different keys in
  `.haex-hive.local.json`.
- **SC-006**: **Zero** cases in which `haex-init sync` writes any
  file inside the device-local state area of a producer that shares
  a storage name with a different canonical URL. Origin verification
  must precede any reuse.
- **SC-007**: An operator running `haex-init sync` after bumping a
  pinned revision to a commit where an explicit item was renamed
  sees a clear diagnostic naming the unresolvable path within
  **five seconds** of running the command.
- **SC-008**: A consumer whose `harness_sources[]` array contains
  only Spec-004-shaped entries produces **byte-identical**
  session-start injected content before and after Spec 006 lands.
- **SC-009**: `haex-init add-source --from-repo <neighbor>`
  successfully copies a compatible external-harness entry between
  two consumers on the same device with **zero manual JSON editing**,
  provided the neighbor's config is schema-valid.
- **SC-010**: A shell test suite exercises every acceptance scenario
  from US1 through US4 against a local fixture producer, without
  network dependency, and **completes in under two minutes** on
  typical CI hardware.
- **SC-011**: Two concurrent `haex-init sync` invocations against
  the same consumer serialise cleanly: **zero** cases in which
  either invocation observes or produces a partial state.

## Assumptions

- **A1**: Producer repositories are speckit-shaped or share the
  conventional `.specify/` root layout wherever the `auto_include:
  "speckit-defaults"` preset is used. Producers that use a different
  layout are still supported via `additional_include`, but do not
  benefit from the preset.
- **A2**: Producer repositories are small enough (< 500 MB
  full-history estimate) that full clones are acceptable disk-wise.
  Larger producers can adopt shallow-clone or partial-clone opt-ins
  in a later spec.
- **A3**: Operators run `haex-init sync` after `git clone` of a
  consumer repository and after every mutation of `.haex-hive.json`
  (SHA bump, added source, changed includes). Automatic session-start
  syncing is deliberately out of scope for Spec 006; the sync moment
  is an explicit operator action.
- **A4**: Producer file renames between pinned revisions are ordinary
  consumer maintenance. `auto_include`-matched files absorb renames
  automatically (new deterministic keys appear, old ones disappear);
  explicit `items[]` entries require the operator to update `path:`.
  Aliases (`as:`) are the recommended stability mechanism for
  consumer-side wiring that survives producer rename.
- **A5**: Authentication is the operator's responsibility. The system
  provides actionable diagnostics on failure but performs no
  credential provisioning.
- **A6**: Speckit's own slash-commands read templates and workflows
  from the consumer's own working tree. Spec 006 does not swap those
  with producer content — the consumer's local speckit defaults win
  for speckit-driven commands. Producer templates/workflows remain
  agent-readable content only.
- **A7**: The device-local haex-hive state area is treated as
  regenerable persistent state, not throw-away cache. OS-level
  cache-cleanup tooling targeting the platform cache location does
  not touch it. If a manual deletion occurs, `haex-init sync`
  rebuilds it end-to-end on next invocation.
- **A8**: haex-hive itself, currently self-referencing under Spec
  004's shape, remains fully backwards-compatible after Spec 006
  lands: its `harness_sources[0]` continues to work under the same
  semantics with no config migration required.
- **A9**: Cross-platform validation for Spec 006 targets Linux
  mechanically. macOS and Windows-under-WSL2 receive smoke-test
  validation in a follow-up validation-run document and are not
  gating on the Spec 006 merge.

## Non-Goals

The following are explicitly out of scope for Spec 006 and are
deferred to later specs or explicitly not planned:

- **NG-1**: Live-catalog or spec-browsing from consumer against a
  producer (e.g., "list which specs in the producer are still open"
  invoked from inside the consumer). Operators browse by `cd`-ing
  into the producer clone or the producer repo directly.
- **NG-2**: Spec authoring from the consumer landing in the
  producer. Authoring stays in the producer repo. Strict separation
  of responsibility.
- **NG-3**: Overriding speckit's own template and workflow lookups
  with producer content. Consumer's local files win for
  speckit-driven commands.
- **NG-4**: A public-URL / `curl`-based install of `haex-init`
  itself (`--fetch-latest`). Tool distribution is a separate concern
  and belongs in a later spec.
- **NG-5**: Cache-eviction policy for the device-local state area
  or for the Spec 004 object cache. Storage remains bounded by usage
  and is regenerable; explicit eviction can be added later if
  needed.
- **NG-6**: `git worktree`-per-pinned-SHA. Multiple pinned revisions
  are handled via content-addressed extract directories, not
  multiple working trees.
- **NG-7**: Automated syncing at session start. `haex-init sync` is
  an explicit operator action; session-start reads the resolution
  table but does not itself invoke sync.
- **NG-8**: Windows-native (non-WSL2) validation. WSL2 is the
  intended Windows target for Spec 006's mechanical support; native
  Windows validation is deferred.

## Dependencies

- Spec 004 (`spec-resolve` tool, unified `harness_sources` schema)
  is a hard prerequisite. Spec 006 extends both the schema and the
  tool.
- Spec 005 (`haex-init` CLI) is a hard prerequisite. Spec 006 adds
  sub-commands (`sync`, `add-source`) and reuses the marker-block
  and gitignore-handling machinery.
- No new external system dependencies beyond what Spec 004 and 005
  established (git ≥ 2.30, Python ≥ 3.10 for CLI implementation,
  standard POSIX shell for tests).
