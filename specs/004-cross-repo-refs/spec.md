# Feature Specification: Cross-Repo References (Phase 1)

**Feature Branch**: `004-cross-repo-refs`
**Created**: 2026-08-27
**Status**: Draft
**Input**: Land Phase 1 of the design roadmap: a portable, device-independent
mechanism for a haex-hive-opted-in repository to reference and consume
harness content pinned in another Git repository by immutable SHA. Ship as
a small resolver tool, a unified `harness_sources` shape in
`.haex-hive.json`, a canonical JSON Schema, and the enforcement logic
required by Constitutional Principles IV and V — replacing the split
`constitution` slot plus `external_sources.allowed` list left over from
Spec 003. Design authority: [docs/plans/2026-08-27-spec-004-cross-repo-refs-design.md](../../docs/plans/2026-08-27-spec-004-cross-repo-refs-design.md).

## Clarifications

### Session 2026-08-27

- Q: How does the resolver compare `repository` field values for allowlist matching and cache directory naming? → A: String-exact match (byte-identical values required; no canonicalization).
- Q: What does the resolver do when a reference's `repository` field is the literal string `"self"`? → A: `"self"` is a reserved magic keyword meaning "the repository containing this `.haex-hive.json`". The resolver reads content from the local repo via git plumbing without any network access. No other special values are recognized in `repository`; every other value is a Git repository URL.
- Q: Which URL schemes are accepted in a `repository` field? → A: Network schemes only — `https://`, `ssh://`, or SCP-style `user@host:path`. `file://`, `git://` (unencrypted), and bare local paths MUST be rejected at load-time. This enforces Principle II (device-independence) mechanically at the schema level.
- Q: When `.haex-hive.json` fails validation at session start, what work is the session permitted to do? → A: Fail-closed, whole file. ANY validation error (whole-file or per-entry) blocks the entire session from harness-governed work. The snippet surfaces the error with the offending entry, refuses to load the constitution, and refuses to start harness work. The operator MUST fix `.haex-hive.json` before proceeding.
- Q: Is `revision: "self"` a legal value? → A: No. `revision` values MUST match `^[0-9a-f]{7,40}$` only. The `"self"` keyword is `repository`-only per Q2. This tightens the design-doc's draft schema pattern which was over-permissive; the corrected pattern is authoritative for Spec 004.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fresh session in an opted-in repo resolves its pinned constitution end-to-end (Priority: P1)

An operator opens a fresh CLI session in the haex-hive repository (or any
future opted-in repo). The session-start snippet reads `.haex-hive.json`,
finds the constitution entry in `harness_sources`, verifies that the pinned
Git object is available (fetching it into the shared local cache if not),
and produces the constitution content for the session to enforce. All of
this happens without any hand-editing of paths on the local machine and
without any device-specific configuration file — the same `.haex-hive.json`
is what every device sees.

**Why this priority**: this is the load-bearing claim of Phase 1. Without
it, no opted-in repo can portably reference content from another repo, and
Principle IV's "cross-device byte-identical resolution" guarantee has no
mechanical basis.

**Independent Test**: on a freshly-cloned checkout of this repo, delete
`~/.cache/haex-hive/` if it exists, then run the updated session-start
snippet end-to-end. The snippet MUST prefetch the constitution object,
resolve it, and start harness work without prompting the operator to edit
any local path. A second run of the same snippet MUST resolve from cache
without any network activity.

**Acceptance Scenarios**:

1. **Given** a clean checkout on Linux with an empty `~/.cache/haex-hive/`
   and network access to the repository, **When** the session-start snippet
   runs, **Then** the resolver populates the cache, resolves the pinned
   constitution content, and reports readiness — with the resolved content
   byte-identical to the file at the pinned SHA.
2. **Given** the same checkout after a successful first run (cache
   populated) with network disabled, **When** the session-start snippet
   runs again, **Then** resolution succeeds entirely from cache with no
   network attempt, and reports readiness.
