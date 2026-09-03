# haex-hive Scope Realignment (Design)

**Status**: Design. Captured 2026-09-03 from a brainstorming session that re-examined the project's premise rather than a single feature. Supersedes the scope framing of the main design doc; does not yet supersede any landed spec.

**Purpose**: The operator asked two questions in sequence. First, whether "model everything as a skill" would simplify the harness model. Second, and more fundamentally, whether haex-hive still solves a problem that is not already solved elsewhere. This document records the ecosystem findings, the resulting scope decisions, and what they mean for the specs in flight.

**Related**:
- [Main haex-hive design](2026-08-26-haex-hive-design.md): its Phase 3/4 vision is retired by Decision 1.
- [Spec 007: Unified Manifest v2/v3](../../specs/007-unified-manifest-v2/spec.md): the `contributes`/`atoms` category map is restructured by Decision 6; multi-source assembly changes under Decision 9.
- [Spec 008: Install Transaction](2026-08-29-spec-008-install-transaction-requirements.md): landed, unaffected.
- [Spec 009: Hook Boundary](2026-08-29-spec-009-hook-boundary-requirements.md): recalibrated by Decision 11.
- [Spec 010: Compiler & Agent Adapters](2026-08-31-spec-010-compiler-preview.md): adapter surface shrinks under Decision 3; `contributes.*` extension list replaced by Decision 6; degradation reporting added by Decision 7.
- [Spec 013: `haex add` and molecule rename](2026-09-02-spec-013-add-cli-and-molecule-rename-design.md): gains the manifest-optional adoption path from Decision 4.
- [ADR 0010](../adr/0010-drop-multi-source-llm-constitution-merge.md): records Decision 9 against landed behaviour.

---

## 1. Findings

All findings verified 2026-09-03 against primary sources.

### Agent Skills is a format standard, not a package manager

The Agent Skills format (originally Anthropic, released as an open standard, now at `agentskills.io` and `github.com/agentskills/agentskills`) defines a directory containing `SKILL.md` with YAML frontmatter. Required: `name`, `description`. Optional: `license`, `compatibility`, `metadata`, `allowed-tools` (experimental). `metadata` is an explicit third-party extension namespace, constrained to a flat string-to-string map. A reference validator exists (`skills-ref validate`).

Adoption covers effectively the whole "perspective set" Spec 010 targeted: Claude Code, Codex, Gemini CLI, Cursor, GitHub Copilot, VS Code, opencode, Amp, Goose, Kiro, Factory, pi, Trae, Roo Code, Junie, Tabnine, OpenHands, Letta, Hermes and others.

The specification has no page on, and no mechanism for: registries, distribution, packaging, versioning, dependencies between skills, or hooks.

### Neighbouring distribution mechanisms lack immutable pinning

- `skills.sh` installs via `npx skills add <owner/repo>`. No manifest, no version pinning, no lockfile.
- Spec Kit community extensions use `extension.yml` with semver via GitHub releases, installed by `specify extension add`, discovered through `catalog.json` plus `catalog.community.json` with `SPECKIT_CATALOG_URL` for org catalogs. Versioning is release-tag based; there is no commit-SHA pinning, which is what Principle IV requires.

### The delegation problem has been solved by others

- **Claude Code Remote Control** (research preview, early 2026) makes a browser or the Claude mobile app a viewport into a local session. A machine running `claude remote-control` appears as a device card; selecting it starts a session on that machine. Code, filesystem, MCP config and settings stay local; only message routing is cloud-side, which is also why it cannot work without internet.
- **OpenHands** provides the cloud-hosted variant, model-agnostic and open source.
- **Buzz** (block/buzz) provides the self-hosted variant: a Nostr relay in Rust, desktop/mobile/CLI/web clients, an ACP harness (`buzz-acp`) for Goose, Codex and Claude Code, MCP integration, and YAML workflow triggers.
- **ACP (Agent Client Protocol)**, created by Zed in August 2025, standardises editor-to-agent communication over JSON-RPC (stdio locally, HTTP/WebSocket remotely, remote support explicitly still in progress). Adopted by JetBrains, Google and GitHub, with 25+ agents.

