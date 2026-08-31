# haex-hive

A CLI and specification set for building **portable, review-gated project harnesses** — the pinned constitutions, skills, and instruction atoms an AI agent must respect when working inside a repository.

> **Status:** `2.0.0.dev0` — the manifest v2 CLI surface (Spec 007) has landed. The install transaction (Spec 008) is in progress on `008-install-transaction`. Interfaces are not yet stable.

## Vision

haex-hive is being built to solve one problem end-to-end: doing serious AI-assisted development across **multiple devices, multiple git accounts, and multiple agent CLIs** without giving up autonomy on any single satellite.

The picture:

- **A hive of satellites.** Your laptop, your workstation, a remote VM — each one runs agent CLIs (Claude Code, Codex, Gemini, …) fully locally, including with local models. No central VM is a single point of failure; every satellite can complete real work offline.
- **Layered harnesses instead of copy-pasted `CLAUDE.md`s.** A thin global layer that always applies, plus reusable groups (not necessarily tied to one git remote or account), plus per-project overrides. Defined once, pinned by commit SHA, consumed by any agent CLI that follows the harness contract.
- **Multi-account by default.** Private and professional GitHub/GitLab identities live side by side; a project only inherits what its own `.haex-hive.json` explicitly opts into.
- **Optional mobile visibility.** A future liveness plane (self-hosted Nostr relay) will let you see running sessions from your phone and hand new instructions to any satellite — but its unreachability never blocks local work. Git alone is enough for the code plane.

The full design lives in [docs/plans/2026-08-26-haex-hive-design.md](docs/plans/2026-08-26-haex-hive-design.md). What ships today is the config-plane foundation; the liveness plane, mobile client, and multi-CLI compiler are on the roadmap.

## What you can do today

The `haex` CLI covers the **constitution** portion of the config plane. As an operator you can:

1. **Migrate a legacy v1 `.haex-hive.json` into the v2 shape** — `haex migrate` writes a `.migrated` sidecar with a reviewable unified diff; the original file is untouched until you replace it manually.
2. **Assemble a single-source constitution deterministically** — one `atoms[]` entry pointing at a constitution atom pinned by SHA produces a byte-for-byte copy of the source file at `.haex-hive/constitution.md`, plus an `install.lock` recording atom-ID, revision, source URL, and a SHA-256 content hash.
3. **Assemble a multi-source constitution via reviewed LLM merge** — with N atoms all contributing a constitution (e.g. base + team overlay), `haex constitution assemble` on a device with LLM access loads every source, asks you interactively to resolve conflicts, and writes the reconciled result. You commit the file plus its recorded hash; other satellites `git pull` and verify it byte-for-byte without re-running the LLM.
4. **Inspect the effective constitution on any satellite** — `haex constitution show` prints an "Assembled from" preface synthesized from `install.lock` (one line per source with atom-ID + SHA + URL), a `---` separator, then the constitution content. `--no-preface` for scripting.

Spec 008, in flight on `008-install-transaction`, extends this to a full `haex install` command that publishes atoms atomically across `.haex-hive/`, `.claude/`, `.codex/` and other participating roots — with concurrent-install safety, crash recovery, and delta-driven cleanup when an atom is removed.

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

`haex constitution assemble` resolves the atoms and writes both the effective constitution and an `install.lock` recording which SHA supplied which section together with a SHA-256 content hash. For a **single-source** manifest, assembly is fully deterministic — two satellites resolving the same pinned SHA see byte-identical output. For a **multi-source** manifest, an interactive LLM merge produces a reviewed `constitution.md` that the operator commits; other satellites `git pull` and use the committed content, and the recorded hash lets them verify integrity without re-running the LLM.

## Non-Negotiable Principles

The constitution enforces eight NON-NEGOTIABLE principles. Every spec, plan, and tool in this repo respects them:

1. **No secrets in git** — repos carry identity aliases; key material lives in the OS keychain.
2. **No local absolute paths in versioned config** — output must resolve identically on Linux, macOS, WSL2.
3. **Project identity is device-independent** — a project is its git remote (or `.harness-id`), never a path.
4. **Cross-repo references pin immutable revisions** — consumed spec, plan, and task content requires a full commit SHA; branch or `HEAD` refs are permitted only for explicit living-document cases.
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
