# Quickstart: Declarative Spec Kit Integration Installer

This quickstart is for implementing and validating Spec 024. It uses a fake
`specify` executable for deterministic tests and does not modify the operator's
real Claude or Codex installation.

## 1. Prepare a fake official CLI

Create a temporary fake CLI for tests. Production molecules declare an exact
`specify-cli` package version; spaex runs it through `uv tool run` without
requiring a separately installed `specify` executable. The fake CLI supports:

```text
specify version
specify integration list
specify integration install claude
specify integration install codex --integration-options=--skills
```

The fake CLI should write markers under the consumer's `.claude/skills/` and
`.agents/skills/` directories and log every invocation. Tests MUST use a temp
directory and MUST NOT write to the real home directory.

## 2. Adopt a fixture molecule

Use an integration fixture publisher with a v4 molecule manifest containing a
`speckit` declaration for `claude` and `codex`. Adopt it at a full SHA with
the normal `spaex add` path.

## 3. Validate the first interactive flow

Run `spaex install` in a pseudo-terminal and select Codex only. Verify:

- the fake CLI receives `integration install codex` and `--skills` as the
  declared integration option;
- no Claude marker is created;
- the install lock records the selected Codex integration and its outcome; and
- no Spec Kit `SKILL.md` content is present in the spaex molecule fixture.

## 4. Validate repeatability

Run `spaex install` again with the same molecule, CLI version, and selection.
Verify that the fake CLI log has no second installation call and no selection
prompt appears.

Then run:

```text
spaex install --speckit-agents claude,codex
```

Verify that only the newly selected Claude integration is installed and the
Codex result remains recorded.

Never use `--speckit-agents all` as an unattended shortcut. If it is supplied,
spaex opens the selector so the operator can review the available integrations
and choose the final set; without an interactive terminal it refuses safely.

## 5. Validate automation and failures

Exercise these cases with the fake CLI:

- `spaex install --speckit-agents codex` with stdin closed: succeeds without a
  prompt;
- non-interactive install without a selection or matching lock: exits with
  `speckit-selection-required`;
- missing `specify`: exits with `speckit-cli-missing`;
- incompatible `specify version`: exits with
  `speckit-cli-version-incompatible`;
- unsupported selected key: exits with
  `speckit-integration-unsupported` before any install call;
- official install exit code 1: exits with `speckit-cli-failed`, leaves the
  prior `.spaex/` generation unchanged, and reports any fake external marker
  that was already written;
- `spaex install --no-speckit-integrations`: publishes other molecule content
  but does not call the fake CLI.

## 6. Live smoke test

Only after the fake-CLI suite passes, run the read-only checks in the current
environment:

```bash
specify version
specify integration list
```

Do not run a live install against the operator's home or this repository unless
the operator explicitly requests that external agent files be changed.