### The consistency problem has been solved by nobody

None of the above addresses whether an agent reached on a second device *behaves* the same as on the first. Remote Control is explicitly a viewport into that machine's own configuration. Buzz and OpenHands transport sessions; they do not reconcile harness configuration across devices or across agent CLIs. No tool composes an agent harness from multiple independent publishers with immutable pinning and a reproducible install.

## 2. The three planes

The project has been conflating three separable concerns.

| Plane | Question it answers | State of the art |
|---|---|---|
| **Harness** | Does the agent behave the same everywhere? | Unsolved. This is haex-hive. |
| **Environment** | Does the build work the same everywhere? | Solved by Nix, devcontainers, mise, devbox, podman. |
| **Execution** | Can I reach the device? | Solved by ACP, Buzz, OpenHands, Remote Control. |

## 3. Decisions

### Decision 1: haex-hive builds no execution plane; it defines a handoff contract instead

Phase 3 and Phase 4 of the main design doc (the Nostr liveness plane, cross-device delegation, mobile control) are retired as haex-hive deliverables. haex-hive ships no daemon, no transport, no device identity plane, no session protocol and no mobile client.

**On the ACP-over-Nostr architecture specifically.** The operator's original plan was Nostr-based, and it is sound on its merits: Nostr supplies device identity through keypairs without a central auth service, gives NAT traversal for free because both ends dial out to a relay, and is self-hostable down to a LAN-local relay, which satisfies the offline requirement that Remote Control structurally cannot. ACP supplies session semantics that would otherwise have to be invented, across 25+ agents. The combination is a real architecture and much smaller than building from scratch.

It is nonetheless rejected as a haex-hive deliverable for two reasons that are about timing and duplication, not merit:

1. ACP's remote transport is explicitly work in progress. Bridging against it now is bridging a moving target at its most expensive moment.
2. Buzz already is ACP over Nostr, self-hosted, with clients. Building a second one requires an explicit answer to "why not Buzz", and that answer must be stated rather than assumed.

**What haex-hive does own is the handoff.** When a task is delegated to another device, the harness pin travels with it, and the receiving side runs `haex install` at that pin before starting the agent. That is the actual guarantee behind "the same thing runs everywhere", it is small, and it is implementable against any execution plane: against Buzz, against Remote Control via a session hook, against a future bridge.

If a minimal ACP-over-Nostr bridge is built later, it belongs in a separate repository with a separate release cycle (working name `haex-relay`) and consumes this contract. It is not a precondition for anything here. Revisit no earlier than: the harness plane is complete, and ACP remote transport is no longer marked work in progress.

### Decision 2: the environment plane is declared, never installed

A project's toolchain (Rust, Tauri, Android SDK, Node) is not haex-hive's to resolve. `flake.lock` is already a content-hashed lockfile of the same shape as `install.lock`, backed by a package set haex-hive cannot compete with. Docker, podman, devcontainers, mise and devbox likewise.

There is nonetheless a real gap on the harness plane: **Nix tells the machine which toolchain applies; it tells the agent nothing.** An agent cloning a project onto a fresh server does not know it must run `nix develop` first, calls `cargo`, gets "command not found", and improvises with a system package manager. That is precisely the class of damage the harness exists to prevent.

The manifest therefore gains a small declarative `environment` block:

```json
{
  "environment": {
    "provider": "docker-compose",
    "requires": [
      { "check": "docker compose version",
        "hint": "Docker Engine + Compose plugin: https://docs.docker.com/engine/install/" }
    ],
    "exec_prefix": ["docker", "compose", "exec", "-T", "dev"],
    "verify": "cargo tauri --version"
  }
}
```

Field semantics:

- **`requires`** checks that the provider itself is present, from outside. Each entry is a command plus an operator-facing hint. Failure means "the provider is missing, install it yourself".
- **`exec_prefix`** is the command prefix every build command must carry. Its presence *is* the mode: present means the agent runs outside the environment and must wrap; absent means commands run directly, which covers both a correct host toolchain and an agent already running inside a container. No mode enum is needed, and none is introduced.
- **`verify`** checks the toolchain from inside, after wrapping. Failure means "you are not in the dev environment".

