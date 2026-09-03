# Spec 013: pnpm-style `haex add` / `haex remove` and the atoms→molecules format rename (Design Preview)

**Status**: Design preview. Not yet a spec. Captured 2026-09-02 as the requirements source for a subsequent `/speckit-specify` invocation that creates `specs/013-add-cli-and-molecule-rename/`.

**Purpose**: two co-shipping changes.

1. Add `haex add` and `haex remove` subcommands so that adopting an atom is a one-line operation, not a manual edit of `.haex-hive.json` followed by manual `haex install`. Under the Spec 011 simplification amendment (2026-09-02), a single workflow atom's adoption in `.haex-hive.json` alone determines binding, so no separate `activate` step is needed.
2. Rename the consumer-manifest and atom-manifest fields so the schema vocabulary matches the prose one that Spec 010 and the graphify-first-authoring design already use.
   - `.haex-hive.json`: outer `atoms[]` becomes `molecules[]`; per-entry `includes[]` becomes `atoms[]`.
   - Atom manifests: `contributes`-siblings unchanged, but `includes[]` (profile-atom composition) becomes `atoms[]`.

These two changes ship together because `haex add` writes the new schema shape directly, and shipping the CLI on top of the old `includes[]` name would freeze bad vocabulary at the exact moment we get a chance to fix it.

**Related**:
- [Spec 007: Unified Manifest v3](../../specs/007-unified-manifest-v2/spec.md): defines the v3 molecule model. Spec 013 defines the consumer/profile-field migration from the merged v2 shape into that model.
- [Spec 008: Install Transaction](../../specs/008-install-transaction/): landed. `haex add` and `haex remove` delegate publication to the existing install transaction; they add no new file-publication logic.
- [Spec 010: Compiler & Agent Adapters](2026-08-31-spec-010-compiler-preview.md): uses "molecule" prose to describe the personal harness bundle. Spec 013 promotes that prose term to a schema field name.
- [Spec 011 simplification amendment (2026-09-02)](../../specs/011-simplify-workflow-atom/): retires `workflow-registry.json` and `active_workflow`. Spec 013 inherits this: no `haex workflow activate`, no `--activate` flag, no interactive activation prompt.
- [Spec 012: Speckit Session Hopper Atom](2026-09-02-spec-012-speckit-session-hopper-atom-design.md): first atom that the new `haex add` flow will adopt in a single command instead of a copy-and-paste JSON block. The atom's README will be rewritten against the Spec 013 CLI once it lands. The Spec-012 doc itself pre-dates the Spec 011 amendment and still references `active_workflow`; its parallel branch updates that.
- [graphify-first-authoring design doc](2026-08-31-graphify-first-authoring-design.md): where "molecule" was first defined as a prose-only term. Spec 013 lifts the "no schema" caveat.

---

## What this covers

### 1. CLI subcommands

- **`haex add <source-url> [<atom-id>[,<atom-id>...]] [--revision=<SHA>]`**
  - Adds a molecule entry to `.haex-hive.json` and then runs the existing `haex install` in the same invocation. Analogous to `pnpm add <pkg>`.
  - `<atom-id>` positional list is optional; when omitted, the command fetches the publisher-manifest of `<source-url>` at `<revision>` and prompts the operator interactively to pick one or more atoms (or takes all with `--all`).
  - `<revision>` is optional; when omitted, the command runs `git ls-remote <source-url> HEAD` and uses the resulting full SHA. Principle IV (immutable revisions) still applies: whatever SHA is resolved is written verbatim into `.haex-hive.json`. A user-supplied `--revision=<SHA>` short-circuits the lookup.
  - Merging: if a molecule with the same `source` and `revision` already exists in `.haex-hive.json`, `haex add` merges the new atom-ids into that entry's `atoms[]` instead of appending a second entry. Same source with a different revision remains a separate entry (Spec 010 already allows this).
  - Workflow atoms: the Spec 011 amendment forbids more than one adopted workflow atom per repository. If the new molecule's atom-ids include a workflow atom and `.haex-hive.json` already resolves to a different workflow atom (bundled or adopted), `haex add` refuses with `key=workflow-atom-already-adopted` naming the currently-bound one. The operator must `haex remove <current-id>` first, then `haex add` the new one. No activation step is involved on either side of that swap.

