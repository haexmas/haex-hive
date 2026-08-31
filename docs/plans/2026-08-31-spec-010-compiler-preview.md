# Spec 010 — Compiler & Agent Adapters — Design Preview

**Status**: Preview notes. Not yet a spec. Captured 2026-08-31 during a conversation that mistakenly started drafting this as `Spec 008` before discovering that slot was already reserved for [Install Transaction Contract](2026-08-29-spec-008-install-transaction-requirements.md).

**Purpose**: preserve the design decisions worked out in that conversation so nothing is lost when Spec 010 is properly drafted after Spec 008 and Spec 009 have landed.

**Related**:
- [Spec 007 — Unified Manifest v2](2026-08-28-spec-007-unified-manifest-design.md) — §"Spec 010" is the pre-existing high-level sketch this preview refines.
- [Spec 008 — Install Transaction](2026-08-29-spec-008-install-transaction-requirements.md) — prerequisite.
- [Spec 009 — Hook Boundary](2026-08-29-spec-009-hook-boundary-requirements.md) — prerequisite.
- [Main haex-hive design](2026-08-26-haex-hive-design.md) §Phasing — this fulfils the design-doc's Phase 2 intent ("harness registry + multi-tool compiler") minus the registry piece.

---

## What this covers

The `haex compile` (or equivalent) machinery that turns a project's adopted atoms into working per-tool artifacts on a satellite. Specifically:

- Multi-tool prose delivery (CLAUDE.md, AGENTS.md, GEMINI.md, …) via import syntax where available and byte-copy fallback otherwise.
- Per-tool structured-config translation (`.claude/settings.json`, `.codex/config.toml`, …) from one canonical structured source.
- New `contributes.*` types on the atom-manifest schema so atoms can carry instructions, per-agent settings, and MCP-server declarations.
- Adapter interface for supporting arbitrary agent CLIs over time (initial three, target twenty-four).

## What this does NOT cover (deliberately)

- **A central harness registry with "groups"** mapping project-identity → group(s) → adopted molecules. The original haex-hive design doc's Phase 2 had this; on inspection it added ceremony without net benefit at operator scale, and the operator's personal harness molecule (below) delivers the same "consistency across N projects" outcome more cleanly.
- **Cross-repo architecture map** (which repo uses which SDK, which service talks to which). Legitimate feature, structurally unrelated to harness distribution — probably a future graphify-multi-repo extension. Recorded here so it is not lost; not this spec.
- **Daemon-based auto-recompile**. Deferred to Phase 4 where a satellite daemon exists for relay purposes anyway.

## Terminology (final, aligned to existing codebase)

- **Atom** — structural packaging unit. Directory with `manifest.json` declaring `contributes.*` and optional `includes[]`. Defined by Spec 007. No change.
- **Molecule** — prose-only word for a named bundle of one or more atoms adopted together. No schema. Defined in the graphify-first-authoring design doc. No change.
- **Constitution** — NON-NEGOTIABLE prose (Layer 1 per main design doc). Existing `contributes.constitution`.
- **Instructions** — SHOULD-level prose (Layers 2/3 per main design doc). **New** `contributes.instructions` field on the atom-manifest schema.
- **~~Group~~** — dropped as a Spec 010 concept. What we mean by "sharing a harness across N projects" is handled by the operator's personal harness molecule (below), not by a registry-side project-set declaration.

## Architecture: personal harness molecule, no registry

- The operator maintains a **personal harness repo** — a normal atom-publisher repo where the operator composes their preferred harness by including atoms from any number of external publishers (haex-hive, secana-specs, third-party MCP molecules, …).
- This personal harness repo publishes one or more **profile atoms**: atom manifests with `includes[]` populated (and typically no direct `contributes.*`). This uses Spec 007's already-supported publisher-side `includes[]` — verified against [atom-manifest.v2.schema.json](../../specs/007-unified-manifest-v2/contracts/atom-manifest.v2.schema.json). No schema change needed for composition itself.
- Each consuming project's `.haex-hive.json` adopts the personal harness molecule at a pinned SHA — one entry, one pin, the atom mechanism transitively resolves the rest.
- Adding a new atom to the personal harness → bump the harness's version → bump the `revision`-pin in each consumer project. Consistency across N projects is the operator's discipline (or a batch tool later), not a registry service.
- Multiple personal harnesses are fine — `my-python-harness`, `my-work-harness`, etc. — each project picks one (or more).
- **Publishers remain passive**: secana-specs (or any external publisher) publishes atoms; it does not know or declare who adopts them. The connection is made in the operator's personal harness repo.

## Compiler behaviour

### Invocation and scope

- On-demand `haex compile` subcommand (or an equivalent name). No always-on daemon in Spec 010.
- Write scope limited to (a) per-tool structured-config files and (b) per-tool prose files. Nothing else.
- Idempotent: unchanged inputs → zero writes. A repeated compile on unchanged state must be a no-op.

### Prose delivery: import syntax preferred, byte-copy fallback

- No symlinks. Windows elevation requirements for symlinks are avoided by design.
- Per-tool prose files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, …) resolve to a single canonical assembled markdown at read time.
- Where the target tool supports a file-import directive (Claude Code's `@file`, Codex's `@file` in `AGENTS.md`), the per-tool file is a minimal file whose content is that import directive.
- Where the target tool does not support such an import, the compiler emits a byte-copy of the canonical markdown carrying a compiler-managed integrity marker; drift-detection then applies to that copy.
- **Import-syntax availability per tool must be verified during Spec 010 plan phase.** Claude Code `@file` is known-supported. Codex `@file` in `AGENTS.md` is expected — needs verification. Other CLIs need per-tool investigation.