The prefix form covers every mainstream provider: `["nix","develop","-c"]`, `["mise","exec","--"]`, `["devbox","run","--"]`, `["docker","compose","exec","-T","dev"]`. Environments that cannot be expressed as a command prefix are out of scope; in practice a prefix equivalent always exists.

haex-hive compiles this into exactly two artifacts, both with existing machinery: a prose instruction in the per-tool prose file stating how to run build commands and that system-level package installation is forbidden, and a `SessionStart` hook running `requires` then `verify` and warning or refusing.

**haex-hive never installs a provider.** Installing Docker or podman means root, a daemon, groups and kernel modules. That is categorically different from writing files into a repository and would break the project's own model (Principle II, and the sidecar/review-gate philosophy). Every package manager has this boundary: npm needs node, cargo needs rustup, nix needs the Nix installer. haex-hive's boundary is `requires`.

The recommended layering resolves the bootstrap regress with one global prerequisite:

```
nix (the only global prerequisite)
  └─ nix develop      → provides the docker/podman CLI, mise, just
       └─ <container> → provides Android SDK, NDK, Rust, Tauri
```

Exactly one environment per project. Multiple named environments are not built on suspicion; a project that genuinely needs two is the occasion to extend the schema.

### Decision 3: consume foreign formats natively

Three formats have won their categories: the Agent Skills directory, Spec Kit's `extension.yml`, and MCP server declarations. haex-hive invents no competing format for any of them.

What haex-hive owns is what none of them provide: composition across publishers, SHA pinning, transactional install with a lockfile and orphan deletion, cross-tool compilation, and deterministic activation.

A direct consequence for Spec 010: the adapter problem shrinks substantially. For the skill category, 45 tools already read the same directory format, so an adapter needs to know the destination path, not a translation. Hooks and structured config remain genuinely per-tool.

### Decision 4: the molecule manifest becomes optional

Requiring a publisher-authored `manifest.json` is the decisive adoption barrier for an open-source project: an arbitrary skills repository cannot be adopted even though its content is exactly right.

Adoption therefore detects by shape. A directory containing `SKILL.md` is a prose contribution with `activation: on-demand`, with no manifest. A directory containing `extension.yml` is a Spec Kit extension. `haex add <url>` works against any such repository, at a resolved full SHA, with a lockfile.

A manifest is required only for what the foreign formats cannot express: composition, hooks, activation policy other than the format's default, and binding strength.

This inverts the value proposition. Instead of "write a haex-hive manifest to participate", it becomes "everything that already exists is adoptable, pinned and reproducible, which `npx skills add` cannot do".

### Decision 5: haex-hive's own molecules are valid Agent Skills directories

Because the Agent Skills spec reserves `metadata` for third-party keys, a haex-hive molecule can be a valid `SKILL.md` directory carrying a sibling `haex.json` for the structured parts a flat string map cannot hold.

Consequence: haex-hive molecules function in all skills-compatible tools without haex-hive installed. Operators who have haex-hive additionally get pinning, composition and deterministic activation. There is no lock-in, which for an open-source project is the strongest available adoption argument.

### Decision 6: collapse the category map to four payload kinds plus an activation policy

The current categories (`constitution`, `spec`, `rules`, `hooks`, `skills`, `workflow`, and the planned `instructions`) differ along only two axes: what the payload is, and when it activates. Five of the seven are prose.

```json
{
  "atoms": {
    "prose": [
      { "path": "constitution.md", "activation": "always",     "binding": "non-negotiable" },
      { "path": "style.md",        "activation": "glob",       "globs": ["**/*.rs"] },
      { "path": "skills/tdd/",     "activation": "on-demand" }
    ],
    "agent": [ { "path": "agents/implementer.md" } ],
    "hooks": [ { "path": "hooks/verify_env.py", "event": "SessionStart", "timeout": 5 } ],
    "mcp":   [ { "name": "playwright", "command": "npx", "args": ["..."] } ]
  }
}
```

The constitution stops being a magic category name and becomes what it actually is: prose that always applies with non-negotiable binding. The review gate attaches to `binding: non-negotiable`, which states the reason it exists.