- **`haex remove <atom-id>[,<atom-id>...]`**
  - Removes the named atom-id(s) from every molecule entry in `.haex-hive.json`. If a molecule becomes empty (`atoms: []`), the whole entry is dropped. Runs the existing `haex install` afterwards, so Spec 011 US3 delete-orphans applies to whatever the removed atoms contributed. When the removed atom is the adopted workflow atom, the reader falls back to the bundled `speckit` workflow on the next resolve (Spec 011 amendment FR-008).
  - Refuses with `key=unknown-atom-id` if an atom-id is not present in any current molecule entry.

- **`haex install`** stays unchanged: still resolves every molecule in `.haex-hive.json` and publishes them. `haex add` and `haex remove` are convenience wrappers on top; nothing they do bypasses install.

### 2. Format rename (v2 → v3)

Old (v2):

```json
{
  "haex_hive_version": "2",
  "atoms": [
    {
      "source": "https://github.com/haexmas/haex-hive",
      "revision": "336eaf1e...",
      "includes": ["com.github.haexmas.haex-hive.constitution"]
    }
  ]
}
```

New (v3):

```json
{
  "haex_hive_version": "3",
  "molecules": [
    {
      "source": "https://github.com/haexmas/haex-hive",
      "revision": "336eaf1e...",
      "atoms": ["com.github.haexmas.haex-hive.constitution"]
    }
  ]
}
```

Atom-manifest rename (v2 → v3):

```json
{
  "haex_hive_version": "3",
  "id": "com.example.publisher.my-profile",
  "atoms": ["com.example.publisher.atom-a", "com.example.publisher.atom-b"]
}
```

