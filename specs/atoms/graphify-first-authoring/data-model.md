# Data Model: graphify-first-authoring atom/molecule

This feature has no database and no CRUD entities in the usual sense — its "data model" is the set of on-disk artifacts and config fields the atom reads, writes, or contributes. Each is documented below with its fields and lifecycle.

## AtomManifest (this atom's own manifest.json)

Conforms to Spec 007's existing `atom-manifest.v2.schema.json` — no schema changes needed.

| Field | Type | Value for this atom |
|---|---|---|
| `contributes.constitution` | string (relative path) | `"constitution.md"` |

**Lifecycle**: authored once at implementation time, versioned in git, read by `haex constitution assemble` on every adopting repo (including haex-hive itself).

## ContributedConstitutionText (constitution.md)

Free-form markdown, merged by `haex constitution assemble` into an adopting repo's `.haex-hive/constitution.md` (straight-copy if this is the only constitution-contributing atom adopted, LLM-merged alongside others otherwise — both paths already exist per Spec 007 US2/US3).

**Fields** (as prose sections, not structured data): the principle statement (FR-002/FR-003), the tracked-branch/snapshot lifecycle description, the bootstrap/refresh/warn-and-continue failure semantics (FR-004, FR-006, FR-010), the refuse-then-propose behavior (FR-004), the escape hatch (FR-005).

**Lifecycle**: authored once, versioned; consumed transitively via the adopting repo's own `.haex-hive/constitution.md` — never read directly by an agent.

## TrackedBranchSet

Not a single file — computed from two sources at check time:

| Source | Field | Type |
|---|---|---|
| git | default branch | derived from `git symbolic-ref refs/remotes/origin/HEAD` |
| `.haex-hive.json` | `tracked_branches` | optional array of strings, additional branch names |

**Lifecycle**: recomputed on demand (not cached) by both the `post-commit` hook and the agent-side backstop — cheap enough that caching isn't warranted, and a cache risks going stale if `tracked_branches` changes.

## GraphifyOutDirectory (graphify-out/)

Not owned by this atom — it is `graphify`'s own artifact directory. This atom only reads its presence/freshness and copies it wholesale (never inspects its internal structure).

**Lifecycle**:
- **Tracked branch**: authoritative; refreshed incrementally by `post-commit` after every commit (FR-006), or by the agent-side backstop if the hook is absent/failed/bypassed (FR-010).
- **Feature branch/worktree**: a discarded fork-point snapshot, copied in once by `post-checkout` (FR-008), never refreshed again during the branch's life; removed when the worktree/branch is deleted. Never committed (FR-009).

## FreshnessMarker (graphify-out/.meta.json)

Written by `graphify` at index/refresh time (small addition needed there, or a thin wrapper — noted as an open item in the design doc).

| Field | Type | Meaning |
|---|---|---|
| `indexed_at_sha` | string (git SHA) | The commit the graph currently reflects. |

**Lifecycle**: compared against current `HEAD` on a tracked branch to decide bootstrap (absent) vs. refresh (behind) vs. proceed (current). Not meaningful on a feature-branch snapshot — the snapshot is intentionally frozen at the fork point, never compared against the feature branch's own advancing HEAD (see spec.md Edge Cases).

## InstallerState (ephemeral — install.py's own run-time checks, not persisted)

| Check | Outcome on failure |
|---|---|
| `graphify` on PATH | If absent, prompt to install via `pip install graphifyy` (default Y); on decline, refuse with instructions, no other changes (FR-011) |
| Current branch is tracked | Refuse, name current branch + expected tracked branch(es) (FR-013) |
| Target hook path already occupied | Refuse, instruct manual integration, no overwrite (FR-014) |
| `graphify-out/` directory present in repo | If absent, run `graphify install` (idempotent, one-time per adoption); if present, skip (FR-012) |

**Lifecycle**: none — these are one-shot checks performed each time `install.py` runs; nothing here is written to disk as state.

## RootManifestEntry / ConsumerManifestEntry (haex-hive self-adoption)

Two existing Spec 007 structures, each gaining one entry — no new schema:

- Root `manifest.json`'s `atoms` map gains `com.github.haexmas.haex-hive.graphify-first-authoring → { path: ".specify/atoms/graphify-first-authoring", version: "0.1.0" }`.
- `.haex-hive.json`'s `atoms[]` array gains one entry `{ includes: ["com.github.haexmas.haex-hive.graphify-first-authoring"], revision: <pinned SHA>, source: "https://github.com/haexmas/haex-hive" }`, alongside the existing constitution-atom entry.

**Lifecycle**: both are committed, versioned config, updated once during this feature's implementation and thereafter only on version bumps of the atom itself.
