# Feature Specification: Declarative Spec Kit Integration Installer

**Feature Branch**: `024-speckit-integration-installer`
**Created**: 2026-09-13
**Status**: Draft
**Input**: User description: "Ein spaex-Molecule soll die offizielle Spec-Kit-CLI referenzieren und die Spec-Kit-Skills optional für die vom Nutzer ausgewählten Agents installieren."

**Related decisions**:

- [Spec Kit integration reference](https://github.github.com/spec-kit/reference/integrations.html)
- [Spec Kit installation guide](https://github.com/github/spec-kit/blob/main/docs/installation.md)
- [Spec 016: Molecule Install Hooks](../016-molecule-install-hooks/): existing arbitrary side-effect escape hatch; this feature deliberately does not use it as the public contract.
- [Spec 011: Speckit Workflow Molecule](../011-speckit-workflow-atom/): existing workflow publication design; this feature installs the official agent integrations separately.
- [Scope Realignment](../../docs/plans/2026-09-03-scope-realignment-design.md): skills remain external and spaex consumes foreign formats rather than republishing skill content.

## User Scenarios & Testing

### User Story 1 - Select Spec Kit agents during installation (Priority: P1)

A project maintainer adopts a molecule that provides the project's Spec Kit integration policy. During `spaex install`, the maintainer sees the supported Spec Kit agent integrations declared by the molecule and chooses which ones to install, such as Claude Code, Codex CLI, or Gemini CLI. The installer then invokes the official Spec Kit integration installer for each selected agent. The molecule does not carry duplicate `SKILL.md` files.

**Why this priority**: The central value is one reviewed project declaration that makes the same Spec Kit workflow available to the project's selected agents without maintaining separate agent-specific copies in spaex.

**Independent Test**: Given a consumer with the Spec Kit integration molecule adopted and a usable `specify` CLI, an interactive `spaex install` presents the declared agents, installs only the selected integrations, and records the result.

**Acceptance Scenarios**:

1. **Given** a molecule declaring Claude Code and Codex as supported integrations, **When** the maintainer selects only Codex, **Then** spaex invokes the official Codex integration installation and does not install the Claude integration.
2. **Given** a molecule declaring several supported integrations, **When** the maintainer selects all detected integrations, **Then** spaex installs each selected integration through the official Spec Kit CLI and reports the resulting agent-specific locations.
3. **Given** the maintainer selects no integrations, **When** installation continues, **Then** spaex publishes the normal molecule state without modifying any agent integration files and records that Spec Kit integration installation was skipped.

### User Story 2 - Reuse the same selection deterministically (Priority: P1)

A maintainer has selected the desired agents once. Later `spaex install` runs reuse that selection without asking again unless the molecule revision, declared integration set, or local selection changes. A second install does not duplicate, reorder, or unnecessarily rewrite Spec Kit integration files.

**Why this priority**: Repeated installs are normal in spaex. An installer that prompts on every run or rewrites agent files unnecessarily would make adoption disruptive and difficult to automate.

**Independent Test**: Run `spaex install` twice with unchanged molecule, CLI, and selection state. The second run produces no external integration changes and no new prompt.

**Acceptance Scenarios**:

1. **Given** a successful Codex integration installation recorded in the current lock state, **When** the maintainer runs `spaex install` again without changing inputs, **Then** spaex reports the integration as already satisfied and does not invoke a second installation.
2. **Given** the maintainer changes the selected agents from Codex to Claude plus Codex, **When** `spaex install` runs, **Then** only the newly selected Claude integration is installed and the existing Codex selection remains active.
3. **Given** the adopted molecule changes its Spec Kit revision or declared integration options, **When** `spaex install` runs, **Then** spaex detects the changed installation input and applies the new selection after confirmation.

### User Story 3 - Use the official Spec Kit integration contract (Priority: P1)

A project maintainer receives the same integration artifacts and invocation semantics as a direct Spec Kit installation. spaex delegates the agent-specific file layout, command names, compatibility checks, and integration bookkeeping to the official `specify` CLI instead of reimplementing them.

**Why this priority**: Spec Kit owns the contract for its integrations. Reimplementing it in spaex would cause drift and would recreate the agent-specific skill distribution that the architecture intentionally externalizes.

**Independent Test**: For each supported target in the conformance matrix, compare a spaex-mediated installation with the equivalent official `specify integration install` invocation and verify that the same managed integration artifacts and command entry points are available.

**Acceptance Scenarios**:

1. **Given** a selected Claude Code integration, **When** spaex installs it, **Then** the resulting Spec Kit skills are located and invoked according to the official Claude integration contract.
2. **Given** a selected Codex integration, **When** spaex installs it with the official skills option, **Then** the resulting Spec Kit skills are located and invoked according to the official Codex integration contract.
3. **Given** an integration that the installed Spec Kit CLI does not support, **When** the maintainer attempts to select it, **Then** spaex refuses before modifying agent files and reports the available integration keys.

### User Story 4 - Run safely in automation (Priority: P2)

A CI job or another non-interactive caller can install the declared integrations without hanging on an agent-selection prompt. The caller can explicitly provide the desired integrations or explicitly disable Spec Kit integration installation. Missing tools, invalid selections, and failed official CLI invocations produce actionable diagnostics.

**Why this priority**: The same project manifest must work for local development and reproducible automation, while automation must never make an implicit agent choice.

**Independent Test**: Run the installer without a TTY once with an explicit agent selection and once without a selection. The first run completes for the selected agents; the second refuses or skips according to the documented non-interactive policy without waiting for input.

**Acceptance Scenarios**:

1. **Given** a non-interactive invocation with an explicit Codex selection, **When** `spaex install` runs, **Then** it installs Codex without prompting.
2. **Given** a non-interactive invocation without a persisted or explicit selection, **When** `spaex install` reaches the Spec Kit integration step, **Then** it refuses with a diagnostic explaining how to provide the selection or disable the step.
3. **Given** that `specify` is missing, has an incompatible version, or exits non-zero, **When** a non-empty integration selection is requested, **Then** spaex refuses the integration step without claiming success and identifies the failing prerequisite or command.

### Edge Cases

- The molecule declares no integrations: installation succeeds without an external Spec Kit action.
- The molecule declares an integration that is not available in the installed `specify` CLI: validation refuses before any selected integration is installed.
- The selected integration is already installed and its managed files are unchanged: spaex treats it as satisfied.
- A selected integration has locally modified files: spaex delegates conflict handling to the official Spec Kit CLI and does not silently overwrite user changes.
- Two adopted molecules declare incompatible Spec Kit integration policies: spaex refuses before invoking the official CLI; no precedence-by-install-order is allowed.
- The user cancels the agent-selection prompt: normal molecule publication remains unchanged, and the Spec Kit step records cancellation as not installed rather than as success.
- The official CLI partially installs several requested integrations before failing: spaex reports the partial external result, preserves the previous spaex generation, and does not claim an atomic rollback of files owned by the external CLI.
- The consumer removes the molecule after integrations were installed: spaex warns that external Spec Kit files may remain and does not silently uninstall integrations that may also be used by another project or molecule.

## Requirements

### Functional Requirements

- **FR-001**: A molecule MAY declare a Spec Kit integration contribution without carrying copies of the Spec Kit `SKILL.md` files.
- **FR-002**: The Spec Kit integration declaration MUST identify the Spec Kit source and an immutable revision or an exact CLI version policy sufficient to identify the integration content used for installation.
- **FR-003**: The declaration MUST identify the supported Spec Kit integration keys and the Spec Kit-specific options required by each integration, including the skills option for integrations that require it.
- **FR-004**: `spaex install` MUST validate the declaration before invoking any external Spec Kit command. Invalid source, revision, integration key, duplicate target, or unsupported option MUST refuse with a diagnostic and zero external invocations.
- **FR-005**: In an interactive terminal, `spaex install` MUST allow the operator to select zero or more integrations from the declared and currently supported set, unless a persisted selection or explicit command-line selection already exists.
- **FR-006**: In a non-interactive invocation, `spaex install` MUST NOT prompt. It MUST use an explicit command-line selection or a previously persisted selection; otherwise it MUST refuse the Spec Kit step with an actionable diagnostic.
- **FR-007**: The operator MUST be able to explicitly disable Spec Kit integration installation for one invocation without disabling the molecule's other contributions.
- **FR-008**: For every selected integration, spaex MUST invoke the official `specify integration install <key>` operation and MUST NOT reimplement the integration's agent-specific file layout or command semantics.
- **FR-009**: Before invoking the official CLI, spaex MUST provision the declared exact `specify-cli` package through its bundled `uv` dependency when a CLI provisioning declaration is present, then verify that the resulting pinned runner satisfies the molecule's declared version policy. spaex MUST NOT install an agent runtime implicitly as part of this feature.
- **FR-010**: spaex MUST pass the integration-specific options declared by the molecule, including `--skills` where required by the official integration contract.
- **FR-011**: spaex MUST record the selected integrations, the effective Spec Kit CLI version or immutable source revision, the declaration identity, and each integration outcome in the install lock or an equivalent generation-owned record.
- **FR-012**: Repeating `spaex install` with unchanged declaration, CLI identity, selection, and successful integration state MUST be a no-op with respect to external Spec Kit files and MUST NOT prompt.
- **FR-013**: A changed selection MUST install only newly selected integrations and MUST preserve the recorded state of unchanged integrations.
- **FR-014**: A failed official CLI invocation MUST produce a non-zero spaex result for the Spec Kit step, name the integration and failure category, and MUST NOT record that integration as successfully installed.
- **FR-015**: External Spec Kit file changes MUST remain distinguishable from spaex-owned files. spaex MUST NOT delete or overwrite locally modified external integration files without the official CLI's conflict behavior and explicit operator consent.
- **FR-016**: Removing a molecule that provided Spec Kit integrations MUST emit a warning about external files that may remain. Automatic uninstallation is out of scope unless a later contract proves ownership and safe removal.
- **FR-017**: The feature MUST remain independent of `install_hook`; a conforming Spec Kit integration declaration MUST be installable without an arbitrary molecule-provided script.
- **FR-018**: The installer MUST refuse or warn on conflicting declarations from multiple adopted molecules; it MUST NOT resolve conflicts by declaration order or install order.
- **FR-019**: The installer MUST expose a machine-readable outcome for each requested integration, including `installed`, `already_satisfied`, `skipped`, `cancelled`, `unsupported`, and `failed` states where applicable.
- **FR-020**: The conformance suite MUST cover at least Claude Code and Codex CLI, including project-local target paths, repeated installation, unsupported integration selection, missing `specify`, non-interactive invocation, and modified managed files.

### Key Entities

- **Spec Kit integration declaration**: The molecule-owned description of the external Spec Kit source, version/revision policy, supported integration keys, and integration-specific options.
- **Integration selection**: The consumer-owned set of agent integrations selected for the current project, persisted so repeated installs do not prompt unexpectedly.
- **Integration outcome**: The per-agent result reported by spaex and stored with the current install generation.
- **External integration artifact**: A file or directory created and managed by the official Spec Kit CLI in an agent-specific project path such as `.claude/skills/` or `.agents/skills/`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In a clean fixture project, a maintainer can adopt the molecule and complete a first interactive installation for one selected agent without manually copying a Spec Kit skill file.
- **SC-002**: For Claude Code and Codex CLI, 100% of conformance runs with a valid selection produce the official agent-specific Spec Kit integration layout and expose the documented Spec Kit commands for that agent.
- **SC-003**: 100% of repeated installs with unchanged inputs produce no new external Spec Kit file writes and no selection prompt.
- **SC-004**: 100% of non-interactive installs without an explicit or persisted selection terminate deterministically with an actionable result and never block waiting for input.
- **SC-005**: 100% of unsupported-agent, missing-CLI, incompatible-version, and official-CLI-failure cases report the affected integration and do not record it as successfully installed.
- **SC-006**: No conforming installation path stores duplicate Spec Kit `SKILL.md` content in a spaex molecule.
- **SC-007**: A consumer can inspect the install record and determine which integrations were selected, which CLI identity was used, and whether each integration was installed, skipped, already satisfied, cancelled, unsupported, or failed.

## Assumptions

- The official Spec Kit CLI remains the authority for integration layouts, command naming, file ownership, and agent-specific compatibility.
- The first implementation supports project-local integrations only. Global agent installation is out of scope unless explicitly added by a later requirement.
- The `specify` CLI is provisioned through spaex's bundled `uv` dependency when the molecule supplies a pinned CLI declaration. The feature does not install an agent runtime or modify the user's PATH.
- The molecule's external Spec Kit reference is reviewed and pinned before installation. A moving branch or `latest` reference is not sufficient for reproducible content.
- A project may select multiple Spec Kit integrations when the installed Spec Kit CLI declares them safe; otherwise the operator must explicitly acknowledge the CLI's multi-install safety requirement.
- External CLI side effects are not part of spaex's atomic file-generation rollback. spaex records the result and reports partial external changes rather than pretending to undo them.
- Skills remain external Agent Skills content. spaex owns selection, orchestration, provenance, and lifecycle diagnostics, not the Spec Kit skill text.
