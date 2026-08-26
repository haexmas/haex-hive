# Implementation Plan: Phase 0 — Pilot Harness in haex-hive Itself

**Branch**: `001-phase-0-pilot-harness` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-phase-0-pilot-harness/spec.md`

## Summary

Make haex-hive the first pilot consumer of its own harness. Land a canonical
constitution (already committed as v1.0.0), a per-project system declaration
with an empty external-sources allowlist, per-tool adapter files (`CLAUDE.md`,
`AGENTS.md`) that reference the canonical instruction without duplicating it,
and a discoverable pointer to the currently active phase and feature. Then
prove — by hand, using a runnable checklist committed alongside the spec —
that fresh agent sessions in at least two supported CLIs reconstruct the full
working context from repository state alone, hand off cleanly between tools,
and refuse to inherit external harness content.

Technical approach: purely local, single-repo, single-machine. Filesystem-level
mechanisms only (files, symlinks-where-available, one JSON pointer). No
services, no daemons, no relay, no build step. The whole point of Phase 0 is
to prove the harness works in its simplest possible form before any of the
liveness-plane infrastructure gets built.

## Technical Context

**Language/Version**: N/A — Phase 0 delivers no runnable code. Artifacts are
Markdown, YAML, and JSON only.
**Primary Dependencies**: git; the spec-kit toolchain already installed under
`.specify/`; whichever supported agent CLIs are installed on the validation
machine (Claude Code confirmed present; second CLI to be confirmed during
research).
**Storage**: git objects and the working tree. No database, no cache, no
external store.
**Testing**: manual fresh-session validation against a committed checklist
(User Stories 1–3 in the spec). No automated evaluator in Phase 0 — that is
deferred to a later phase per the design doc.
**Target Platform**: Linux workstation (this machine). Windows/WSL2 and macOS
compatibility is a stated constitutional invariant (Principle II) but is not
validated in Phase 0 — only the parts we can hand-verify on this one machine
are in scope here.
**Project Type**: harness/documentation. Not a service, library, or
application in the traditional sense — the "product" is a set of files that
condition how an agent behaves in this repo.
**Performance Goals**: N/A.
**Constraints**:
- No absolute paths in versioned files (Principle II).
- No secret material in versioned files (Principle I).
- All 8 functional requirements from the spec MUST be satisfied simultaneously
  — none may be traded off against another.
- Validation MUST be repeatable by a future contributor in under 15 minutes
  (SC-005).
**Scale/Scope**: one repo, one machine, two CLIs, three user stories, eight
functional requirements. Deliberately small.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0 — the seven
NON-NEGOTIABLE principles.

| Principle | Status | Notes |
|-----------|--------|-------|
| I. No Secrets in Git | ✅ PASS | Plan introduces no secret material. Adapter files reference identity aliases only if at all; no keys, tokens, or passwords committed. |
| II. No Local Absolute Paths in Versioned Config | ✅ PASS | All planned artifacts (`.specify/system.yaml`, adapter files, checklist) use repo-relative paths or no paths. `.specify/feature.json` (already committed) uses the repo-relative form `specs/001-phase-0-pilot-harness`. |
| III. Project Identity Is Device-Independent | ✅ PASS | Phase 0 is single-machine; no cross-device addressing introduced. Nothing planned violates the invariant when future phases arrive. |
| IV. Cross-Repo References Pin Immutable Revisions | ✅ PASS | Phase 0 declares an EMPTY external-sources allowlist, so no cross-repo references exist. Compliance is trivial. |
| V. External Sources Are Opt-in Per Project | ✅ PASS | The empty allowlist is the strictest possible expression of this principle. FR-003 mandates it; US3 validates it. |
| VI. Self-Modifying Instructions Are Always Review-Gated | ✅ PASS | No reflection pipeline installed in Phase 0. No mechanism exists for the agent to modify its own instructions. Compliance vacuous but complete. |
| VII. Relay Unavailability Never Blocks Local Work | ✅ PASS | No relay dependency in Phase 0 whatsoever. Everything is local files. |

**Gate result**: PASS on all seven principles at plan time. No complexity
tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/001-phase-0-pilot-harness/
├── plan.md              # This file
├── research.md          # Phase 0 output: resolves the one unknown (second CLI availability)
├── quickstart.md        # Phase 1 output: the runnable fresh-session validation checklist for a human
├── contracts/
│   └── system-yaml.schema.md   # Phase 1 output: the concrete `.specify/system.yaml` shape this repo must expose
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

`data-model.md` is intentionally omitted: this feature has no runtime data
model. The Key Entities section of `spec.md` describes documentation
artifacts, not persistent data — capturing them again in a `data-model.md`
would be redundant. This is a deliberate deviation from the plan template's
default outputs, permitted because the feature has no persistent-data
component to model.

### Source Code (repository root)

Phase 0 delivers no source code. The artifacts that ship live at these paths
(all repo-relative):

```text
CLAUDE.md                        # thin adapter, already exists (spec-kit init)
AGENTS.md                        # thin adapter, TO BE CREATED
.specify/memory/constitution.md  # canonical instructions, already committed
.specify/system.yaml             # per-project system declaration, TO BE CREATED
.specify/feature.json            # active-feature pointer, already committed
docs/plans/2026-08-26-haex-hive-design.md   # design doc, already committed
specs/001-phase-0-pilot-harness/quickstart.md   # runnable validation checklist
```

**Structure Decision**: the harness surface for this repo is exactly the files
above. No `src/`, no `tests/`, no packages. The only "test" is the manual
fresh-session validation checklist under `specs/001-phase-0-pilot-harness/quickstart.md`.

## Complexity Tracking

None. All seven constitution gates pass at plan time without justification
entries.

## Phase 0: Outline & Research

The spec left one item explicitly conditional and one implicit — both need
resolution before task generation.

Research tasks:

1. **Which second CLI, actually available on this machine, will be used for
   the cross-tool handoff test?** Spec assumption names Codex as the default
   with "any other supported CLI" as fallback. Check `which codex` / `codex
   --version`. If absent, enumerate what IS installed (gemini, qwen, opencode,
   etc.) and pick one. Record the decision.
2. **Does the chosen second CLI actually read an `AGENTS.md` file at the repo
   root?** If it uses a different filename or location, the FR-002 wording
   ("per-tool adapter files … at the repo root") is satisfied by producing
   that alternate file; the spec is neutral about the exact filename. Confirm
   what the second CLI reads and document it.
3. **On this filesystem: are symlinks supported for the adapter files?** The
   spec permits "symlink where possible, thin reference otherwise". On this
   Linux workstation the answer is trivially yes, but the plan should record
   the fact so future contributors on constrained filesystems (Windows without
   Developer Mode, network filesystems that flatten symlinks) know what the
   fallback is.

Output: `research.md` recording the three decisions with rationale and
alternatives considered.

## Phase 1: Design & Contracts

### No `data-model.md`

Justified above: no runtime data model.

### Contract: `.specify/system.yaml` schema

The one contract this feature exposes is the *shape* of the
`.specify/system.yaml` file, because anything future haex-hive tooling reads
must agree with it. It is captured as a small schema-and-example document
under `contracts/system-yaml.schema.md`.

The Phase 0 concrete instance for haex-hive itself will have:

```yaml
system:
  id: haex-hive
external_sources:
  allowed: []
```

The contract document defines the required top-level keys, the meaning of
each, and the allowed value shapes.

### Quickstart

`quickstart.md` is the runnable-by-a-human validation checklist covering User
Stories 1–3 from the spec. It is not narrative; it is a numbered sequence of
prompts to issue in fresh sessions plus expected-outcome checkboxes. SC-005
requires it to be executable in under 15 minutes.

### Agent context update

Per the plan skill's outline: update the `<!-- SPECKIT START -->…<!-- SPECKIT
END -->` block in `CLAUDE.md` to point at this plan file. Also produce a
matching `AGENTS.md` at the repo root that either symlinks to the canonical
instruction file or thin-references it, per the research outcome.

### Re-evaluated Constitution Check post-design

All seven gates still pass. Design does not introduce any new artifact type,
identity, path, dependency, or self-modification mechanism that would touch a
principle. Re-check clean.

## Next Command

`/speckit-tasks` — decomposes this plan into dependency-ordered tasks under
`tasks.md`.