`agent` is a subagent definition and is structurally close to a skill: frontmatter carrying name, description, tools and model, with the body as system prompt. Claude Code materialises these at `.claude/agents/*.md`.

Whether "workflow" survives as a payload kind or becomes an attribute on a prose contribution is left to the spec phase; Spec 011's one-per-repository rule needs some marker either way.

### Decision 7: activation is declared intent; the compiler picks the strongest available mechanism and reports degradation

This answers the question the session opened with. Skills and hooks are not alternatives. **Hooks are what make skills deterministic, and that is exactly the gap the Agent Skills standard leaves open.** The standard has no way to express "this always applies"; activation there is implicitly and always model-discretionary. haex-hive can supply it, because it compiles per tool.

| Declared activation | Claude Code | Cursor | Tool without hooks | Tool without skills |
|---|---|---|---|---|
| `always` | `CLAUDE.md` | `alwaysApply` rule | `AGENTS.md` | `AGENTS.md` |
| `glob` | PreToolUse hook | native glob rule | prose (degraded) | prose |
| `on-demand` | `.claude/skills/` | Cursor skills | skill directory | prose section |
| `on-event` | `settings.json` hooks | degraded | degraded | degraded |
| `agent` payload | `.claude/agents/` | native equivalent | prose, sequential (degraded) | prose |

Two rules keep this honest rather than overstated:

1. **Degradation must be reported.** `haex install` emits, for example, `hook verify_env (SessionStart): unsupported by codex, degraded to prose note in AGENTS.md`. Agent-agnostic does not mean equally strong everywhere; it means the strongest available mechanism, with the operator told where the guarantee weakens. Silent degradation would also conflict with Principle VIII.
2. **`activation: always` on a skill-format payload compiles to a skill directory plus a `SessionStart` hook that injects a reference to it.** This yields portability and determinism at once without leaving the skill format.

### Decision 8: subagent delegation is opt-in per workflow step, never automatic

The `agent` payload kind declares *availability*. Whether a given workflow step delegates to a subagent is declared by that step, and the default is sequential execution in the running session.

Rationale: delegation is not uniformly beneficial. It pays when the task is independent, the result is small relative to the work performed, and the exploration would otherwise pollute the orchestrator's context: search, research, independent implementation tasks, reviews. It costs when a step builds directly on the previous step's reasoning, because a fresh subagent re-reads the artifacts but not the deliberation that produced them. In a Spec Kit loop that makes `implement` the strong case and `specify → plan → tasks` the weak one.

A separate, more ambitious option is recorded but not adopted: an MCP server that spawns and drives ACP agents would give any MCP-capable orchestrator agent-agnostic subagents, so that a Claude Code orchestrator could delegate to Gemini CLI or Codex. It is local-only, needs no transport or identity plane, and would ship as an `mcp` payload in a molecule. If built, it belongs in a separate repository (working name `haex-acp-bridge`), not in the haex-hive core, and the token-cost caveat above applies more strongly, not less.

### Decision 9: drop the multi-source LLM constitution merge

Multi-source constitution assembly becomes deterministic concatenation in canonical order with provenance headers. An operator who wants a reconciled single document produces it themselves with a model of their choosing and adopts the result as a single-source molecule.