### Layer merge semantics: strictly additive

- Layer order: `global + molecule/atom + per-project` (or however the atom-inclusion order resolves).
- Arrays: union with dedupe.
- Maps: deep-merge; later layers may add keys but **must never overwrite** existing ones.
- **No removal or replacement mechanism.** A per-project layer attempting to subtract or overwrite an inherited value is a clean refusal from the compiler.
- Rationale: pushes classification into the atom/molecule composition layer instead of ad-hoc per-project overrides. A project that needs a genuine subtraction is a signal that it should adopt a differently-composed molecule, not carry a local exception.

### Drift-on-recompile behaviour

- The compiler must never silently overwrite a compiled output that has been hand-edited since the last run.
- In an interactive TTY: present a unified diff between the drifted file and the freshly computed canonical output; prompt operator to accept, reject, or edit.
- In a non-interactive context (CI, script, pipe): refuse the write and exit with a diagnostic naming the drifted file(s).

## Agent adapters

The compiler must not hardcode a fixed enum of supported tools. Adding a new agent CLI = writing a new adapter + registering it, no core change.

### Adapter interface (four questions per agent)

1. **Prose file path and convention** — e.g. `CLAUDE.md` at repo root, or `AGENTS.md` shared with other tools, or `.github/copilot-instructions.md`.
2. **Import syntax support** — either "yes, `@<relative-path>`" (or whichever syntax the tool defines), or "no → byte-copy fallback".
3. **Structured-config file path and format** — e.g. `.claude/settings.json` (JSON), `.codex/config.toml` (TOML), `mcp-servers.yaml` (YAML). Plus which parts of the canonical config the adapter is responsible for translating.
4. **Auxiliaries** — skill directories, plugin files, workflow files. Are these fixed payloads shipped by the adapter, or generated from atom contributions?

### MVP set (Spec 010 landing target)

- **claude** (Claude Code)
- **codex** (OpenAI Codex CLI)
- **gemini** (Gemini CLI)

### Perspective set (roadmap, matching graphify's supported platforms)

`graphify install --platform` supports these 24 today; Spec 010 adapters should cover them over time in priority order the operator declares:

claude, codex, opencode, kilo, aider, copilot, claw, droid, trae, trae-cn, hermes, kiro, pi, codebuddy, antigravity, antigravity-windows, windows, kimi, amp, devin, gemini, cursor, vscode

They fall into families that map to different adapter shapes:

- **AGENTS.md family** (codex, opencode, aider, claw, droid, trae, trae-cn, kimi, amp, …) — write a section into a shared `AGENTS.md`.
- **Own-prose-file family** (claude → `CLAUDE.md`, gemini → `GEMINI.md`).
- **Skills-directory family** (copilot, hermes, kiro, pi, devin) — write a skill folder under `~/.<tool>/skills/` or `.<tool>/skills/`.
- **Native-plugin/config family** (opencode plugin, kilo plugin, antigravity `.agents/`, cursor `.cursor/`).

The adapter interface must accommodate all four families without special-casing.

## Schema extensions required in Spec 007's atom manifest

Verified against [atom-manifest.v2.schema.json](../../specs/007-unified-manifest-v2/contracts/atom-manifest.v2.schema.json):

- The `contributes` block currently has `additionalProperties: false` and lists exactly: `constitution`, `spec`, `rules`, `hooks`, `skills`. Spec 010 needs to extend this with at least: `instructions` (SHOULD-level prose), and per-agent settings — either as a generalized `agent_configs` map keyed by adapter name, or as explicit fields per adapter (`claude_settings`, `codex_config`, `mcp_servers`, …). Decision deferred to Spec 010's design phase.
- The publisher-side `includes[]` field already supports transitive atom composition — the mechanism the personal harness molecule depends on. **No change needed for composition itself.**

## Explicitly rejected alternatives (recorded so we don't relitigate)

- **Symlinks for prose files** — Windows elevation problem. Import-syntax + byte-copy fallback avoids the whole class of issue.
- **A haex-hive block inside `settings.json` / `config.toml` pointing at our canonical source** — third-party tools ignore unknown keys, so a reference block in a foreign config file has no effect on the tool. Format-translation compilation is unavoidable for these files.
- **Central registry with `group.members: [projectA, ...]`** — adds ceremony without net benefit at operator scale. Personal harness molecule delivers the same "N projects share a harness" outcome via existing atom-composition primitives.
- **Groups defined by publishers** — Publishers must remain passive. Groups (if we ever reintroduce them) belong to the operator, not the publisher.

## Cross-cutting notes

- **Windows**: no elevation required at any point. The `settings.json` / `config.toml` compilation is native file writes; prose delivery is either an import-directive file (single-line text) or a byte-copy (regular text file). Symlinks nowhere.
- **Principle IV** (immutable revisions): every atom reference the compiler follows — including into the operator's personal harness molecule — must be a full-SHA pin. Branch/HEAD references are refused.
- **Principle I** (no secrets): the compiler must not put secret material into any compiled output. Adapter authors must audit their translation for accidental secret leakage.
- **Principle II** (no local absolute paths): compiled outputs must not embed device-local paths.

## Ordering / prerequisites

Spec 010 depends on:

1. **Spec 008 landed** — `haex install` transaction with lock/journal/recovery. The compile step is a natural extension of the install pipeline; without Spec 008's transaction guarantees, the compiler's write-safety story is incomplete.
2. **Spec 009 landed** — `haex hook run` boundary. Non-prose atoms contributing hooks (e.g. graphify-first-authoring) need Spec 009's execution contract to be exercised correctly by the compiler's summary output.

Do not draft Spec 010 before 008 and 009 are at least in-flight.