3. **Given** a checkout on a second Linux machine cloning the same repo
   and revision, **When** the operator runs the same snippet, **Then** the
   resolved constitution content is byte-identical to the content resolved
   on the first machine — no local path configuration involved.

---

### User Story 2 — Opted-in repo refuses to consume harness content not permitted by its `harness_sources` (Priority: P1)

The Principle V opt-in boundary is enforced mechanically. An attempt to
resolve a reference into a repository that is not permitted by any entry
in `.haex-hive.json.harness_sources` — whether via a `spec-ref.json` in a
feature directory, a direct invocation of the resolver, or an indirect
consumer — fails loudly with a message that names both the offending
reference and the missing/mismatching permission entry. No content is
returned. No local files are modified. The operator sees the refusal in
the same shape whether the attempt came from a snippet step or a manual
command.

**Why this priority**: Principle V is NON-NEGOTIABLE and this is its
mechanical enforcement point. The wording in the constitution is only
authoritative if the tool it points at actually refuses. Test 3.2 in
Spec 001 already exercised the intent at the wording level; Spec 004
provides the code that enforces the wording for every kind of
reference, not just the constitution slot.

**Independent Test**: in a scratch working tree derived from a clean
checkout, place a `spec-ref.json` under `specs/<any>/spec-ref.json`
pointing at a real external repository (e.g. `secana-specs`) at a real
SHA with `harness_sources` set to permit only `self`. Invoke
`spec-resolve resolve` on that reference. Result MUST be a non-zero
exit code, a stderr message that names the offending repo/SHA/path and
identifies the missing permission entry, and zero file writes anywhere
under the working tree. Repeat with each of the four allowlist shapes
in play and verify each mismatch fails with an equally specific message.

**Acceptance Scenarios**:

1. **Given** `harness_sources` containing only the `role: "constitution"`
   entry pointing at `self`, **When** the resolver is asked to fetch any
   non-`self` reference, **Then** it refuses with a message naming the
   reference and the missing permission entry, and no file is written.
2. **Given** a permission-only entry with a specific `revision`, **When**
   the resolver is asked to fetch a reference into the same repo at a
   different SHA, **Then** it refuses with a message naming both SHAs.
3. **Given** a permission-only entry with a `paths` list, **When** the
   resolver is asked to fetch a reference to a path not in the list at
   an otherwise-permitted repo/SHA, **Then** it refuses with a message
   naming the requested path and the permitted set.
4. **Given** a `role`-carrying entry that names a specific repo/SHA/path,
   **When** the resolver is asked to fetch that exact reference, **Then**
   it succeeds — the role entry is self-permitting, no separate
   permission-only entry is required.

---

### User Story 3 — Malformed or unknown-role `.haex-hive.json` is rejected before harness work starts (Priority: P2)

An operator introduces an invalid change to `.haex-hive.json` — an unknown
`role` value, a permission-only entry with a `path` field (forbidden by
the entry-shape rules), a role-carrying entry missing `revision`, or a
malformed SHA. The resolver detects the problem the next time it is
invoked (which happens as part of the session-start snippet) and refuses
with a message that pinpoints the offending entry. The operator is not
left in a state where the session appears to start correctly and only
fails partway through a task.

**Why this priority**: the config file is the single source of truth for
the repo's harness identity and permissions. Silent partial acceptance of
a malformed config would let an operator work under a false assumption
about what is or isn't permitted, defeating Principle V's mechanical
enforcement. P2 rather than P1 because Story 2's refusal path handles
the load-bearing "external content refused" case; Story 3 covers the
adjacent "config itself is broken" surface.

**Independent Test**: for each of a curated set of malformed configs
(unknown role, forbidden field combination, malformed SHA, missing
required key), invoke the resolver and verify a non-zero exit code plus
a stderr message that names the specific problem and the offending entry
by array index or `role` value.

**Acceptance Scenarios**:

1. **Given** `.haex-hive.json` with a `harness_sources` entry whose
   `role` is not in the current role enum, **When** the resolver runs,
   **Then** it refuses with a message naming the unknown role value and
   the entry's array index, and lists the valid values.
