# Research: Multi-Spec External-Ref

**Phase**: 0 (planning)
**Spec**: [spec.md](spec.md)
**Design doc**: [`docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md`](../../docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md)

The design doc and the two-round `/speckit-specify` + `/speckit-clarify`
process resolved every scope-shaping decision. This research phase
addresses (a) the three detail-level items explicitly deferred from
`/speckit-clarify` (JSON Schema required/optional split, glob syntax
for `additional_include`, Constitution multi-source label format),
and (b) the technical implementation choices needed to bind the
design to Python-stdlib code across Linux, macOS, and Windows-under-WSL2.

---

## Decision 1 — `$HAEX_HIVE_STATE` resolution across platforms

**Decision**: `$HAEX_HIVE_STATE` resolves in this order:

1. Explicit environment variable `HAEX_HIVE_STATE` (absolute path)
2. XDG-state pattern: `${XDG_STATE_HOME:-$HOME/.local/state}/haex-hive`
   on Linux and WSL2
3. `~/Library/Application Support/haex-hive` on macOS
4. `%LOCALAPPDATA%\haex-hive` on native Windows (out of scope
   mechanically, supported semantically)

**Rationale**: XDG Base Directory Specification is the Linux
convention for regenerable-but-persistent state. macOS App-Support is
the platform-native equivalent (Apple's guidance for user-owned
application state). Windows LOCALAPPDATA is the platform-native
equivalent on Windows. The explicit override lets operators relocate
(e.g., to a large-disk mount) without patching the CLI. All four are
**per-user**, not per-project — one producer clone shared across all
consumers on the device (FR-014 origin verification).

**Alternatives considered**:

- `~/.haex-hive/` (dot-directory in `$HOME`): rejected in
  `/speckit-clarify` deliberation because it does not respect
  platform state-directory conventions (XDG on Linux especially).
- `~/.cache/haex-hive/`: rejected explicitly (D4 in design doc) —
  OS cleanup tools target `~/.cache/`.
- Per-project storage inside each consumer repo: rejected as
  duplication and drift (this is the D6 discussion in the design
  doc).

---

## Decision 2 — Directory-scoped locking mechanism (FR-025)

**Decision**: A **lockfile at `$HAEX_HIVE_STATE/repos/<name>/.sync.lock`**
opened with an OS-level advisory exclusive lock. On Unix-like systems
(Linux, macOS, WSL2), use `fcntl.flock(fd, fcntl.LOCK_EX)`. On native
Windows, use `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` in a retry loop.
Both wrapped behind a platform-detecting Python function; Python's
`platform.system()` selects the branch. Lock scope is one producer
storage `name` at a time (not the whole state area), so different
producers can sync concurrently.

**Rationale**: `fcntl.flock` is stdlib, portable across every
haex-hive target Unix, and released automatically when the process
exits. `msvcrt.locking` is the stdlib Windows equivalent. Neither
requires third-party libraries. A file inside the producer clone
directory (rather than a global lock file) means concurrent syncs
across different consumers on the same machine don't serialise if
they target different producers.

**Alternatives considered**:

- `filelock` package: rejected — third-party dependency violates
  Spec 005's stdlib-only constraint carried through Spec 006.
- Directory-existence pseudo-lock (`mkdir` succeeds iff not
  present): rejected — race between check and create, and
  stale-lock cleanup on crash is complex.
- Global lock at `$HAEX_HIVE_STATE/.sync.lock`: rejected —
  serialises unrelated producers unnecessarily.

---

## Decision 3 — Atomic file publication (FR-023, FR-024)

**Decision**: Write to a same-directory temporary file
(`.haex-hive.local.json.tmp-<pid>-<random>` for the resolution
table; `<path>.tmp-<pid>-<random>` inside each extract directory),
call `os.replace(tmp, target)` (Python stdlib) — atomic on POSIX and
Windows since Python 3.3. `os.replace` succeeds even when the target
exists; failures leave the target untouched. Best-effort cleanup of
stale `.tmp-*` siblings on `sync` startup (older than 24 h, matching
current-PID-not-alive check on Unix; on Windows, `os.stat`-based
age heuristic only).