The decisive argument is not code volume but reachability: **an install that can prompt is not automatable.** Interactive assembly requires a device with model access and an operator at a terminal, which contradicts both the offline goal (Decision 2's motivation) and ecosystem integration (Decision 10). See [ADR 0010](../adr/0010-drop-multi-source-llm-constitution-merge.md).

### Decision 10: integration readiness is a deliverable, in both directions

The operator's goal is that haex-hive both integrates the existing ecosystem and can be integrated by it. Decisions 3, 4 and 5 cover the inbound direction. The outbound direction needs four things, three of them small:

| Item | Why |
|---|---|
| `haex install --json` | machine-readable result including the Decision 7 degradation report, so an orchestrator knows what it actually got |
| exit codes as contract | `util/exit_codes.py` exists; it needs to become a documented, stable surface |
| non-interactive install | delivered by Decision 9 |
| handoff manifest | delivered by Decision 1, so a delegating side can send the pin |

Concretely, integration with Buzz then reduces to: a Buzz workflow trigger runs `haex install` at the handed-off pin on the target device before `buzz-acp` starts the agent. No haex-hive-side transport code.

Publication follows from Decision 5: haex-hive's own molecules are valid Agent Skills directories and can be listed on `agentskills.io`; workflow molecules can be submitted to the Spec Kit community catalog.

### Decision 11: recalibrate Spec 009 to the actual trust model

Spec 009's current requirements (cgroup v2 subtrees, Windows Job Objects, `openat2`-based TOCTOU closure, descendant reaping with session-leader tests) are multi-tenant hardening against hostile publishers. The document already concedes that containment is advisory, because hooks run under the operator's own account with no OS-level sandbox.

The actual trust model is the one npm, pip and GitHub Actions operate under, and which the ecosystem has accepted: the operator deliberately adopted this publisher at this SHA. The pinning is the security control; the sandbox is not.

Recommendation: retain subprocess isolation, the timeout contract and the environment allow-list. Defer platform-specific containment and no-follow TOCTOU machinery until a concrete hostile-publisher scenario exists, and state the trust model plainly in the README instead.

## 4. Consequences for specs in flight

| Spec | Effect |
|---|---|
| 007 | The `contributes`/`atoms` category map is restructured per Decision 6. Multi-source assembly changes per Decision 9. The v3 rename in Spec 013 should carry the new shape rather than the seven-category one. |
| 008 | Landed. Unaffected: the transaction, lockfile, journal and orphan deletion are exactly the primitives Decisions 3, 4 and 10 rely on. |
| 009 | Recalibrate per Decision 11 before drafting. |
| 010 | Adapter surface shrinks for skills, stays per-tool for hooks and structured config. Add degradation reporting (Decision 7), the `agent` payload kind (Decision 6) and `--json` output (Decision 10). Replace the proposed `contributes.*` extension list with the collapsed model. |
| 011 | Unaffected in substance. Gains per-step delegation declaration (Decision 8). Whether "workflow" survives as a payload kind is a Decision 6 follow-up. |
| 013 | Gains the manifest-optional adoption path from Decision 4: `haex add` must accept a plain skills repository and a Spec Kit extension repository, not only a haex-hive publisher. |

## 5. Explicitly rejected alternatives

- **Model everything as a skill, including hooks.** Rejected. It conflates packaging with activation. The skill directory is a good container; skill *loading* is model-discretionary and cannot express deterministic activation, which is the thing haex-hive uniquely provides.
- **Build an agent-agnostic Remote Control inside haex-hive.** Rejected per Decision 1. The ACP-over-Nostr architecture is sound but is a second product, is duplicated by Buzz, and would bridge an unfinished remote transport.
- **Fork Buzz.** Not rejected on merit, but out of scope: Buzz is an execution plane, and haex-hive composes with it rather than becoming it.
- **Resolve or install toolchains inside haex-hive.** Rejected per Decision 2. Duplicating `flake.lock` is strictly worse than delegating to it, and installing providers requires privileges that contradict the project's own write model.
- **A `mode` enum on the `environment` block.** Rejected as vocabulary that must be learned without explaining anything. The presence of `exec_prefix` carries the same information.
- **Adopt `npx skills add` semantics.** Rejected: no pinning, violating Principle IV. haex-hive consumes the same repositories at a full SHA instead.
- **Automatic subagent delegation for every workflow step.** Rejected per Decision 8.
- **Multiple named environments per project.** Deferred until a real case demands it.

## 6. Open questions

1. Does "workflow" remain a payload kind after Decision 6, or become an attribute on a prose contribution?
2. Where does the Spec Kit extension format sit: a fifth payload kind, or a foreign format the installer translates into the four existing ones?
3. What is the minimum viable adapter set, given that skills are portable by format and only hooks, structured config and `agent` payloads remain per-tool?
4. Should `requires` failures refuse the install outright, or warn and let the compiled prose carry the instruction? Refusal is safer; warning keeps `haex install` usable on a machine that only edits configuration.
5. Does the handoff manifest (Decision 1) warrant its own spec slot, or does it belong inside Spec 010's compiler output?