2. **Given** a permission-only entry that carries a `path` (singular),
   **When** the resolver runs, **Then** it refuses with a message
   explaining that `path` is reserved for role-carrying entries and
   permission-only entries use `paths` (plural).
3. **Given** a role-carrying entry missing `revision` or `path`,
   **When** the resolver runs, **Then** it refuses naming which
   required field is absent.
4. **Given** any entry whose `revision` does not match the SHA pattern
   (`self` or 7-40 hex chars), **When** the resolver runs, **Then** it
   refuses naming the invalid value.

---

### User Story 4 — Editors validate `.haex-hive.json` against a canonical schema (Priority: P3)

An operator editing `.haex-hive.json` in their IDE (VSCode or JetBrains
family) gets autocomplete on field names and `role` values, and inline
errors on typos or forbidden field combinations, without running any
haex-hive command. The schema file that drives this is committed at a
known location and is the same schema the resolver's built-in checks
mirror.

**Why this priority**: catches errors before they reach the resolver's
runtime check. Real convenience, real prevention of a class of mistakes,
but not load-bearing — Story 3 already catches the same problems at
runtime.

**Independent Test**: with the operator's editor configured per the
`docs/spec-resolve.md` instructions, introduce each of Story 3's
malformed samples into `.haex-hive.json`. The editor MUST highlight the
error inline before saving; the message MUST be specific enough to
identify the field and the constraint violated.

**Acceptance Scenarios**:

1. **Given** the schema file exists and is mapped in the operator's
   editor, **When** the operator types `"role": "cons"` in an entry,
   **Then** autocomplete offers `constitution` and the incomplete value
   is flagged as an enum mismatch.
2. **Given** the same mapping, **When** the operator adds a `path` field
   to a permission-only entry, **Then** the entry is flagged as
   violating the forbidden-field-combination constraint.

---

### Edge Cases

- **Network unreachable on first run, cache empty**: the resolver refuses
  to start harness work and surfaces the failure with actionable text
  (which repo, which SHA, which network operation failed). No silent
  degradation to a partial state.
- **Cache directory exists but is corrupted** (e.g. partial pack file):
  the resolver treats this as a cache miss for the affected SHA, refetches
  from the remote if the network is reachable, and refuses cleanly if not.
- **Two entries in `harness_sources` permit the same reference**: the
  first matching entry wins; resolution succeeds. No error, no ambiguity
  report — the array order is authoritative.
- **`harness_sources` array is empty**: the resolver refuses every
  reference including `self`, matching Principle V's "empty allowlist =
  no external content" wording extended to include the local repo — this
  is intentional: a repo that intends to opt in MUST declare its
  constitution entry.
- **`harness_sources` array is absent from `.haex-hive.json`**: config
  is invalid per the JSON Schema; the resolver refuses via Story 3's
  path.
- **A reference resolves to an empty file**: success is empty content;
  the resolver does not treat empty content as an error. The consuming
  layer (e.g. the constitution loader) is responsible for its own
  content-shape validation.
- **The pinned SHA exists in the local cache but was fetched from a
  different repository URL**: the cache is content-addressed by SHA;
  the same SHA from two URLs is treated as one object, matching Git's
  own semantics. Cross-URL collisions are impossible without a SHA
  break.
- **Snippet is triggered in a repo without `.haex-hive.json`**: the
  detection step of the snippet (existing from Spec 003) exits early
  and the resolver is never invoked. No behavior change from Spec 003
  for non-opted-in repos.

## Requirements *(mandatory)*

### Functional Requirements

**Data model:**