**Rationale**: `os.replace` is the stdlib primitive with the
cross-platform atomicity guarantees FR-023/FR-024 require. Writing
into the same directory as the target avoids cross-filesystem rename
failures (`EXDEV` on Linux). Same-directory `.tmp-*` siblings
survive process crash without corrupting the target — but they
accumulate, hence the startup cleanup.

**Alternatives considered**:

- `shutil.move`: fallback-copies across filesystems, silently
  becoming non-atomic. Rejected.
- `tempfile.NamedTemporaryFile` in `/tmp/`: cross-filesystem
  rename risk. Rejected.
- Fsync-before-rename: added on top of `os.replace` inside
  finalisation, for durability (crash while writing tmp file
  loses only that partial file; crash after rename keeps
  target). Included as an implementation detail, not a separate
  primitive.

---

## Decision 4 — File-permission enforcement across platforms (FR-038)

**Decision**: On Unix-like systems (Linux, macOS, WSL2):

- `os.makedirs(mode=0o700, exist_ok=True)` for
  `$HAEX_HIVE_STATE`, `$HAEX_HIVE_STATE/repos/`,
  `$HAEX_HIVE_STATE/repos/<name>/`, and each
  `.extracts/@<sha>/` subdirectory
- `os.chmod(target, 0o600)` after each extract-file rename, if the
  file's current permissions grant any bit beyond owner
- Umask NOT changed; explicit modes override umask via `os.chmod`

On native Windows: `os.chmod` cannot express POSIX-style permissions
usefully. Rely on default LOCALAPPDATA ACL (already user-scoped by
Windows). No further hardening in Spec 006.

**Rationale**: Explicit `chmod` after write is the most portable way
to guarantee an owner-only mode regardless of umask, and honours
FR-038's "existing tighter permissions left unchanged" clause via a
pre-check. Skipping Windows ACL manipulation matches
FR-038's "MUST NOT fail the sync on that basis" fallback clause.

**Alternatives considered**:

- Setting the process umask at CLI startup: rejected — affects
  files created by external `git` subprocess calls in unpredictable
  ways.
- Using `pathlib.Path.chmod`: identical to `os.chmod`, no
  functional difference. Chose `os.chmod` for consistency with the
  existing haex-init codebase.

---

## Decision 5 — Dual-store compatibility (FR-034)

**Decision**: The Spec-004 object cache at
`${XDG_CACHE_HOME:-$HOME/.cache}/haex-hive/repos/<sha256(repo)>/`
remains the authoritative store for:

- Legacy `role: "constitution"` entries (Spec 004 shape)
- Legacy permission-only (no-role) entries (Spec 004 shape)
- Discovered `specs/*/spec-ref.json` references

New `role: "external-harness"` entries use the new state area at
`$HAEX_HIVE_STATE/repos/<name>/`. No entry is migrated. `spec-resolve
resolve` reads the legacy cache exactly as before (raw bytes to
stdout, byte-for-byte per FR-019). `spec-resolve prefetch --dry-run`
emits its established `OK`/`MISSING` lines for legacy entries and
appends the planned `external-harness` items in deterministic order.

