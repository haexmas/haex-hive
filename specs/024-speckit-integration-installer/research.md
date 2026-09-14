# Research: Declarative Spec Kit Integration Installer

## Decision 1: Delegate agent integration layout to the official Spec Kit CLI

**Decision**: spaex invokes `specify integration install <key>` for each selected
integration and does not copy or synthesize Spec Kit skill files.

**Rationale**: The official Spec Kit integration reference identifies the
agent-specific keys and layouts. Claude Code uses `.claude/skills`; Codex CLI
uses `.agents/skills` and its skills mode. The official CLI also owns command
names, compatibility checks, managed-file hashes, and multi-install behavior.

**Evidence**: The official integration reference documents `claude` and
`codex` as skills-based integrations, and the official installation guide
documents `specify init` and the integration installation flow:

- https://github.github.com/spec-kit/reference/integrations.html
- https://github.com/github/spec-kit/blob/main/docs/installation.md

**Alternatives considered**:

- Copying `SKILL.md` files into a spaex molecule would duplicate external
  content and was rejected by the skills-externalization decision.
- Calling `npx skills add` would use a general distribution layer instead of
  the official Spec Kit integration contract.

## Decision 2: Add a typed molecule contribution, not an install hook

**Decision**: Add a first-class `speckit` declaration to the molecule manifest.
The declaration is metadata and contains no skill files. The installer invokes
the official CLI through a small spaex-owned runner.

**Rationale**: The current `install_hook` contract intentionally executes
arbitrary publisher code and cannot reverse its side effects. Spec Kit
installation is a known, reviewable capability and needs schema validation,
selection handling, lock recording, and deterministic conflict behavior.

**Alternatives considered**:

- A publisher-provided `install.py` hook is retained only for unrelated escape
  hatches, not used for the normal Spec Kit path.
- A generic external-action framework is unnecessary for the first feature and
  would broaden the public model without a second concrete consumer.

## Decision 3: Require an exact or lower-bound Spec Kit CLI policy; do not provision toolchains

**Decision**: The declaration carries a `version_constraint` using spaex's
existing exact/lower-bound grammar. spaex verifies the `specify` executable and
its reported version before installation. The first implementation does not
silently install Python, uv, or an agent runtime.

**Rationale**: The current repository already treats external toolchains as
operator-managed. Automatic provisioning would add network, privilege, and
rollback concerns unrelated to selecting project-local integrations. Recording
the effective CLI version still makes the external input visible and allows a
project to require an exact version when reproducibility matters.

**Alternatives considered**:

- Running an unpinned `latest` CLI was rejected because the installed skill
  content could change without a molecule revision change.
- Automatically provisioning `specify-cli` through uv/pip was deferred; it is
  a separate toolchain-management feature.

## Decision 4: Persist selection and outcomes in the install generation

**Decision**: The selected integration set and successful outcomes are recorded
in the molecule's install-lock entry. Selection precedence is:

1. explicit `spaex install`/`spaex add` command-line selection;
2. matching persisted selection from the current install lock;
3. interactive prompt when a TTY is available;
4. refusal in non-interactive mode when no selection exists.

**Rationale**: The lock is already the generation-owned record for installed
molecule state. Keeping the selection there avoids silently editing the
consumer manifest merely because an interactive install occurred. An explicit
command-line selection can create a new generation with a new recorded
selection.

**Alternatives considered**:

- Persisting an interactive answer directly in `.spaex/manifest.json` would
  turn an install-time choice into a manifest mutation and complicate the
  existing manifest lock flow.
- Prompting on every install would make normal repeated installs noisy and
  unsuitable for automation.

## Decision 5: Run selected integrations serially and outside the file swap

**Decision**: The runner invokes one official install operation per selected
integration in canonical key order. It runs before the spaex generation is
published, but its external files are not part of the rename-swap transaction.

**Rationale**: Per-agent outcomes become observable and deterministic. The
official CLI may create files outside `.spaex/`; spaex cannot safely restore
those files if a later agent installation fails. The lock therefore records
only a successful completed generation, while failures report any partial
external action without claiming rollback.

**Alternatives considered**:

- One opaque multi-agent subprocess would lose per-agent diagnostics.
- Pretending external files are transactionally rolled back would be unsafe
  and misleading.

## Decision 6: Use the lock fingerprint for the clean no-op path

**Decision**: If the lock contains the same molecule revision, declaration
fingerprint, CLI version, selected agent set, and successful outcomes, spaex
does not invoke the external installer again. If any input changes, spaex
revalidates and invokes the official CLI for the affected integrations.

**Rationale**: The current official `specify integration list` command is a
human-readable status surface, not a stable machine-readable ownership API.
The lock gives spaex a deterministic no-op decision without reimplementing
Spec Kit's file ownership model. The official CLI remains responsible for
conflicts when an installation is actually needed.

**Alternatives considered**:

- Reimplementing every agent's managed-file path and hash rules in spaex was
  rejected because those rules belong to Spec Kit.
- Running the external installer on every spaex install would violate the
  no-op expectation and could repeatedly prompt on modified files.

## Decision 7: Project-local integrations only in the first implementation

**Decision**: spaex invokes project-local Spec Kit integrations. Global
installation is rejected as unsupported in this feature and may be added as a
separate, explicitly requested scope.

**Rationale**: Project-local output is reviewable with the project and avoids
mutating a user's home directory from a repository manifest. It also matches
spaex's per-repository composition boundary.

## Current environment observation

The current checkout has Spec Kit `0.8.1.dev0` installed. `specify version`,
`specify integration list`, and `specify integration install --help` are
available; Claude is currently marked installed and Codex is available but not
installed. The implementation tests must use a fake `specify` executable for
deterministic contract tests and reserve live CLI checks for an opt-in smoke
test.

## Amendment 2026-09-14: Provision the pinned CLI through uv

The original Decision 3 deliberately left CLI provisioning to the operator.
That boundary does not meet the intended molecule user experience: adopting a
reviewed molecule should be sufficient to install its selected integrations.
The follow-up decision is to add an optional `speckit.cli` block containing the
fixed `specify-cli` package and exact version. spaex invokes that package via
its runtime `uv` dependency and `uv tool run`, preserving isolation and the
no-global-PATH rule. Declarations without the block retain the legacy
PATH-based behavior for compatibility.