- **FR-001**: `.haex-hive.json` MUST carry a top-level `harness_sources`
  array whose entries are either role-carrying (concrete pointer with
  `role`, `repository`, `revision`, `path`) or permission-only (scope
  entry with `repository` and optional `revision` and `paths`). The
  `repository` field accepts either a Git repository URL or the reserved
  magic keyword `"self"`; no other special values are recognized.
  Accepted URL schemes: `https://`, `ssh://`, and SCP-style
  `user@host:path`. `file://`, `git://` (unencrypted), and bare local
  paths MUST be rejected at load-time with a validation error. This
  restriction is enforced at both the JSON Schema layer (FR-016) and
  the resolver's built-in checks (FR-017).
- **FR-002**: The system MUST NOT retain a separate top-level
  `constitution` slot in `.haex-hive.json`. The constitution reference
  lives as a `role: "constitution"` entry in `harness_sources`.
- **FR-003**: A role-carrying entry MUST carry `role`, `repository`,
  `revision`, and `path` (single); it MUST NOT carry `paths` (plural).
- **FR-004**: A permission-only entry MUST carry `repository`, MAY carry
  `revision` and `paths`, and MUST NOT carry `role` or `path`.
- **FR-005**: The Phase 1 role enum MUST contain exactly the value
  `constitution`. Any other `role` value is invalid.
- **FR-006**: `revision` values in any entry MUST match the pattern
  `^[0-9a-f]{7,40}$` — a 7-to-40-character lowercase hexadecimal string
  only. The `"self"` keyword is `repository`-only (per FR-001); it is
  NOT a legal `revision` value. Any `revision: "self"` MUST be rejected
  at load-time. (This tightens the over-permissive pattern
  `^(self|[0-9a-f]{7,40})$` drafted in the design doc; Spec 004's FR-006
  is authoritative.)

**Resolution and enforcement:**

- **FR-007**: The system MUST provide a resolver tool (`spec-resolve`)
  that reads a reference (`repository + revision + path`) and returns
  the file content pinned at that SHA. When `repository == "self"`, the
  resolver MUST read content from the local repository containing the
  invoking `.haex-hive.json` via git plumbing (e.g. `git show <sha>:<path>`)
  and MUST NOT attempt any network operation. If the pinned SHA is not
  present in the local object database, the resolver MUST refuse with a
  message naming the missing SHA — never fall back to a remote fetch
  under `"self"` semantics.
- **FR-008**: The resolver MUST refuse any reference not permitted by
  at least one entry in the calling repo's `harness_sources`. Refusal
  MUST name both the offending reference and the missing/mismatching
  permission scope. `repository` values MUST be compared byte-identically
  — no canonicalization (no stripping of `.git`, no SSH↔HTTPS normalization,
  no host-case folding). If the operator wants two URL forms of the same
  underlying repo permitted, they MUST declare two entries.
- **FR-009**: A role-carrying entry MUST implicitly permit its own
  reference. No separate permission-only entry is required to authorize
  a role entry's exact reference.
- **FR-010**: When multiple entries could permit the same reference,
  the first matching entry in array order MUST be authoritative. Order
  is meaningful and preserved by the tool.
- **FR-011**: The resolver MUST provide subcommands `resolve`,
  `prefetch`, and `status`. `resolve` returns content for a reference.
  `prefetch` warms the cache for every reference discoverable in the
  repo. `status` prints a compact summary suitable for embedding in the
  session-start snippet, drawn only from cache metadata (no network).
- **FR-012**: The resolver MUST NOT ship `check-updates` or `bump`
  subcommands in Spec 004. Update-detection and update-application are
  Spec 005 scope.

**Cache:**

- **FR-013**: The resolver MUST cache Git objects in an XDG-compliant
  per-user location by default (`~/.cache/haex-hive/repos/` on Linux,
  honoring `$XDG_CACHE_HOME` if set). Cache contents MUST NOT contain
  device-specific paths or secrets.
