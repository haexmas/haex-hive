# Quickstart: v3 Vocabulary and `haex add` / `haex remove`

**Spec**: 013

This walk-through covers the three end-to-end flows this spec enables: migrating a v2 project to v3, adopting a molecule with one command, and retracting a molecule with one command. It assumes the v3 tool is installed and the operator has git access to whichever `<source-url>` publishes the molecule.

---

## Prerequisite: migrate an existing v2 project to v3

If your project's `.haex-hive.json` still says `"haex_hive_version": "2"`, the tool refuses at load time and points at `haex migrate`. Run:

```bash
haex migrate --check
```

The command scans `.haex-hive.json`, `manifest.json` (if this repo is also a publisher), and every per-molecule `manifest.json` under the repository, and prints one unified diff per input file. Nothing is written. Review the diffs.

When the diffs look right, run:

```bash
haex migrate
```

Every affected file gets a `.migrated` sibling:

- `.haex-hive.json.migrated`
- `manifest.json.migrated` (root, if you publish)
- `<molecule-dir>/manifest.json.migrated` for each of your molecule directories

Manifests referenced from immutable remote revisions land under `$HAEX_HIVE_STATE/migrations/<source-digest>/<revision>/<repo-relative-path>.migrated` instead of in your working tree. Do **not** overwrite the originals unattended; the migrator never does. To adopt each local proposal:

```bash
git diff --no-index .haex-hive.json .haex-hive.json.migrated
mv .haex-hive.json.migrated .haex-hive.json
```

Repeat for every proposal. For remote-publisher proposals, copy the `.migrated` content into a publisher checkout, open a PR upstream, and bump your consumer's pin to the new SHA after that PR lands.

Verify with:

```bash
haex install
```

A clean install on the newly adopted v3 manifests confirms the transition.

---

## Adopt a molecule in one command

Once your project is on v3, adopting a molecule is a single command:

```bash
haex add https://github.com/haexmas/atoms com.github.haexmas.atoms.graphify-first-authoring
```

The command:

1. Resolves the current HEAD SHA of `haexmas/atoms` via `git ls-remote`.
2. Fetches (or reuses) the publisher clone under `$HAEX_HIVE_STATE/repos/<source-digest>/`.
3. Validates that `com.github.haexmas.atoms.graphify-first-authoring` is listed in the publisher's root `manifest.json` at that SHA.
4. Writes a new `compoundEntry` (or merges into an existing one for the same source and revision) into `.haex-hive.json`.
5. Runs `haex install` in the same invocation, so `.haex-hive/` is up to date immediately.

To pin an exact revision:

```bash
haex add https://github.com/haexmas/atoms com.github.haexmas.atoms.graphify-first-authoring \
  --revision=ff6fda2180563479497e0bd5a25144653d3175fb
```

To adopt every molecule the publisher ships (rarely what you want, but occasionally useful):

```bash
haex add https://github.com/haexmas/atoms --all
```

To adopt without specifying a molecule id, on a TTY:

```bash
haex add https://github.com/haexmas/atoms
```

The command lists the available molecule ids and prompts you to pick one or more. On non-TTY invocations, this form refuses; scripts must pass explicit ids or `--all`.

### Review-gated constitution merge

When adopting a molecule that contributes a constitution and there is already an adopted constitution-contributing molecule in `.haex-hive.json`, `haex install` invoked by `haex add` triggers the review-gated `--llm=file` two-phase flow. `haex add` writes the manifest edit, runs install in `--llm=file` mode, and prints:

```
constitution-review-pending: review at .haex-hive/pending/<candidate>
```

Complete adoption with:

```bash
haex install --accept-merged .haex-hive/pending/<candidate>
```

This second command is the Principle VI review gate. `haex add` never bypasses it.

---

## Retract a molecule in one command

To remove a previously adopted molecule:

```bash
haex remove com.github.haexmas.atoms.graphify-first-authoring
```

The command:

1. Scans `.haex-hive.json` and removes `com.github.haexmas.atoms.graphify-first-authoring` from every compound's `molecules[]` array.
2. Drops any compound whose `molecules[]` became empty.
3. Runs `haex install`, which deletes every file that was contributed only by the retracted molecule (Spec 008 US3 delete-orphans).

If the retracted molecule was the currently adopted workflow molecule, the ensuing install falls back to the bundled `speckit` workflow on the next resolve. No separate activation step is needed (Spec 011 amendment).

If the named molecule id is not present in any current compound, `haex remove` refuses with `unknown-molecule-id` and modifies nothing.

To retract multiple molecules in one call:

```bash
haex remove com.github.haexmas.atoms.graphify-first-authoring,com.github.haexmas.atoms.speckit-session-hopper
```

---

## Concurrency and the manifest lock

`haex add`, `haex remove`, and `haex install` all acquire the permanent advisory manifest lock at `.haex-hive.json.lock` before reading or replacing `.haex-hive.json`. Concurrent invocations serialize; a second contender either waits or refuses on contention (`manifest-lock-contended`, exit 6) rather than corrupting the manifest.

The lock file is created once by the tool on first use and never renamed or deleted. Its content is inconsequential; only the OS-level advisory lock matters.

---

## Common refusals and their meaning

| Refusal key | Meaning | Recovery |
|---|---|---|
| `source-url-invalid` | `git ls-remote <source-url>` failed. | Check the URL, network, and any auth. |
| `revision-not-found` | `--revision=<SHA>` does not exist at the remote. | Verify the SHA or drop the flag to resolve HEAD. |
| `publisher-manifest-missing` | The resolved SHA has no `manifest.json` at repo root. | Confirm the source is a haex-hive publisher; pick a different revision if the publisher moved. |
| `molecule-id-not-in-source` | A named molecule id is not in the publisher manifest at that SHA. | Check spelling and case; the publisher may have renamed. |
| `interactive-selection-unavailable` | No molecule ids, no `--all`, and stdin is not a TTY. | Pass explicit molecule ids or `--all`. |
| `workflow-molecule-already-adopted` | The added set includes a workflow molecule; a different one is already adopted. | `haex remove <current-workflow-molecule-id>` first. |
| `constitution-review-pending` | A review-gated merge is required. | `haex install --accept-merged <candidate>`. |
| `unknown-molecule-id` | `haex remove` was called with an id not present in any compound. | Check spelling; nothing changed. |
| `manifest-lock-contended` | Another process holds `.haex-hive.json.lock`. | Wait and retry; investigate stuck processes if it persists. |
