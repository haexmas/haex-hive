# Spec 006 — Multi-Spec External-Ref: Design

**Status**: Draft (design brainstorming from 2026-08-28 session)
**Author**: haex-hive constitution v1.2.0 process
**Related**: [Spec 004 — Cross-Repo References](../../specs/004-cross-repo-refs/spec.md);
[Spec 005 — haex-init CLI](../../specs/005-haex-init/spec.md);
[Roadmap Phase 1](2026-08-26-haex-hive-design.md#L458-L469);
[ADR 0005 — Unified `harness_sources`](../adr/0005-unify-harness-sources-and-drop-system-yaml.md);
[Constitution §Principle IV, V](../../.specify/memory/constitution.md)

## Problem

Spec 004 shipped the mechanism for a consumer to reference **one**
external harness entry at a pinned SHA (the constitution). Spec 005
shipped the CLI to bootstrap this for a fresh project. The concrete
adoption case Spec 004+005 unblocked was **haex-hive as its own
consumer** (self-ref) — a single-repo Phase 1 demonstration.

The real Phase 1 acceptance test is **another repo consuming
haex-hive-style harness content from a shared producer repo**. The
concrete case:

- **Producer**: `secana-specs` (private GitLab repo, itemis-internal,
  speckit-shaped: has `.specify/memory/constitution.md`,
  `.specify/workflows/`, `.specify/templates/`, `.specify/schemas/`,
  `tools/harness-evaluator/`, `tools/spec-number-guard/`, and 20+
  numbered feature specs under `specs/`)
- **Consumer**: `secure-web-frontend` (Vue/React frontend, currently
  not haex-hive-managed at all, existing `CLAUDE.md` + `GEMINI.md`,
  multi-remote setup)

Spec 004/005's config shape cannot express this today:

- Only one `harness_sources` entry is expected (the constitution)
- No mechanism to inherit multiple items from one producer without
  N × SHA duplication
- No mechanism to auto-flow the speckit-conventional content
  (`.specify/**` subtree) as a group
- No CLI ergonomics for adding sources to `.haex-hive.json` — the
  operator has to hand-edit JSON, which is fragile

Spec 006 fixes all four.

## Non-Goals (bounded up-front)

Explicitly out of scope for Spec 006:

- **Live catalog / spec browsing from consumer.** No feature like
  "from `secure-web-frontend`, list which specs in `secana-specs` are
  open." If the operator wants to browse, they `cd
  ~/.haex-hive/repos/secana-specs/` or into the producer clone
  directly. Deferred to a future spec (candidate Spec 008 territory).
- **Spec creation from the consumer landing in the producer.** No
  feature like "from `secure-web-frontend`, run `/speckit-specify`
  and have the new spec land in `secana-specs`." Spec authoring
  stays inside the producer repo (strict separation of
  responsibility, decided in brainstorm).
- **Speckit template / workflow swapping.** Speckit's own
  slash-commands (`/speckit-specify`, `/speckit-plan`, etc.) read
  files from paths under `.specify/templates/` and `.specify/workflows/`
  in the consumer's own working tree. Spec 006 does NOT replace or
  redirect those with producer content — the consumer's local speckit
  defaults win for speckit-managed workflows. Producer's templates/workflows
  ARE inheritable as content (agents can read them), but they don't
  drive speckit's own commands.
- **`--fetch-latest` / curl-based install of `haex-init` itself.**
  That is the Spec 007 (or later) territory — tool distribution, not
  reference resolution.
- **Cache eviction policy** — deferred from Spec 004, still deferred.
  Disk usage per pinned SHA is bounded and small for spec repos.
- **`git worktree`-per-pinned-SHA**. Multiple pinned SHAs are handled
  via content-addressed extract directories (see Storage below),
  not multiple working trees.

## Design decisions (numbered for reference)

### D1. Consumer-side selection is authoritative (Principle V)

The consumer's `.haex-hive.json` is the single trust-boundary
declaration. Producer-side manifests were explicitly rejected in
brainstorming — we cannot expect arbitrary producers to adopt
haex-hive conventions on their side. All selection semantics live
consumer-side.

### D2. One `harness_sources` entry per producer repo, with `items[]`

The Spec-004 shape (`{ role, repository, revision, path }` — one item
per entry) is generalized to `{ role: "external-harness", repository,
revision, auto_include, additional_include, items[] }`. Single-SHA
pin per producer, multiple items inside. Avoids N-fold SHA duplication
when a consumer inherits multiple things from one producer.

### D3. Coarse `auto_include: "speckit-defaults"` preset

For speckit-shaped producers (any repo with a `.specify/` root),
consumer can say `auto_include: "speckit-defaults"` and inherit a
fixed set of paths without hand-listing them:

- `.specify/memory/**`
- `.specify/workflows/**`
- `.specify/templates/**`
- `.specify/schemas/**`

Content **outside** `.specify/` (root `CLAUDE.md`, `tools/`,
`docs/`, etc.) is opt-in via `additional_include` — the consumer
lists paths / globs explicitly.

Not in speckit-defaults (rationale): `.specify/scripts/`,
`.specify/extensions/`, `.specify/integrations/` are producer-repo-internal
infrastructure (like `haex-init` and `spec-resolve` inside haex-hive
itself); they run on the operator's machine, they are not consumer-shared
content by design.

### D4. Full clone at `~/.haex-hive/repos/<name>/`

Producer repos are cloned in full (no `--depth=1`) to
`~/.haex-hive/repos/<producer-name>/`. This location is
**state**, not cache — semantically distinct from `~/.cache/` (which
OS cleanup tools may wipe).

Rationale:
- Spec repos are small (secana-specs full history estimated < 50 MB)
- `--depth=1` complicates multi-SHA resolution (would need
  server-side `uploadpack.allowAnySHA1InWant`, not portable)
- Full clone lets `git show <any-sha>:<path>` succeed without
  additional fetches

Working tree stays at the producer's default-branch tip (updated
by `haex-init sync`), for `cd + browse` operator ergonomics. This
tree is **NOT** what consumers read — they read via extracts (see D5).

### D5. Content-addressed extracts per pinned SHA

Under `~/.haex-hive/repos/<name>/.extracts/@<sha>/…`, `spec-resolve`
writes the extracted file content for pinned SHAs on first access.
Subsequent reads follow the stable filesystem path. Structure:

```
~/.haex-hive/repos/secana-specs/
├── .git/                              # full history
├── .specify/…                          # working tree at HEAD (browse only)
├── specs/…
├── tools/…
└── .extracts/
    ├── @b2f884158dc90fbd4ab956f00ee100a82b6ec3eb/
    │   └── .specify/memory/constitution.md
    └── @<other-sha>/
        └── ...
```

Extract paths are stable and Windows-portable (real files, no
symlinks). Multiple consumers pinning different SHAs of the same
producer coexist without conflict — each SHA has its own extract
subtree.

### D6. Path-Return via `.haex-hive.local.json` (device-local, gitignored)

`spec-resolve resolve <ref>` returns absolute filesystem paths into
`~/.haex-hive/repos/<name>/.extracts/@<sha>/…`.

The consumer repo has a device-local `.haex-hive.local.json`
(gitignored), populated by `haex-init sync`, which maps consumer-facing
refs (aliases) to those absolute paths:

```json
{
  "generated_from_config": "sha256:...",
  "generated_at": "2026-08-28T14:23:00Z",
  "device": "haex-linux-desktop",
  "resolved": {
    "secana-specs:constitution": "/home/haex/.haex-hive/repos/secana-specs/.extracts/@b2f8841.../.specify/memory/constitution.md",
    "secana-specs:plan-review-workflow": "/home/haex/.haex-hive/repos/secana-specs/.extracts/@b2f8841.../.specify/workflows/plan-review.md",
    "secana-specs:harness-evaluator": "/home/haex/.haex-hive/repos/secana-specs/.extracts/@b2f8841.../tools/harness-evaluator/"
  }
}
```

Consumer-side tooling (session-start snippet, agent-side reads,
haex-hive-aware code) reads paths from this table. **No content is
duplicated inside the consumer repo.** Drift is impossible — there is
one source of content-truth (the clone).

### D7. Windows portability requires no symlinks, no bind mounts

Symlinks require Admin/Developer Mode on Windows and are inconsistent
across git. Junctions work only for directories. Bind mounts require
root. All three are rejected. Spec 006 uses only regular files and
paths — cross-platform by construction.

### D8. Speckit-owned files are NOT inherited into consumer's speckit

Consumer's own `.specify/templates/**` and `.specify/workflows/**`
remain the source-of-truth for the consumer's own speckit tooling.
Producer content in those paths is available as CONTENT (an agent can
Read the extracted path from the resolution table) but does not
override speckit's local lookups.

Rationale: speckit hard-codes local relative paths for its own
templates/workflows; overriding them cross-repo requires either
symlinks (rejected D7), copy (rejected because of drift and
duplication), or forking speckit (out of scope). Consumer-side spec
authoring uses consumer-side templates, or the operator `cd`s to the
producer repo for authoring there.

### D9. Rename semantics — fail-loud + `as:` alias as best practice

If a pinned path in an explicit `items[]` entry is unresolvable at a
new pinned revision (renamed, moved, or removed in producer), `haex-init
sync` refuses to overwrite `.haex-hive.local.json` and prints:

> The pinned path `<path>` in `<repo>` does not exist at revision
> `<new-sha>`. Either update `path:` in `.haex-hive.json`, revert
> `revision:`, or remove this item. `.haex-hive.local.json` retains
> the previous resolution.

For `auto_include` (glob-based), renames are absorbed transparently —
new SHA's file listing is the new set, no config action required.

Best-practice: consumer-side wiring uses `as: "<alias>"` on explicit
items. Consumer code references the alias (`secana-specs:plan-review`),
NOT the raw path. When the producer renames, the operator updates
`path:` once; the alias stays and downstream code is unaffected.

### D10. Auth failures surface with actionable errors

Consumer clones/fetches use the operator's ambient SSH/HTTPS
credentials. No credential provisioning is scoped to Spec 006 (out of
scope: keyring integration, deploy keys). The tool MUST surface auth
failures with a clear, actionable diagnostic:

- SSH: "cannot connect to `<host>` — verify with `ssh -T git@<host>`"
- 403: "no read access to `<repo>` — check that this account has
  access, or `git credential-manager` state on this device"
- Network: "cannot reach `<host>` — check network / VPN"

Error surface is part of the CLI contract, tested in shell tests
alongside the success paths.

## Data model — `.haex-hive.json` after Spec 006

### JSON Schema outline

The `harness_sources[]` entry evolves to a discriminated shape by
`role`:

- **`role: "constitution"`** — the Spec 004 single-item shape;
  backwards-compatible. Still valid.
- **`role: "external-harness"`** — new. Multi-item container per
  producer repo (see below).

### `role: "external-harness"` entry

```json
{
  "role": "external-harness",
  "repository": "git@gitlab.com:itemis/solutions/secana-specs.git",
  "revision": "<40-char-full-SHA>",
  "name": "secana-specs",

  "auto_include": "speckit-defaults",

  "additional_include": [
    "CLAUDE.md",
    "tools/harness-evaluator/",
    "specs/023-obfuscate-snapshot-migration/"
  ],

  "items": [
    {
      "role": "workflow",
      "path": ".specify/workflows/plan-review.md",
      "as": "plan-review-workflow"
    }
  ]
}
```

Field semantics:

- **`repository`**: git remote URL (SSH or HTTPS). Determines the
  clone target under `~/.haex-hive/repos/<name>/`.
- **`revision`**: full 40-character git commit SHA. Immutable per
  Principle IV.
- **`name`**: local storage name (default: derived from repository URL
  basename). Determines the directory name under
  `~/.haex-hive/repos/`. Allows multiple entries for the same URL if
  needed (rare).
- **`auto_include`**: either `"speckit-defaults"` (D3 preset) or `null` /
  omitted (no auto-include, only explicit items).
- **`additional_include`**: array of paths / globs OUTSIDE the
  speckit-defaults set. Each entry is a directory or file path
  relative to the producer repo root.
- **`items`**: array of explicit item entries with individual `role`,
  `path`, and optional `as:` alias. For content that needs a stable
  consumer-facing name.

Multiple `external-harness` entries in `harness_sources[]` allowed —
consumer can inherit from multiple producers.

## Storage layout — `~/.haex-hive/`

```
~/.haex-hive/
├── repos/
│   ├── secana-specs/
│   │   ├── .git/                              # full history clone
│   │   ├── .specify/…                          # working tree at HEAD
│   │   ├── specs/…
│   │   ├── tools/…
│   │   └── .extracts/@<sha>/…                 # per-pinned-SHA extracts
│   └── <other-producer>/
│       └── …
└── (future: registry, config, etc.)
```

`~/.haex-hive/` semantically is "haex-hive persistent state". OS
cleanup tools targeting `~/.cache/` leave it alone. If manually
deleted, `haex-init sync` on next run regenerates it.

## Command surface

### `spec-resolve` extensions

Existing commands:

- `spec-resolve resolve <ref>` — returns absolute path (unchanged
  contract, now includes `.extracts/@<sha>/…` under the hood)
- `spec-resolve prefetch` — populates the local store; extended to
  handle multi-item entries and `auto_include`
- `spec-resolve status` — extended to summarize `.haex-hive.local.json`
  freshness (SHA of source config vs regenerated table)

New commands:

- `spec-resolve regenerate` — writes `.haex-hive.local.json` from
  `.haex-hive.json` + current extracts state. No network required.
  Called internally by `haex-init sync` after clone/fetch.

### `haex-init sync` (new sub-command)

Called by the operator after `git clone <consumer-repo>` or after
modifying `.haex-hive.json` (SHA bump, added source, etc.). Steps:

1. Read `.haex-hive.json`; validate against schema.
2. For each `external-harness` entry:
   a. Ensure `~/.haex-hive/repos/<name>/` exists (clone if missing).
   b. `git fetch origin` to ensure pinned revision is reachable.
   c. Refuse loudly if pinned revision is not reachable.
3. For each item (including auto-include expansions), extract content
   to `.extracts/@<sha>/<path>` if not present.
4. Rename check: if any explicit item's `path:` does not exist at
   pinned revision, print structured error, refuse to write
   `.haex-hive.local.json`, exit non-zero.
5. Write `.haex-hive.local.json` (device-local, gitignored, replaces
   in place).
6. Append `.haex-hive.local.json` to consumer's `.gitignore` inside a
   `haex-init`-managed marker block (per Spec 005 marker-block
   conventions).

Flags:

- `--dry-run` — compute + print action plan without writing (mirrors
  Spec 005 pattern)
- `--yes` — auto-confirm prompts (non-TTY safe)

### `haex-init add-source` (new sub-command, US4 P3)

Called by the operator to add an `external-harness` entry
interactively:

```
haex-init add-source [--from-repo <path>] [--url URL] [--revision SHA]
```

Modes:

- **From-scratch**: prompts for `repository`, `revision` (resolves
  from remote at prompt time), `name`, `auto_include` preset,
  `additional_include`, and initial `items[]`.
- **`--from-repo <path>`**: reads a neighbor consumer's
  `.haex-hive.json` and offers to copy an existing `external-harness`
  entry (adjusted for the current repo). Solves the DX-Wunsch of
  low-friction propagation to new consumers.

Post-add: automatically triggers `haex-init sync` (unless
`--no-sync`).

Validation:
- Refuses if `revision` is not a full 40-character SHA
- Refuses if the target repo has schema-invalid `.haex-hive.json`
- Refuses if an entry with the same `repository` already exists
  (operator uses `--replace` or manually edits)

## `.haex-hive.local.json` shape (device-local, gitignored)

```json
{
  "haex_hive_local_version": "1",
  "generated_from_config": "sha256:<hash-of-.haex-hive.json>",
  "generated_at": "2026-08-28T14:23:00Z",
  "device": "<hostname or persistent device id>",
  "resolved": {
    "<producer-name>:<alias>": "<absolute path in ~/.haex-hive/repos/…/.extracts/@<sha>/…>"
  }
}
```

Consumers of this table:

- Session-start snippet (in `~/.claude/CLAUDE.md`, `~/.codex/…`,
  `~/.gemini/…`) — reads the constitution ref, injects into session
- Agent-side reads (any code that needs an inherited file)
- Future haex-hive-aware tooling

Not consumed by: speckit itself (D8), external CI, arbitrary editor
plugins.

## User stories (P1 → P3, mirrors Spec 005 pattern)

### US1 (P1 🎯 MVP) — Fresh consumer inherits Constitution from a producer

**As** an operator with a not-yet-haex-hive-managed project
**I want** to run `haex-init` once, add secana-specs as an
`external-harness` source with only its constitution referenced, and
**expect** agent sessions in this project to see secana-specs'
constitution as their governing rules.

**Independent test**: on a clean checkout of `secure-web-frontend`,
run `haex-init` + `haex-init add-source` for `secana-specs` +
`haex-init sync`. Open a Claude Code session in the project. Session
start reads the constitution via `.haex-hive.local.json` → path in
`.extracts/@<sha>/`. Agent quotes a specific Principle from the
producer constitution unprompted.

### US2 (P2) — Consumer inherits skills / docs / additional_include

**As** an operator
**I want** to inherit not just the constitution but also a chosen
subset of producer content (skills, docs, specific specs), listed via
`auto_include` + `additional_include`
**so that** the agent can read a skill from secana-specs
(`tools/harness-evaluator/`) or a specific spec
(`specs/023-…/spec.md`) as if it were local.

**Independent test**: after US1 setup, extend the `external-harness`
entry with `additional_include: ["tools/harness-evaluator/"]`, run
`haex-init sync`. Agent successfully reads the extracted path (via
Path-Return) for the harness-evaluator skill.

### US3 (P2) — SHA-bump update flow

**As** an operator who bumped `revision:` in `.haex-hive.json`
**I want** `haex-init sync` to (a) fetch the new SHA, (b) regenerate
the extracts, (c) regenerate `.haex-hive.local.json`, (d) refuse
loudly if any explicit item's path is unresolvable at the new SHA
**so that** stale state is impossible and every SHA change is a
review-gated act.

**Independent test**: bump the `revision:` field, run `sync`, verify
`.haex-hive.local.json` shows new SHA in paths. Then bump to a SHA
that renames an explicit item — verify `sync` refuses with a
structured error naming the unresolvable path and leaves
`.haex-hive.local.json` untouched.

### US4 (P3) — `haex-init add-source` CLI + `--from-repo` bootstrap

**As** an operator adding a new source (or onboarding a new consumer
repo)
**I want** `haex-init add-source` to guide me through adding a
correctly-shaped `external-harness` entry — either from scratch or
by copying from a neighbor consumer's config — without touching
`.haex-hive.json` by hand
**so that** the config stays schema-valid and DX for propagation
across consumer repos is low-friction.

**Independent test**: two consumers on the device — one already
configured (`secure-web-frontend`), one fresh (`fresh-consumer`).
Run `haex-init add-source --from-repo ~/Projekte/secure-web-frontend`
in the fresh consumer. Interactive prompt offers to copy the
`secana-specs` entry. Post-accept, `.haex-hive.json` in the fresh
consumer contains the same entry (repository, revision, includes) as
the source; `sync` succeeds.

## Testing strategy

Follows Spec 005's `tests/haex-init/` shell-test pattern. New tests
under `tests/multi-spec-external-ref/`:

- `test-fresh-external-harness.sh` — US1 end-to-end on a fake
  producer repo
- `test-auto-include-speckit-defaults.sh` — the preset produces the
  documented set at SHA X, mutates on SHA-bump
- `test-additional-include.sh` — arbitrary paths flow correctly
- `test-explicit-items-aliases.sh` — items with `as:` produce
  stable-named entries in `.haex-hive.local.json`
- `test-sha-bump-clean.sh` — US3 happy path
- `test-sha-bump-rename-refuses.sh` — D9 fail-loud on rename
- `test-add-source-fresh.sh` — US4 from-scratch mode
- `test-add-source-from-repo.sh` — US4 `--from-repo` bootstrap mode
- `test-auth-error-clarity.sh` — D10 error surface

Test fixtures use a bare-repo-based local "producer" to avoid
network dependency (same pattern as Spec 004 tests).

Cross-platform validation is manual for Spec 006 (Linux is the
mechanical target). macOS + Windows-under-WSL2 receive smoke-test
validation in a follow-up (`.validation-runs/` document).

## Assumptions

- **A1**: Spec repos are small enough that full clone (no `--depth=1`)
  is acceptable disk-wise. Rough upper bound: producer repos < 500 MB
  full history. If violated for a real producer, we introduce
  `--depth=N` or `--filter=blob:none` as an opt-in later.
- **A2**: Consumer operators run `haex-init sync` after `git clone
  <consumer>` and after every `.haex-hive.json` mutation.
  Documented in operator docs; not mechanically enforced (no session-
  start auto-sync in Spec 006 to keep the sync moment explicit).
- **A3**: Producer file renames between pinned revisions are ordinary
  consumer maintenance. Auto-include absorbs them; explicit items
  require manual reconciliation. Aliases (`as:`) are the recommended
  stability mechanism for consumer wiring.
- **A4**: Auth is the operator's responsibility. Spec 006 provides
  actionable error messages but no auto-fix.
- **A5**: Speckit-managed files (`.specify/templates/**`,
  `.specify/workflows/**`) in the consumer are NOT overridden by
  producer content. Producer content is available for read via
  Path-Return but does not drive speckit's own commands.
- **A6**: `haex-hive` itself, currently self-ref, remains
  backward-compatible: its `harness_sources[0]` (constitution,
  role: constitution, repository: self) continues to work under the
  Spec 006 schema.

## Open questions (deferrable, not blocking Spec 006 MVP)

- **Q1**: Should `haex-init sync` warn (not refuse) if
  `~/.haex-hive/repos/<name>/` has un-fetched newer HEAD than what's
  pinned? Rationale: signals "producer has moved forward, review
  before bumping" without forcing action. Deferrable to sharpening
  phase.
- **Q2**: Ref-name namespacing. Currently `secana-specs:<alias>`. If
  two producers have overlapping alias names, is that a hard error or
  a warning? Probably hard error at `sync`. Sharpening detail.
- **Q3**: `.haex-hive.local.json` conflict detection. If two
  simultaneous shells on the device edit it (unlikely but possible),
  what happens? File-lock during write in `haex-init sync`;
  simultaneous shells serialize. Sharpening detail.
- **Q4**: `add-source --from-repo <path>` behaviour when the source
  repo has schema-invalid `.haex-hive.json`. Refuse with clear
  message; don't attempt partial import. Confirming during
  clarification phase.

## Notes for the sharpening phase (`/speckit-specify`)

The following are intentionally left underspecified in this design;
the `/speckit-specify` session should surface them as clarifications:

- Exact shape of the JSON Schema constraints for `external-harness`
  entry (which fields required, which optional)
- Exact ref-name convention beyond `<producer-name>:<alias>` (path
  characters allowed? colon collisions?)
- Behavior when a `harness_sources[]` array mixes v1.1.1-style
  `role: constitution` entries with new `role: external-harness`
  entries — implicit or explicit ordering
- Precise `haex-init sync` exit codes (align with Spec 005's 0–4
  scheme)
- Whether `sync` should be triggered automatically by any other
  operation (e.g., `add-source` triggers `sync` unless `--no-sync`,
  covered; anything else?)

## Constitution compliance check

- **Principle I** (No Secrets in Git): unaffected. Config carries
  refs, not secrets.
- **Principle II** (No Local Absolute Paths in Versioned Config):
  `.haex-hive.json` remains free of local paths. `.haex-hive.local.json`
  IS device-local absolute paths — but is gitignored, so it never
  enters versioned config.
- **Principle III** (Project Identity Device-Independent): producer
  `repository:` URLs are git remote URLs, device-independent.
- **Principle IV** (Cross-Repo References Pin Immutable Revisions):
  every `external-harness` entry pins a full 40-char SHA. No branch/
  HEAD references introduced.
- **Principle V** (External Sources Are Opt-in Per Project):
  `harness_sources[]` remains the sole trust boundary; coarse
  opt-in via `auto_include` is still consumer-explicit
  ("I opt into secana-specs' speckit-defaults set at SHA X" is a
  deliberate act).
- **Principle VI** (Self-Modifying Instructions Review-Gated):
  `.haex-hive.local.json` is device-local, gitignored, regenerated
  from checked-in config — not self-modifying instructions.
- **Principles VII, VIII**: not affected.

All eight NON-NEGOTIABLE principles satisfied by this design.

## Delivery preview

**MVP** = Phases 1 (framework) + 2 (US1) alone. Enough to prove
`secure-web-frontend` can inherit `secana-specs`' constitution.
US2–US4 harden the mechanism but are not blocking the "the mechanism
works" verdict.

**Estimated task count** (based on Spec 005's ratio of design →
tasks): ~40–60 tasks across ~6 phases, similar shape to Spec 005.

**Estimated cross-platform validation**: Linux mechanical; macOS
smoke; Windows-under-WSL2 smoke (deferred to a follow-up validation
run doc, not blocking Spec 006 merge).