- **FR-014**: Multiple opted-in repos on the same device MUST share
  one cache entry per external repository. Deduplication is by stable
  hash of the byte-identical `repository` value from the reference
  (matching FR-008's exact-match rule). Two different URL forms of the
  same underlying repo therefore produce two separate cache directories
  — accepted duplication cost, in exchange for zero canonicalization
  ambiguity.
- **FR-015**: Deleting the cache directory MUST NOT corrupt any
  opted-in repo's state; the next resolver invocation MUST repopulate
  it from remotes.

**Schema:**

- **FR-016**: The system MUST commit a canonical JSON Schema at
  `.specify/schemas/haex-hive.schema.json` that describes the full
  shape of `.haex-hive.json` including the `role` enum and the
  role-vs-shape entry constraints.
- **FR-017**: The resolver MUST validate every loaded `.haex-hive.json`
  against the same constraints the schema expresses. When the schema
  and resolver disagree on any curated valid/invalid sample, the
  system MUST be considered non-conforming until they agree. Any
  validation error (whether whole-file such as malformed JSON or missing
  required top-level key, or per-entry such as unknown role or forbidden
  field combination) MUST cause the resolver to reject the entire config
  — no partial acceptance, no "valid subset" mode.
- **FR-018**: Extending the `role` enum in a future phase MUST be a
  PATCH-level change to the constitution (widening only, never
  removing values).

**Consolidation and constitution:**

- **FR-019**: `.specify/system.yaml` MUST be removed. Its content
  moves into `.haex-hive.json.harness_sources` as part of Spec 004's
  landing commit.
- **FR-020**: Principle V's wording MUST cite `.haex-hive.json`'s
  `harness_sources` array rather than `.specify/system.yaml`'s
  `external_sources.allowed` list. The constitution version stamp
  MUST bump from v1.1.0 to v1.1.1 (PATCH — pure wording refresh, no
  principle removed, added, or relaxed).
- **FR-021**: An ADR under `docs/adr/` MUST record the rename
  (`external_sources` → `harness_sources`) and the shape unification
  (split `constitution` + `external_sources.allowed` collapsed into
  one array), so that future readers of the constitution can trace
  the wording change to its motivation.

**Snippet integration:**

- **FR-022**: The Spec 003 global snippet MUST gain a step that
  invokes `spec-resolve status` (or an equivalent readiness check)
  after reading `.haex-hive.json` and before starting harness work.
  If any pinned reference is unresolvable and the network is
  reachable, the snippet MUST run `spec-resolve prefetch` before
  proceeding; if a reference is unresolvable with no network, the
  snippet MUST refuse to start harness work and surface the failure.
  If `.haex-hive.json` itself fails validation (FR-017), the snippet
  MUST refuse the entire session's harness-governed work — no partial
  degradation, no "load what you can". The operator sees a clear
  message naming the offending entry and MUST fix the file before any
  harness enforcement resumes.
- **FR-023**: The staleness indicator emitted by the snippet at
  session start MUST be drawn from cache metadata only. No network
  call at session start is permitted for the staleness display.

**Testing:**

- **FR-024**: The system MUST include synthetic Git-fixture tests
  covering: happy-path resolve, refusal for each of the four
  allowlist entry shapes, SHA mismatch, path mismatch, malformed
  reference, cache-miss with network available, and cache-miss with
  network unavailable.
- **FR-025**: The system MUST include a curated valid/invalid
  sample set for `.haex-hive.json` such that the schema and the
  resolver's built-in checks are demonstrated to agree on each.
- **FR-026**: The system MUST include one documented manual smoke
  test resolving a real external SHA (e.g. from a real secana-specs
  commit) in a scratch checkout — deliberately NOT in this repo's
  own `.haex-hive.json` — to prove that `git fetch <repo> <sha>` and
  content extraction work end-to-end against real remotes.

**Documentation:**

- **FR-027**: The system MUST document (in `docs/spec-resolve.md` or
  the project README) the resolver's command surface, cache
  location, JSON Schema location and editor-mapping instructions,
  and the process a downstream consuming repo follows to wire an
  external harness source into its own `harness_sources`.

### Key Entities

- **`.haex-hive.json`**: the per-repo opt-in marker plus canonical
  location for the `harness_sources` array and any other repo-scoped
  haex-hive metadata. Owned by the repo; committed.
- **`harness_sources` entry**: one element of the array. Either a
  role-carrying concrete pointer or a permission-only trust scope.
- **`spec-ref.json`** (documented escape hatch): an optional
  feature-scoped file at `specs/<feature>/spec-ref.json` mapping
  names to reference triples for features that need to pin external
  content for their own work.
- **`haex-hive.schema.json`**: canonical JSON Schema describing
  `.haex-hive.json`'s shape. Committed at
  `.specify/schemas/haex-hive.schema.json`.
- **`spec-resolve`**: the resolver CLI tool. Committed at
  `.specify/scripts/spec-resolve` (executable).
- **Object cache**: per-user Git object store under
  `~/.cache/haex-hive/repos/<repo-hash>/`. Owned by the operator's
  device; not versioned; safe to delete.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh clone of the haex-hive repository, run through
  the updated session-start snippet on a machine with an empty cache
  and network access, reaches "ready to work" state (constitution
  resolved, harness enforcement active) with zero device-specific
  path configuration required.
- **SC-002**: A repeat run of the same snippet on the same machine
  with the network disabled succeeds without any network attempt,
  as observed by monitoring network activity during the run.
- **SC-003**: Two operators running the snippet against the same
  repository commit on two Linux machines get byte-identical
  resolved constitution content, verified by hashing both outputs.
- **SC-004**: For every malformed sample in the curated invalid
  set, the resolver refuses with an error message that a first-time
  reader of the message can act on without consulting external
  documentation — measured by inspection during review, not by
  runtime metric.
- **SC-005**: For every valid/invalid sample in the curated set,
  the JSON Schema and the resolver agree on accept/reject in 100%
  of cases.
- **SC-006**: With `harness_sources` containing only the
  `role: "constitution"` self-entry, every attempt to resolve a
  non-`self` reference is refused; 100% of the four allowlist
  shapes exercised by the fixture tests hit their intended refusal
  path.
- **SC-007**: The constitution's version stamp is v1.1.1 upon
  Spec 004 landing, and every reference to the old
  `.specify/system.yaml` path in constitutional wording is
  replaced.
- **SC-008**: `git grep external_sources` on the landing commit
  returns matches only in historical files (ADRs, this spec's
  design doc, superseded validation notes).

## Assumptions

- **Platform**: primary validation happens on Linux. macOS and
  Windows/WSL2 validation are deferred to when a real satellite of
  that class exists (matching the design plan's deferral of WSL2
  validation for the same reason). Spec 004 ships a written
  cross-OS test plan so the eventual validation is a well-defined
  follow-up, not a fresh design exercise.
- **Python runtime**: `python3` (3.10+) is available in the
  session's execution environment. This matches the design plan's
  Nix-first direction (Phase 3) without requiring Nix in Phase 1.
- **Git runtime**: `git` (2.30+) is available in the session's
  execution environment. Older Git versions may lack partial-clone
  filters or SHA-refspec fetch; if encountered, the tool falls back
  to a full fetch.
- **No external harness source is wired into this repo's own
  `harness_sources`**. The mechanism is validated by fixtures and
  one scratch smoke test — deliberately keeping haex-hive isolated
  from itemis-internal content per Principle V's spirit.
- **The consumer of the resolver's output** (initially, the
  constitution-loading path in the session-start snippet) is
  responsible for its own content-shape validation. `spec-resolve`
  guarantees byte-identical content at a pinned SHA; it does not
  guarantee that the content is a well-formed constitution.
- **Editor JSON-Schema mapping**: Spec 004 documents mapping
  instructions for the two mainstream editor families (VSCode,
  JetBrains) but does not automate the mapping — the operator
  configures their own editor once per device. Automating this
  would belong to a Phase 2/3 tooling layer.
- **`identity` / `identity_note`** in `.haex-hive.json` remain
  as-is; Spec 004 does not change their semantics or placement.
- **`groups` and `active_feature`** in `.haex-hive.json` remain
  as-is; both are outside Spec 004's scope.
