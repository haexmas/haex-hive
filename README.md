# haex-hive

A CLI and specification set for building **portable, review-gated project harnesses** — the pinned constitutions, skills, and instruction atoms an AI agent must respect when working inside a repository.

`haex-hive` treats a project's guardrails as versioned artifacts: assembled from immutable, cross-repo references (`repository + commit SHA + path`), opt-in per project, and never carrying secrets or device-local paths.

> **Status:** `2.0.0.dev0` — the manifest v2 CLI surface (Spec 007) has landed. The install transaction (Spec 008) is in progress on `008-install-transaction`. Interfaces are not yet stable.

## Install

Not published to PyPI yet. Install from a local checkout:

```bash
git clone https://github.com/haexmas/haex-hive.git
cd haex-hive
pip install -e .
```

Requires Python 3.10+ and Git 2.30+ on `$PATH`. Only runtime dependency is `jsonschema`.

## The `haex` CLI

```bash
haex migrate                # rewrite a v1 .haex-hive.json into the v2 sidecar
haex constitution assemble  # produce .haex-hive/constitution.md + install.lock
haex constitution show      # print the effective constitution to stdout
```

Every write goes through a **sidecar → review → replace** flow: migrations write to `.migrated`, constitution assembly stages into `.haex-hive/*.lock`, and no versioned config file is ever rewritten in place by the tool.

See [specs/007-unified-manifest-v2/quickstart.md](specs/007-unified-manifest-v2/quickstart.md) for a full walkthrough of each command, including the multi-source LLM-merge flow and every refusal path.

## Core Model

A project opts into haex-hive by committing a `.haex-hive.json` at its root. That file is a **manifest of atoms** — each atom names an external harness source pinned by commit SHA:

```json
{
  "haex_hive_version": "2",
  "identity": "com.github.acme.my-project",
  "atoms": [
    {
      "source": "https://github.com/haexmas/haex-hive",
      "revision": "443c3af57255f3d85a57774c1f54439190462534",
      "includes": ["com.github.haexmas.haex-hive.constitution"]
    }
  ]
}
```

`haex constitution assemble` resolves the atoms, merges their content, and writes the effective constitution plus an `install.lock` recording exactly which SHA supplied which section. Two satellites resolving the same manifest on different days see byte-identical output.

## Non-Negotiable Principles

The constitution enforces eight NON-NEGOTIABLE principles. Every spec, plan, and tool in this repo respects them:

1. **No secrets in git** — repos carry identity aliases; key material lives in the OS keychain.
2. **No local absolute paths in versioned config** — output must resolve identically on Linux, macOS, WSL2.
3. **Project identity is device-independent** — a project is its git remote (or `.harness-id`), never a path.
4. **Cross-repo references pin immutable revisions** — full commit SHAs only; no branches or `HEAD` for consumed content.
5. **External sources are opt-in per project** — no `.haex-hive.json`, no inheritance. The allowlist is a trust boundary.
6. **Self-modifying instructions are always review-gated** — no in-place rewrites of versioned config; migrations use sidecars.
7. **Relay unavailability never blocks local work** — the Nostr liveness plane is optional; all content resolves from git.
8. **No concealment instructions in agent output** — agents may not tell downstream readers to hide anything from the operator.

The authoritative text lives in [.haex-hive/constitution.md](.haex-hive/constitution.md); amendments follow the procedure in Principle VI.

## Repository Layout

| Path | Purpose |
|---|---|
| `src/haex_hive/` | Python package (`haex` CLI, constitution assembly, migration, schema) |
| `.haex-hive/` | This repo's own assembled constitution and install lock |
| `.specify/` | Spec-kit workspace: constitutions, atom definitions, scripts |
| `specs/` | Numbered specifications (001 → 008) driving the implementation |
| `docs/adr/` | Architecture decision records |
| `docs/plans/` | Design documents behind each spec |
| `tests/` | Pytest suite (`pytest -m 'not slow'` by default) |

## Development

```bash
pip install -e '.[dev]'
pytest                    # fast suite
pytest -m slow            # opt-in end-to-end scenarios
ruff check .
mypy
```

Contributions follow the PR / conventional-commits flow in
[docs/adr/0006-development-workflow-pr-flow-and-conventional-commits.md](docs/adr/0006-development-workflow-pr-flow-and-conventional-commits.md).

## License

Apache-2.0 — see [pyproject.toml](pyproject.toml).
