# Quickstart: Adopting a Speckit Workflow Atom

**Feature**: Spec 011: Speckit Workflow Atom
**Audience**: satellite operators adopting a workflow atom, and adapter authors verifying reader consistency.

## Prerequisites

- `haex` CLI installed and functional (Spec 007 + Spec 008 landed and available).
- Project already uses haex-hive: a valid `.haex-hive.json` (v2 shape) is present and the operator can run `haex install` today.
- A publisher clone of the workflow atom's source repository is reachable under `$HAEX_HIVE_STATE/repos/`.
- Any speckit-community extensions the workflow atom declares as `required_extensions` are already installed under `.specify/extensions/<extension-id>/` at a compatible version.

## 1. Adopt the workflow atom

Edit `.haex-hive.json`:

```json
{
  "haex_hive_version": "2",
  "identity": "com.github.example.consumer",
  "atoms": [
    {
      "source": "https://github.com/example/speckit-workflows",
      "revision": "aabbccddeeff00112233445566778899aabbccdd",
      "includes": ["com.example.publisher.strict-tdd-workflow"]
    }
  ]
}
```

The `revision` MUST be a full 40-char SHA (Principle IV). The workflow atom is adopted the same way as any other atom.

## 2. First install with the atom

The multi-source merge path applies only when multiple constitution contributions require merging. The sample atom contributes one `constitution.md`; if the consumer has no other constitution contribution, the single-source path applies. If a base constitution atom is already adopted, this becomes a multi-source install and follows the two-phase flow:

```console
$ haex install --llm=file
# exits with code 5 and writes .haex-hive/constitution.merge.pending.json

$ # review the pending merge; produce a merged constitution candidate
$ # (using an LLM, an editor, or a manual copy-paste-review)

$ haex install --accept-merged /path/to/merged-candidate.md
installed generation g_20260902T160000Z_ab12
```

Alternatively, if only a single constitution-contributing atom is adopted (no merge needed), a plain `haex install` publishes the workflow atom directly.

## 3. Verify the publication

After a successful install, the following files exist:

```console
$ ls .specify/workflows/
com.example.publisher.strict-tdd-workflow/
speckit/
workflow-registry.json

$ ls .specify/workflows/com.example.publisher.strict-tdd-workflow/
workflow.yml

$ ls .specify/extensions/workflow-atoms/
com.example.publisher.strict-tdd-workflow/

$ ls .specify/extensions/workflow-atoms/com.example.publisher.strict-tdd-workflow/
pre-implement.sh
post-tasks.sh
```

The atom's constitution fragment appears in `.haex-hive/constitution.md`:

```markdown
## Workflow-Contributed Rules

### From atom `com.example.publisher.strict-tdd-workflow` (revision `aabbccdd`)

<the atom's constitution.md content verbatim>
```

The registry lists both the bundled workflow and the newly-adopted atom-workflow:

```console
$ cat .specify/workflows/workflow-registry.json
{
  "schema_version": "1.0",
  "active_workflow": null,
  "workflows": {
    "speckit": {
      "name": "Full SDD Cycle",
      "version": "1.0.0",
      "source": "bundled",
      "installed_at": "2026-09-02T14:30:00Z",
      "updated_at": "2026-09-02T14:30:00Z"
    },
    "com.example.publisher.strict-tdd-workflow": {
      "name": "Strict TDD Cycle",
      "version": "1.2.0",
      "source": "atom",
      "atom_id": "com.example.publisher.strict-tdd-workflow",
      "atom_revision": "aabbccddeeff00112233445566778899aabbccdd",
      "installed_at": "2026-09-02T14:30:00Z",
      "updated_at": "2026-09-02T14:30:00Z"
    }
  }
}
```

`active_workflow` is `null`: the bundled `speckit` workflow is still the implicit default.

## 4. Activate the atom-adopted workflow

Manually edit `.specify/workflows/workflow-registry.json` to set:

```json
{"active_workflow": "com.example.publisher.strict-tdd-workflow"}
```

Verify:

```python
from pathlib import Path
from haex_hive.workflow.resolver import resolve_active_workflow

resolution = resolve_active_workflow(Path.cwd())
assert resolution.active_id == "com.example.publisher.strict-tdd-workflow"
assert resolution.source == "atom"
assert resolution.workflow_path.name == "workflow.yml"
```

Downstream `/speckit-<step>` invocations now read the atom's `workflow.yml` for their steps and review gates. The constitution's "Declared speckit workflow adherence" bullet resolves to this new workflow.

## 5. Refusal path: required extension missing

If the workflow atom declares `required_extensions: [{id: v-model-extension-pack, version_constraint: ">=0.7.2"}]` and the extension is not installed locally:

```console
$ haex install
error: exit=4 key=required-workflow-extension-missing
  workflow atom `com.example.publisher.strict-tdd-workflow` requires
  extension `v-model-extension-pack` version `>=0.7.2`; not installed
  under .specify/extensions/
  hint: install the extension via `speckit extensions install v-model-extension-pack@0.7.2`
```

Install refuses BEFORE any file publication. Fix by installing the extension and retrying.

## 6. Coexistence: swap between workflows

With both the bundled and the atom-adopted workflow present, swap by editing `active_workflow`:

```json
{"active_workflow": "speckit"}
```

or

```json
{"active_workflow": null}
```

No `haex install` needed for a swap; the resolver reads `active_workflow` at query time. However, `haex install --verify-only` (when T037 lands) will report the resolved workflow so the operator can confirm the switch.

## 7. Downgrade: remove the workflow atom

This walkthrough assumes that another constitution-contributing source remains adopted as the project's base constitution. Delete only the workflow atom entry from `.haex-hive.json.atoms[]` and re-install:

```console
$ haex install
installed generation g_20260902T170000Z_bd41
```

If `active_workflow` had named the removed atom:

```console
$ haex install
installed generation g_20260902T170000Z_bd41
warning: key=workflow-atom-reset-to-default
  active_workflow was `com.example.publisher.strict-tdd-workflow`, which is no
  longer adopted; reset to null (bundled `speckit` workflow now binding)
```

The atom's files are gone:

```console
$ ls .specify/workflows/
speckit/
workflow-registry.json

$ ls .specify/extensions/workflow-atoms/
(empty)
```

The constitution's `## Workflow-Contributed Rules` section is either gone (no atoms contribute rules anymore) or reduced (only remaining atoms' fragments survive).

If the removed workflow atom was the final constitution source, the current install contract refuses with `key=no-sources-declared` before publication. A zero-constitution generation is not part of this walkthrough; retain an additional constitution source when demonstrating removal.

## 8. Where things live (recap)

- **In the repo checkout** (committed):
  - `.haex-hive.json`: atom adoption declarations (Spec 007).
  - `.specify/workflows/<atom-id>/workflow.yml`: per-atom workflow declarations (Spec 011).
  - `.specify/workflows/workflow-registry.json`: `active_workflow` selector + workflow catalogue (Spec 011).
  - `.specify/extensions/workflow-atoms/<atom-id>/`: atom-contributed hook scripts (Spec 011, reserved namespace).
  - `.specify/extensions.yml`: merged hook wiring (atom + local; Spec 011 extends).
  - `.haex-hive/constitution.md`: merged constitution including `## Workflow-Contributed Rules` (Spec 011).
  - `.haex-hive/install.lock`, `.haex-hive/visibility.json`: install transaction outputs (Spec 008).
- **Under `$HAEX_HIVE_STATE`** (device-local, per FR-022):
  - `repos/<clone-hash>/`: publisher clones (Spec 007).
  - `locks/<repo-key>/install.mutex`: install exclusive lock (Spec 008).

## 9. What this quickstart does NOT cover

- Authoring a workflow atom (publisher-side workflow: how to structure a repository that publishes workflow atoms). That belongs to a publisher-quickstart or a Spec 011 successor.
- Installing speckit-community extensions. Delegated to specifyr or `speckit extensions install`; out of scope for Spec 011.
- Runtime enforcement of the workflow steps. The constitution advises adherence; mechanical enforcement (pre-commit hook, GitHub Action refusing non-workflow task landings) is Phase-7 territory per constitution §Governance.
