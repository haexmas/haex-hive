# ADR 0020: uv-managed Spec Kit CLI provisioning

**Status**: Accepted
**Date**: 2026-09-14
**Supersedes**: The CLI-provisioning boundary in ADR 0019

## Context

ADR 0019 implemented delegation to the official Spec Kit CLI but left
`specify` installation to the operator. That does not provide the intended
experience for a molecule: adopting a pinned Spec Kit molecule should be
enough to install its selected agent integrations.

spaex already runs on Python and now carries `uv` as a runtime dependency.
The official Spec Kit distribution is the `specify-cli` package, so spaex can
run an exact package version without copying Spec Kit files or changing the
user's PATH.

## Decision

A `speckit.cli` declaration may name the fixed `specify-cli` package and an
exact semantic version. When present, spaex invokes the CLI through the
installed uv module:

```text
python -m uv tool run --from specify-cli==X.Y.Z specify ...
```

`uv tool run` creates or reuses an isolated cached tool environment. The
declaration fingerprint includes the package and exact version, while the
install lock records the effective CLI version as before. An explicit
executable override remains available to deterministic tests and legacy
declarations without `speckit.cli`.

The feature provisions the Spec Kit CLI only. It does not install or configure
Claude Code, Codex CLI, or another agent runtime, and it does not update shell
startup files or the user's PATH.

spaex's supported Python baseline is pinned to the Python 3.14 minor series;
the repository development interpreter is pinned to the current 3.14 patch
release in `.python-version` and CI.

## Consequences

- A conforming molecule can install its selected Spec Kit integrations without
  a pre-existing `specify` executable.
- The first invocation may download the pinned package and its dependencies;
  network and package-index failures are surfaced as install failures.
- The uv dependency increases spaex's distribution footprint and requires
  platform testing for uv's supported wheels.
- Existing declarations without `speckit.cli` retain the legacy PATH-based
  behavior until their publisher adds the pinned provisioning block.
