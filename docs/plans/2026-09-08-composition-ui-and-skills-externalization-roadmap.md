# Composition UI & Skills Externalization (Roadmap)

**Status**: Design roadmap. Captured 2026-09-08 during a brainstorming session that reviewed the DeepSeek Harness (dsh) UI as a reference for the spaex composition surface. Not a single spec: this document orchestrates a sequence of follow-up specs and names the decisions that gate them.

**Author**: brainstorming session 2026-09-08 with operator.

**Target spaex versions**: 4.2.0 through 5.4.0 (see Phasing). Skills externalization (Phase A) is a breaking change to the molecule ontology and drives the MAJOR bump.

**Related**:
- [Scope Realignment (2026-09-03)](2026-09-03-scope-realignment-design.md): Section "Agent Skills is a format standard, not a package manager" already found that skills.sh and agentskills.io own the skill distribution problem. This roadmap acts on that finding by removing skills from spaex/atoms entirely.
- [Spec 016 install-hooks](2026-09-08-spec-016-molecule-install-hooks-design.md): The `install_hook` machinery is the natural carrier for "install these skills from skills.sh" as a molecule side effect (see Phase A).
- Atoms publisher v4 (memory `atoms_publisher_v4`): current publishers of skill atoms (`graphify-first-authoring`, `speckit-session-hopper`) migrate out of atoms as part of Phase A.
- DeepSeek Harness reference screenshots captured 2026-09-08 (session scratchpad, not committed).

---

## 0. Normative status

This is a design record. It fixes *direction and phasing*, not contracts. The normative home for every requirement below is a numbered spec under `specs/`, written through `/speckit-specify` per [ADR 0009](../adr/0009-declared-speckit-workflow-adherence.md) and the constitution's Development Workflow clause. Wherever this document names a spec number (018, 019, ...), that number is a placeholder pending a `docs/plans/YYYY-MM-DD-slot-NNN-*.md` slot reservation.

## 1. Problem

Two related problems surfaced in the 2026-09-08 session.

