# ADR 0019: Declarative Spec Kit integration installation

**Status**: Accepted
**Date**: 2026-09-13
**Related**: Spec 024 (`specs/024-speckit-integration-installer/`), Spec 016 (install hooks), Spec 011 (Spec Kit workflow molecule)

## Context

Spec Kit owns the agent-specific integration artifacts and their layouts. A
direct `specify init` or `specify integration install` invocation can install
the appropriate skills for Claude Code, Codex CLI, and other supported agents.
spaex must not copy those `SKILL.md` files into its own molecules or recreate
the integration rules.

The project still needs one reviewed place to declare that a molecule expects
Spec Kit integrations, select the target agents, pin the required CLI content,
and record the result. The existing `install_hook` mechanism is deliberately a
generic arbitrary-code escape hatch. Making a Spec Kit integration depend on a
publisher-provided hook would make the normal path opaque, harder to validate,
and subject to the hook's non-reversible side effects.

## Decision

Spec Kit integration installation is a first-class declarative molecule
contribution, separate from `install_hook`.

The contribution declares:

- the required Spec Kit CLI version policy;
- the supported Spec Kit integration keys;
- the official integration options required for each key, such as the skills
  option for Codex; and
- no copied Spec Kit skill content.

During `spaex install`, spaex validates the declaration, obtains the selected
agent set from an explicit invocation option, persisted install state, or an
interactive prompt, and invokes the official `specify integration install`
operation once per selected integration. The operation is project-local by
default. spaex records the CLI identity, declaration fingerprint, selection,
and per-agent result in the generation-owned install record.

The external CLI remains the authority for agent-specific paths, file layout,
command names, conflict handling, and compatibility. spaex does not silently
install Python, uv, an agent runtime, or a global integration as part of this
feature.

The official CLI runs outside spaex's rename-swap transaction. If it partially
changes external agent files and then fails, spaex reports the partial external
result and does not publish a successful spaex generation. spaex never claims
to roll back files it does not own.

## Consequences

### Positive

- Spec Kit remains the single source of truth for its integrations.
- Claude, Codex, and future agents use their official native layouts.
- Molecules remain small and do not duplicate external skills.
- Agent selection is explicit, repeatable, and inspectable in the install lock.
- The normal path does not execute arbitrary molecule-provided code.

### Negative

- Agent-file changes are an external side effect and cannot be rolled back by
  spaex's generation transaction.
- spaex must maintain a small adapter around the official CLI and its output
  contract.
- Removing a molecule cannot safely uninstall an integration when another
  molecule or the operator may use it; removal therefore warns by default.

## Alternatives considered

- **Copy Spec Kit skills into spaex molecules**: rejected because it duplicates
  an external format and would drift from the official Spec Kit integrations.
- **Use `install_hook` to run `specify integration install`**: rejected as the
  public contract. It hides a normal capability behind arbitrary code and
  inherits the hook's non-reversible and weakly inspectable side effects.
- **Use `skills.sh` as the Spec Kit installer**: rejected for this feature.
  `skills.sh` is a general Agent Skills distribution tool; the official Spec
  Kit path is the `specify` CLI and its integration commands.
- **Reimplement each agent's integration layout in spaex**: rejected because
  it makes spaex responsible for a contract owned by Spec Kit.