`atoms` in an atom manifest is the profile-composition list (Spec 007's `includes`). `contributes.*` fields are unchanged in shape and semantics; they never contained atom-ids, so no rename applies there.

## What this does NOT cover (deliberately)

- **New atom-resolution semantics**: `haex add` and `haex remove` only edit the JSON and call the existing resolver. No new resolution rules, no new dependency graph. If Spec 010 or Spec 011 change how resolution works, Spec 013 inherits those changes.
- **`haex update`**: bumping a molecule's pinned revision to head. Deliberately deferred; the pattern would be `haex update [<atom-id>|--all]` and land in a Spec 013-successor once we have `haex add` and `haex remove` working. For now the operator re-runs `haex add <source>` (same source, no `--revision`) to overwrite the pinned SHA in the merged entry.
- **`haex ls`**: listing installed molecules and atoms. Trivial to add later; not blocking the primary UX.
- **Registry mirroring**: `haex add` does not consult a central atom registry. `<source-url>` remains a direct git URL, and the publisher-manifest is fetched from that repo at that revision.
- **Backwards-compatible v2 read**: v3 refuses v2 files at load-time. The operator must run `haex migrate` (extended in Spec 013 to also handle v2→v3) before `haex add` or `haex install` will accept the file. Pre-user policy (haex-hive has no external adopters yet) makes this acceptable; a hard refuse plus a `haex migrate` hint is clearer than mixed-vocabulary tolerance.

## Terminology

- **Molecule**: a single entry in `.haex-hive.json`'s `molecules[]` list, describing one `source` + one `revision` + the list of `atoms` fetched from that pin. A molecule of size 1 is the common case; larger molecules exist when the operator wants several atoms from the same repo at the same SHA.
- **Profile atom**: an atom whose manifest carries `atoms: [...]` (formerly `includes`) instead of, or in addition to, `contributes.*`. It resolves to the transitive union of the listed atoms. Semantics unchanged from Spec 007's profile-atom rules; only the field name changes.
- **Adopted workflow atom**: a workflow atom that appears in some molecule entry's `atoms[]`. Under the Spec 011 amendment, adoption alone makes the atom binding for the repository; at most one such atom may be adopted at a time.

## Architecture

### CLI dispatch

`src/haex_hive/cli/main.py` gains two subparsers: `add` and `remove`. No `workflow` subparser lands with Spec 013; under the Spec 011 amendment there is no `active_workflow` to activate. A `haex workflow list` or `haex workflow show <atom-id>` command is a plausible read-only follow-up if the operator wants a summary of the adopted workflow atom, but it is out of scope here.

`add` and `remove` invoke a shared `write_and_reinstall(consumer_manifest, install_args)` helper that:

1. Acquires the same manifest lock used by `haex install` (advisory `flock` on
   `.haex-hive.json`; refuses on contention). Lock acquisition order is
   manifest lock first, then the device-local install mutex.
2. Writes the modified manifest to a `.haex-hive.json.tmp` sibling and renames into place (rename-safe under the same rules Spec 008 already uses for other files).
3. Calls `haex_hive.cli.install.run(...)` in-process while retaining the
   manifest lock. `install.run` accepts the held-lock context and must not
   acquire the manifest lock again; standalone `haex install` acquires it
   before reading `.haex-hive.json`.
4. Releases the install mutex and then the manifest lock.

If step 3 raises, the manifest change is rolled back by writing the pre-edit
copy back atomically while the manifest lock remains held. The rollback also
uses the same lock context, and a rollback failure reports the recovery path
without releasing the lock early. Steps 1-2 alone are not a persistent change
from the operator's perspective; either everything succeeded or nothing was
left touched. This prevents a standalone install from reading a manifest
between the add/remove write and its rollback.

### Fetch of publisher-manifest during `haex add`

For interactive atom-id selection and for validating a positional atom-id against the source, `haex add` shells out to `git ls-remote` + a shallow fetch of just the publisher-manifest tree (git sparse-checkout of `manifest.json` at the resolved SHA). This avoids full-repo clones for a one-shot lookup.

For the initial implementation, the simpler-but-slower option is a full shallow clone (`git clone --depth 1 --revision <sha>` into a temp directory, read `manifest.json`, delete). Both are acceptable; the shallow-clone option is easier to write. Whichever ships is an implementation detail, not a spec constraint.

### `haex migrate` v2→v3

Existing v1→v2 migration in `src/haex_hive/cli/migrate.py` is extended with a
second transform. The transform covers every affected manifest and is applied
as one review-gated migration:

- **Consumer manifest (`.haex-hive.json`)**: rename the outer `atoms` list to
  `molecules`, rename each entry's `includes` list to `atoms`, and bump
  `haex_hive_version` from `"2"` to `"3"`.
- **Profile molecule manifests**: rename the top-level `includes` list to
  `atoms` and bump `haex_hive_version` from `"2"` to `"3"`. Existing
  `contributes.*` fields and their values are preserved; they are not an
  atom-id list and therefore are not part of this field rename.
- **Publisher root manifest (`manifest.json`)**: bump
  `haex_hive_version` from `"2"` to `"3"`; preserve the publisher-root
  `atoms` map, its atom ids, paths, versions, and optional descriptions.
- **Priority default**: whenever an affected v2 molecule manifest omits
  `priority`, add `priority: 100`. Preserve every existing integer priority
  unchanged.
- **Minimum-version constraint**: preserve `haex_hive_min_version`'s operator
  and meaning without leaving a v2 floor in a v3 consumer. An exact
  `2.x.y` constraint becomes the corresponding exact v3 contract
  `3.x.y` (the v2 major is replaced while minor and patch are preserved); a
  lower bound `>=2.x.y` becomes `>=3.0.0`. Exact constraints stay exact and
  lower bounds stay lower bounds during serialization. Any other major is
  refused as unsupported for this transform.

The migration MUST follow Spec 007 D10: invalidate a stale sidecar in write
mode, write only to `.haex-hive.json.migrated` after all transforms and
validation succeed, print a unified diff against the original, and require the
operator to review and manually adopt the sidecar. `--dry-run` and `--check`
must not mutate the original, sidecar, or temporary files. Until that reviewed
sidecar is adopted, v3 readers continue to refuse v2 manifests. The transform
is idempotent: running it on an adopted v3 file is a no-op; running it on a v1
file first applies v1→v2, then v2→v3.

### Publisher-manifest bump

Publisher-manifests (the `manifest.json` at the root of a repo like `haexmas/atoms` or `haexmas/haex-hive`) also bump to `haex_hive_version: "3"`. Their internal shape does not change, but the version field must line up so a v3 consumer refuses to adopt from a v2 publisher (and a v2 consumer refuses to adopt from a v3 publisher, if any v2 consumer still exists). Given pre-user policy, this is a simple find-and-replace in the two publisher manifests we ship (`haex-hive` and `haexmas/atoms`), plus every test fixture.

### `haex add` refusal keys

- `key=source-url-invalid`: `<source-url>` does not resolve to a git remote.
- `key=revision-not-found`: `--revision=<SHA>` was given, but the remote does not have that SHA.
- `key=publisher-manifest-missing`: the resolved revision has no `manifest.json` at repo root.
- `key=atom-id-not-in-source`: a positional atom-id is not listed in the publisher-manifest at that revision.
- `key=workflow-atom-already-adopted`: the added molecule includes a workflow atom while `.haex-hive.json` already resolves to a different workflow atom. Names the current one and asks the operator to `haex remove <current-id>` first.
- `key=constitution-review-pending`: the underlying `haex install` needs `--llm=file` review before the change takes effect. In this case `haex add` writes the manifest edit, runs install in `--llm=file` mode, and prints the review path. A follow-up `haex install --accept-merged <candidate>` (or a `haex add --accept-merged` shortcut, TBD) finishes the adoption.

## Adoption flow after Spec 013 lands

The Spec-012 atom README becomes:

```
haex add https://github.com/haexmas/atoms com.github.haexmas.atoms.speckit-session-hopper
haex install --accept-merged .haex-hive/pending/<candidate>
```

Two commands, no JSON edits. No activation step because, under the Spec 011 amendment, adoption alone binds the workflow. `haex install --accept-merged` remains a distinct step by design because Principle VI (review-gated constitution merges) requires operator review; automating past that would violate the constitution.

## Assumptions

- **Pre-user policy**: no external adopters of haex-hive as of 2026-09-02. Bumping to v3 with a hard-refuse-on-v2 read is acceptable. Recorded in memory `haex_hive_pre_user`.
- **`haex install` is stable enough to wrap**: Spec 008 has landed; `haex install` handles publishing, delete-orphans, and constitution merges. `haex add` and `haex remove` add no new file-touching primitives; they only edit `.haex-hive.json` and delegate.
- **`git ls-remote` and shallow-clone availability**: the operator has git installed and can reach `<source-url>`. `haex add` does not offer an offline mode; a network failure surfaces as `key=source-url-invalid` or `key=revision-not-found`.
- **Adoption implies binding**: under the Spec 011 amendment, adopting a workflow atom in `.haex-hive.json` alone makes it the binding workflow. No activation step exists to be automated. `haex add` refuses to add a second workflow atom while one is already adopted, so the operator never accidentally shadows a workflow through a rename or a re-add.
- **Rename is worth the churn**: the value ("molecules" matches Spec 010 and graphify-first-authoring prose, `atoms:` inside a molecule reads naturally) outweighs the migration cost (one test-fixture sweep, one migrate transform, and README updates in this repo plus `haexmas/atoms`). Recorded here because it is a judgment call, not a mechanical follow-up.

## Open questions

1. **`haex add --accept-merged`**: should `haex add` support the two-phase merge in one command (write the manifest, run install in `--llm=file` mode, then accept-merge the candidate the operator points to), or is the two-line "add then accept-merged" flow above sufficient? Default: two-line for MVP; single-command shortcut is a follow-up if the two-line UX chafes.
2. **Interactive atom-id selection UI**: TTY-only or also programmatic (`--interactive=false`)? Default: TTY-only; non-TTY callers must pass positional atom-ids.
3. **`--all` semantics**: does `--all` include profile atoms plus their transitively resolved atoms, or only top-level atom-ids listed in the publisher-manifest? Default: only top-level (the profile atom itself, whose transitive resolution then happens at install time, same as any other adoption).
4. **Where the pre-edit manifest copy lives during rollback**: `.haex-hive.json.pre-<epoch>` in the repo root, or under `$HAEX_HIVE_STATE`? Default: `$HAEX_HIVE_STATE/rollback/` so the operator's checkout stays clean; a failed rollback surfaces the state path for manual recovery.
5. **Swap flow ergonomics**: replacing an adopted workflow atom takes two commands under the current design (`haex remove <current>`, then `haex add <new>`). Should Spec 013 also ship `haex replace <current-id> <source-url> [<new-id>...]` as sugar, or is two commands acceptable? Default: two commands for MVP; sugar can follow if the swap flow chafes.

## Deferred to later specs

- `haex update <atom-id|--all>` for bumping pins to head SHAs. Trivial once the manifest-write helper from `haex add`/`haex remove` exists.
- `haex ls` for showing adopted molecules, their atom-ids, and which workflow is active. Also trivial post-`add`.
- `haex add --from-url <sha-url>` for adopting from a GitHub compare URL or a similar convenience. Sugar, not fundamental.
- A registry index (`haex search` etc.) is explicitly out of scope; Spec 013 keeps `<source-url>` as a direct git URL, matching Spec 011's atom-adoption model.