**Problem A: spaex ships and versions skills, but the skill ecosystem already has that job.** The `graphify-first-authoring` and `speckit-session-hopper` molecules in [haexmas/atoms](https://github.com/haexmas/atoms) publish skill files that spaex materializes into consumer repos. Meanwhile [skills.sh](https://www.skills.sh/) provides discovery and the open [Agent Skills format](https://agentskills.io/skill-creation/quickstart) is supported by Claude Code, Codex, Cursor, Copilot, and others. Duplicating that in spaex/atoms adds maintenance without users (see `spaex_pre_user` memory) and confuses the molecule ontology.

**Problem B: spaex has no browsable, click-toggleable composition surface.** Consumers today edit `.spaex.json` by hand and run `spaex add` / `spaex remove` to change what is active. There is no way to see which molecules are pinned, which atoms they contribute, which constitution parts are active, or which of them came from where. The operator's original vision was "custom harness per repo, selectable via GUI". DeepSeek Harness (dsh) already ships that kind of GUI for its Cordis-plugin composition; its Settings > Plugins tab and Agent presets screen are structurally isomorphic to the spaex molecule/constitution model.

## 2. Non-goals

- **spaex does not become a runtime.** dsh owns an entire agent loop (LLM adapters, session log, tool pipeline, web UI). spaex remains a meta-composition layer that produces artifacts consumed by any agent runtime (Claude Code, Codex, Gemini CLI, potentially dsh itself). See `spaex_composition_gui_vision` memory.
- **spaex does not become a skill registry.** After Phase A, spaex neither indexes nor mirrors skills. It records "this molecule expects the following external skills" and exposes them to an explicit consumer-selected skill-management operation.
- **No skill-content entry in the spaex lockfile.** The external reference
  records a repository, full revision SHA, and path for provenance, while the
  installed skill content and adapter outcome remain outside spaex's
  `install.lock`.
- **No native Electron/desktop shell in v1 of the GUI.** The Phase D GUI is a locally-hosted web app served by the spaex CLI (analogous to `dsh web`). Desktop packaging is a follow-up if there is demand.
- **No live-reload / live-patching of the composition.** The GUI represents the state of `.spaex.json` and `.spaex/install.lock`; user actions rewrite those files and trigger a normal `spaex install`. No in-process patch overlay like dsh's Cordis patch layer.
- **Constitution stays authored, not composed in the GUI.** The GUI shows which constitution files are active and their provenance; it does not offer a WYSIWYG constitution editor. Constitution assembly rules stay as they are (see `spaex_constitution_terminology` memory).

## 3. Findings from the dsh review

Captured from the 2026-09-08 session where the operator and the assistant walked through the DeepSeek Harness Settings dialog.

### Structure that transfers

- **Sidebar sections** in Settings: General / Models / Plugins / Agent presets. Directly maps to spaex's General / Molecules / Constitution / Presets.
- **Two sub-tabs under Plugins**: "Plugin configuration" (categorized cards with a short description of what each category does) and "Plugin list" (flat searchable list of every active plugin). The categorized view is a good landing surface; the flat list is where power users work.
- **Scope split** in the flat list: "Session plugins" (27, per-preset) vs. "Global plugins" (149, always active). Maps to spaex's project-active vs. globally-available.
- **Preset selector at the top of the list**: shows which preset's composition is currently displayed. Maps to spaex's molecule-set / constitution-set switcher.
- **Per-item `From` field**: on expansion, each plugin shows Module, From (which preset pulled it in), Configuration. This is the provenance display that spaex overlays badly need.
- **Agent preset cards** with `Built-in` tag, `In use` tag on the active one, and a Duplicate button. Maps to spaex's molecule-set profiles.
- **"Draft a custom preset with Creator mode" button**: an agent-driven authoring path instead of a pure GUI editor. This fits spaex naturally because the operator already works with Claude Code.
- **"Open configuration file" escape hatch** on every Settings pane. spaex's equivalent is "open `.spaex.json`".

### Structure to reject

- **Read-only plugin details.** dsh has no toggle at the plugin card; edits go through the Cordis patch file. That works for dsh because plugins are typed Cordis rows. spaex atoms are heterogeneous (hooks, MCPs, constitution snippets, workflows) and consumers expect click-to-toggle. spaex's GUI must offer inline enable/disable that rewrites `.spaex.json`.
- **Cordis-row categorization** ("Shell", "Agent loop", "Subagent", "Web search"). That is dsh's runtime ontology, not ours. Categorize by spaex atom type instead (Hooks, MCPs, Speckit-Workflows, Constitution snippets, Instructions), which is the categorization consumers already know from `atoms.<category>`.
- **Cordis patch overlay model.** dsh layers "profile bundles + profile patch + home patch + --patch overlay". spaex has one composition file (`.spaex.json`) and one lock (`install.lock`); do not invent a patch layer without a concrete use case.

## 4. Decisions

Decisions are numbered so downstream specs can cite them (`Roadmap 2026-09-08 §4.N`).

### Decision 1: Skills are external, not atom types

`atoms.skill` (or any equivalent under a different name) leaves the molecule manifest schema. Molecules that want skills reference them by external identifier (skills.sh `owner/repo` slug, or an agentskills.io URL / repo path) and delegate installation to the upstream tool.

**Why:** skills.sh and agentskills.io own discovery, distribution, versioning, and multi-agent portability (Claude Code, Codex, Cursor, Copilot, Gemini CLI, VS Code, and more). Duplicating that in spaex/atoms adds maintenance without users. The 2026-09-03 Scope Realignment already identified this; this roadmap acts on it.

**Blast radius:** breaking change to the molecule manifest v4 schema. Publishers of skill-shipping molecules (`graphify-first-authoring`, `speckit-session-hopper`) migrate. Consumer repos that pinned older revisions keep working until they bump; the bump makes them install skills via the external tool instead.

### Decision 2: Install-hooks (Spec 016) carry skill installation

A molecule that declares external skills gets a small hook (declared via Spec 016's `install_hook`) that reads the pinned molecule manifest and calls `uvx --from skillsmd==<version> skillsmd add ...` in the consumer repo during `spaex install`. spaex itself does not run the skill installer directly; it stays a level above. The Vercel npm CLI remains an optional alternative, while agentskills.io defines the format rather than providing an installer.

**Why:** avoid inventing a second side-effect mechanism next to Spec 016. `install_hook` is already trust-anchored on the SHA pin, already runs at the right moment (after atom materialization), and already handles failure via `on_failure: "abort" | "warn"`.

### Decision 3: Molecule ontology after Decision 1

Post-Phase A the molecule categories are, tentatively:
- `atoms.constitution` (unchanged)
- `atoms.speckit_workflow` (unchanged)
- `atoms.speckit_hooks` (unchanged)
- `atoms.mcp` (NEW: declare MCP servers to register with the consumer's agent)
- `atoms.command` (NEW: Claude Code slash commands, if not already covered)
- `atoms.instruction` (NEW: CLAUDE.md / AGENTS.md fragments)
- `external_skills` (NEW, replaces the `atoms.skill` category: list of external skill references, consumed by the install-hook per Decision 2)
- `atoms.install_hook` (from Spec 016, unchanged)

The exact names are placeholders; Phase A settles them.

### Decision 4: Presets ("molecule sets") become first-class

spaex today has one active composition per project (the `.spaex.json` compounds list). Following dsh's Agent presets pattern, introduce named "molecule sets" a project owner can switch between: e.g. "minimal", "full stack", "docs-only". Each preset is a named list of pinned molecule refs. `.spaex.json` records which preset is active; presets live alongside it (either inline or in `.spaex/presets/*.json`).

**Why:** enables the GUI's preset selector (Finding: dsh has this and it is the piece that makes composition tractable at scale). Also enables the Creator flow (Decision 8).

**Blast radius:** additive change to `.spaex.json` schema. Old projects continue to work as if they had a single unnamed preset.

### Decision 5: GUI is a locally-hosted web app served by the spaex CLI

A new `spaex ui` command (or `spaex web`, TBD in the naming spec) starts a local HTTP server that renders the composition surface. Same shape as `dsh web`: bind to `127.0.0.1`, print URL with an auth token, open browser unless `--no-open`. No auth beyond the token; local-only. Not packaged as Electron in v1.

**Why:** browser-based is portable across OSes, works over SSH forwarding, easy to iterate on. Electron is a follow-up.

### Decision 6: GUI is click-toggle, writing back to `.spaex.json`

Each atom row in the flat list has an inline enable/disable toggle. Toggling rewrites `.spaex.json` (adding the molecule to an "exclude these atoms" list, or removing it from the compound list, depending on granularity chosen in the GUI spec) and re-runs `spaex install` in the background. Failure shows inline. The `Open configuration file` escape hatch is available on every pane for power users.

**Why:** dsh gets away with read-only because Cordis plugins are typed rows edited in one file. spaex atoms are heterogeneous and consumers expect direct control. See §3 Structure to reject.

### Decision 7: Provenance display is mandatory

Every visible atom/molecule row shows a `From:` field: which molecule contributed it, and which preset activated the molecule. Constitution snippets show which molecule authored the snippet. This is non-negotiable; spaex's overlay/assembly model is too opaque without it.

**Why:** dsh's `From` field is the single most valuable transferable pattern from the review.

### Decision 8: Agent-drafted preset (Creator flow)

The GUI offers a "Draft a custom preset with your agent" button that opens a session with the consumer's agent (Claude Code or equivalent) pre-seeded with the current composition state and an instruction to help the user compose a new preset. Modeled on dsh's Creator mode preset, except spaex delegates to the consumer's existing agent runtime instead of running its own.

**Why:** authoring a preset from a hundred molecules and their atoms is exactly the kind of task an agent handles better than a form. Reuses the operator's existing agent setup.

### Decision 9: Constitution stays a dedicated sidebar section

Not folded into Molecules or Presets. Because the constitution is spaex's USP (see `spaex_constitution_terminology` memory) and its assembly rules are non-trivial, it earns its own top-level sidebar entry in the GUI, listing active fragments with provenance.

**Why:** dsh has no equivalent, so there is no dsh-shaped guidance for it. Do not shoehorn it into Plugins-shaped UI.

## 5. Phasing

Each phase corresponds to one Speckit spec. Phase A is a breaking change and drives spaex 5.0.0; the rest are MINOR bumps until proven otherwise.

### Phase A: Skills externalization (proposed Spec 018 slot, spaex 5.0.0)

- Deprecate and remove the skill atom category from the molecule schema.
- Introduce top-level `external_skills` as structured repository/revision/path
  references.
- Add a consumer-owned skill-installation policy and explicit skill-management
  commands. Normal `spaex install` only reports pending external skills; it
  does not invoke an installer selected by the provider.
- Migrate `graphify-first-authoring` and `speckit-session-hopper` in [haexmas/atoms](https://github.com/haexmas/atoms) to the new shape; publish as new molecule versions.
- Update consumer docs: adoption flow no longer materializes skill files; skills are installed by the hook.

Depends on: Spec 016 landed (currently in `docs/plans/2026-09-08-spec-016-molecule-install-hooks-design.md`).

### Phase B: Molecule ontology cleanup + preset schema (proposed Spec 019 slot, spaex 5.1.0)

- Rename / consolidate the remaining atom categories per Decision 3 (final names settled in the spec).
- Introduce named molecule presets in `.spaex.json` per Decision 4. Additive schema change with a default unnamed preset for existing projects.
- New CLI: `spaex preset list`, `spaex preset use <name>`, `spaex preset add <name>`, `spaex preset remove <name>`.

Depends on: Phase A.

### Phase C: `spaex status` CLI + provenance query (proposed Spec 020 slot, spaex 5.2.0)

- New CLI: `spaex status` prints a human-readable summary of the active composition (which preset, which molecules, which atoms per category, with provenance per atom).
- New CLI: `spaex show <atom-id>` or `spaex trace <path>` for provenance lookup ("which molecule wrote this file").
- No GUI yet. This phase makes the data available in a stable form the GUI will consume.

Depends on: Phase B.

### Phase D: GUI MVP (proposed Spec 021 slot, spaex 5.3.0)

- New CLI: `spaex ui` (or `spaex web`, name settled in spec). Starts a local HTTP server, bind `127.0.0.1`, token in URL, `--no-open` flag, mirroring `dsh web` shape.
- UI surface: sidebar (General / Molecules / Constitution / Presets), flat searchable Molecules list with per-atom expansion and `From` field, preset selector at top, inline click-toggle per atom, "Open configuration file" escape hatch per pane.
- Backend: reuses the Phase C status/provenance APIs; toggle actions rewrite `.spaex.json` and run `spaex install`.

Depends on: Phase C.

### Phase E: Agent-drafted preset (proposed Spec 022 slot, spaex 5.4.0)

- New GUI button: "Draft a custom preset with your agent".
- Launches a subsession of the consumer's agent runtime (Claude Code, Codex, ...) with a seeded prompt and the current composition state as context.
- The agent proposes a preset, the user reviews the diff, one click applies it.

Depends on: Phase D.

## 6. Follow-ups / Not now

- **Electron/desktop packaging** of the GUI. Only if browser-served proves insufficient.
- **Live-reload of composition** in the GUI while `spaex install` is running elsewhere. Nice, not needed for v1.
- **Constitution WYSIWYG editor**. Explicitly non-goal; constitution stays authored in files.
- **Cross-project preset library** ("share this preset with my team"). Interesting but separate from the local-composition problem.
- **spaex as dsh bundle producer**. Emit `.spaex/install.lock` compositions as dsh Cordis-patch bundles for consumers who choose dsh as their runtime. Deferred until a real dsh consumer surfaces.
- **Skill registry aggregation**. If skills.sh and agentskills.io diverge in ways that hurt consumers, spaex could add a thin adapter layer. Not now.