**Rationale**: Zero migration risk (SC-008 promise: "byte-identical
session-start injected content before and after Spec 006 lands").
Two stores coexist with clean separation by entry role — no ambiguity
about which store owns which entry.

**Alternatives considered**:

- Migrate the legacy cache into `$HAEX_HIVE_STATE`: rejected —
  breaks Spec 004 shell tests' assumptions about cache paths,
  requires a one-shot migration step in `haex-init sync`, and
  offers no user-visible benefit.
- Unify by content-hash keying: rejected — legacy cache is
  bare-repo-per-URL-hash; new store is full-clone-per-safe-name.
  Different structures serve different needs (bare cache is
  minimum-fetch-set; full clone is browsable).

---

## Decision 6 — Glob syntax for `additional_include` (deferred from `/speckit-clarify`)

**Decision**: Python's `pathlib.PurePosixPath` combined with the
`fnmatch.fnmatchcase` primitive, applied against
git-tree-derived POSIX paths. Supported syntax:

- Literal file paths (`.specify/memory/constitution.md`)
- Literal directory paths (`tools/harness-evaluator/` — recursive
  expansion of every regular file underneath)
- `*` matches any character except `/` within one path component
- `**` matches any number of path components (including zero),
  case-sensitive
- `?` matches any single non-`/` character
- `[abc]` matches one of the listed characters
- Character escaping via `\` not supported (no filename in a git
  tree typically requires it)

Matching is against the pinned Git tree, obtained via `git ls-tree
-r --name-only <sha>` (or its Python-`git`-piped equivalent).
Results are sorted and deduplicated per FR-005.

**Rationale**: `fnmatch` is stdlib. `**`-support is critical for
speckit-defaults-style patterns. Case-sensitive matching is the git
tree's native semantic. POSIX paths inside the git tree are already
the storage format git uses on all platforms — no cross-platform
translation needed for match logic itself.

**Alternatives considered**:

- Full `.gitignore`-syntax parser: rejected — heavier than needed
  and imports semantics (whitelist vs blacklist) we don't want.
- Regex-only: rejected — requires operator to write regexes, worse
  DX.
- Bash-style `[!abc]` negation: rejected — `fnmatch` supports it,
  but operators unfamiliar with the syntax find it surprising;
  intentionally left undocumented.

---

## Decision 7 — Constitution multi-source label format for session-start emission (deferred from `/speckit-clarify`)

**Decision**: Between each emitted Constitution document, the
session-start snippet inserts a single line of the form:

```
--- haex-hive constitution: <source-label> ---
```

Where `<source-label>` is:

- `self` for a top-level `role: "constitution"` entry with
  `repository: "self"`
- `<repository-url>@<short-sha-8>` for a top-level
  `role: "constitution"` entry with an external repository
  (e.g., `git@gitlab.com:itemis/solutions/secana-specs.git@b2f8841`)
- `<name>:<alias>@<short-sha-8>` for a nested item inside an
  `external-harness` entry (e.g., `secana-specs:constitution@b2f8841`)

Emission order per FR-011: top-level `role: "constitution"` first,
then nested items in `harness_sources[]` array order and `items[]`
array order. Each source's raw bytes are emitted verbatim between
label lines; no content transformation.

**Rationale**: One consistent format across all sources, so
downstream readers (humans + agents) can identify which document
they are reading without scanning the content. Short-SHA suffix
disambiguates same-source-different-SHA sessions across
consumers on one device. `---` triple-hyphen prefix is a
conventional textual delimiter that does not collide with typical
Markdown headings inside a constitution.

**Alternatives considered**:

- YAML front-matter block per source: rejected — invasive for
  reader tools that expect plain text.
- No label at all (concatenated documents): rejected — makes
  reasoning about which Principle came from which source
  impossible.
- HTML comments: rejected — invisible in some tooling, which
  defeats the transparency goal.

---

## Decision 8 — JSON Schema field-level required/optional split for `external-harness` entry (deferred from `/speckit-clarify`)

**Decision**: The `external-harness` entry shape:

- **Required**: `role` (const: `"external-harness"`), `repository`
  (string, credential-free URL), `revision` (string, 40-hex-char SHA)
- **Required-with-default**: `name` (derived from `repository`
  basename if omitted, validated per FR-008)
- **Optional**: `auto_include` (string, one of the documented
  presets; defaults to none), `additional_include` (array of
  strings, defaults to `[]`), `items` (array of item objects,
  defaults to `[]`)
- **At least one non-empty inheritance mechanism required**: at
  least one of `auto_include`, `additional_include`, or `items[]`
  MUST be non-empty. An entry with no inheritance is a config
  error and refused by schema+validator combination.

Each `items[]` element:

- **Required**: `role` (item-level role — see below), `path`
  (repo-relative POSIX path), `as` (alias, `^[a-z0-9][a-z0-9-]*$`)
- Item-level `role` values recognised in Spec 006 MVP:
  `constitution`, `workflow`, `template`, `skill`, `doc`, `spec`,
  `other`. Unknown values pass schema but are treated as `other`
  (agent-readable content only). No item-level role influences
  content extraction; the role is a documentation hint for
  operator + agent.

**Rationale**: The three "must have one" mechanism keeps trivially-
empty entries out of the config. Required `repository`/`revision`
enforces Principle IV. Item-level `role` value list documents the
canonical use cases without hard-erroring unknown values — matches
haex-hive's "extend later, don't break early" posture.

**Alternatives considered**:

- Make `role` (item-level) optional: rejected — leaves the
  operator's intent unclear and complicates `items[]` linting.
- Enforce closed set of item-level roles: rejected — every
  extension would require a schema change.
- Merge `additional_include` and `items[]` into one field:
  rejected — different semantics (include is glob-expansion,
  items are individually-aliased), keeping them apart is
  clearer.

---

## Decision 9 — Git operations: subprocess vs Python-git library

**Decision**: All git operations happen via subprocess to system
`git` binary. Commands used:

- `git clone <url> <local-path>` (initial full clone; no `--depth`
  argument, no `--filter`)
- `git -C <path> fetch origin` (network refresh)
- `git -C <path> fetch origin <sha>` (targeted fetch when a pinned
  SHA is not present after a plain `fetch origin` — this happens
  when the producer pushed rewound branches, rare)
- `git -C <path> cat-file -e <sha>^{commit}` (reachability check
  before extraction)
- `git -C <path> ls-tree -r --name-only <sha>` (path enumeration
  for `auto_include` and `additional_include` expansion)
- `git -C <path> ls-tree -r --format='%(objecttype) %(path)' <sha>`
  (used to filter out symlinks/non-regular entries per FR-005)
- `git -C <path> cat-file blob <sha>:<path>` piped to the temp
  extract file (content extraction, equivalent to `git show
  <sha>:<path>`)
- `git -C <path> remote get-url origin` (origin verification per
  FR-014)
- `git -C <path> config remote.origin.url` (fallback if the
  above is unavailable in the target git version)

**Rationale**: Subprocess to `git` is Spec 004's established
pattern, works uniformly across platforms, doesn't require
third-party Python libraries (`GitPython`, `dulwich`, `pygit2` —
all rejected by the stdlib-only constraint), and always uses the
same `git` the operator uses interactively.

**Alternatives considered**:

- `git plumbing` via a Python git-object parser (dulwich): stdlib
  purity broken; also, requires re-implementing fetch protocol
  for private repositories.
- `libgit2` via `pygit2`: same objection.

---

## Decision 10 — HTTPS-credential-URL rejection semantics (FR-007)

**Decision**: URLs matching `^https?://` and containing a userinfo
component (any characters between `//` and the following `@` before
`/`) are rejected at `add-source` write time. Detection uses
`urllib.parse.urlparse` and checks the `username` and `password`
attributes of the result. The rejection error names the specific
issue ("username / password / token embedded in URL") and points at
the operator's remediation (SSH URL, or credential manager for
plain HTTPS).

**Rationale**: `urlparse` correctly handles the pathological cases
(percent-encoded credentials, IPv6-bracketed hosts, ports).
Prevention at write-time is preferable to detection-and-strip at
read-time — the operator sees the refusal immediately, no
silently-stripped credentials.

**Alternatives considered**:

- Strip credentials silently and warn: rejected — silently
  mutating operator input is exactly the kind of surprise that
  causes trust issues later.
- Regex-only detection: rejected as fragile against pathological
  URL shapes.

---

## Consolidated open items

None. Every open item flagged in Spec 006's Notes section is now
resolved. Phase 1 (data-model, contracts, quickstart) can proceed
directly from this research plus the design doc.
