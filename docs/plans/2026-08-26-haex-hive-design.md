# haex-hive — Design

Date: 2026-08-26
Status: Brainstormed, not yet implemented

## Problem

A personal, cross-device AI-assisted development setup:

- Work on multiple satellite machines (laptop, PC, different OSes) with familiar tools
  (VSCode, GitHub/GitLab CLI, terminal, Claude Code / Codex / Gemini CLI).
- From mobile: see the current status of projects/agent sessions, and give a running or
  new agent session instructions ("fix the pipeline", "build feature X").
- Work spans multiple git accounts/orgs simultaneously (private + professional,
  multiple GitHub/GitLab identities) — existing tools (OpenHands) force a single
  account/repo, which doesn't fit.
- Need layered, reusable behavioral/permission configs ("harnesses") — a thin global
  layer that always applies, plus flexible groupings (not necessarily git- or
  account-bound), plus per-project overrides.
- Harnesses must be usable across multiple agent CLIs (Claude Code, Codex, Gemini,
  Qwen, ...), not locked to one tool.
- Each satellite must be able to work fully autonomously (including with local AI
  models) — no hard dependency on any central server for actual work.
- Want a "hive mind": session continuity and recall across devices, not limited to
  code/git projects (e.g. resuming a pure research/brainstorm session on another
  device).

## Prior art considered

- **OpenHands** — closest existing fit, but single git account/repo only. Doesn't
  support the multi-account, multi-repo workflow this needs.
- **Buzz** (block/buzz) — self-hosted Slack/Discord-like workspace on a Nostr relay,
  humans + agents in shared channels, git-patches-as-events (NIP-34), agent harnesses
  via ACP (Goose/Codex/Claude Code), mobile clients still early. Chat-and-approval
  centric rather than IDE/session centric. **Adopted idea: Nostr as the relay
  protocol** (see below).
- **Hermes Agent** (NousResearch) — single always-on gateway process fronting
  Telegram/Discord/Slack/WhatsApp/Signal/CLI, pluggable execution backends
  (local/Docker/SSH/Modal/Daytona), works with local models, cron scheduler, MCP,
  persistent memory with FTS5 search, autonomous skill creation from experience.
  One central gateway + one memory store — doesn't fit the "autonomous peer
  satellites" requirement. **Adopted idea: post-session reflection that distills
  lessons into reusable skills** (see Self-Learning below).
- **secana-specs** (itemis, internal) — the team's existing dev harness: a git repo
  with a `devenv.sh`/`devenv.ps1` bootstrap that clones an allow-listed set of repos
  into one working directory, `CLAUDE.md` importing `.specify/memory/constitution.md`
  (spec-kit), deny-listed sub-repos requiring a separately-rooted session, and a
  `harness-evaluator`/`evals` setup that tests the harness itself. Confirms the
  registry/manifest approach for group membership. Claude-Code-specific (not
  multi-tool). **Decision: referenced as an external, unmodified harness group — not
  ported or rewritten.**
- **earendil-works/pi** — a replacement agent runtime (own multi-provider LLM API,
  own agent core, own CLI), not a compatibility shim over Claude Code/Codex/Gemini.
  No built-in permission system. Would mean replacing the daily-driver tools rather
  than harnessing them. **Decision: not adopted.**
- **haex-vault / haex-sync-server / haex-ucan / haex-claude-proxy** (own existing
  ecosystem) — local-first, E2E-encrypted, CRDT-synced multi-device platform with
  capability-based auth, already has a Claude-CLI-wrapping proxy. Structurally the
  same problem as the hive-memory sync and secrets-sync pieces here.
  **Decision: haex-hive is built as an independent project, not a Haex Space module.
  Secrets and hive-memory sync are built fresh rather than reusing haex-vault,
  despite the overlap** (explicit trade-off, see Secrets and Hive Memory sections).
- **Claude Code's own Remote Control / cloud sessions / push notifications / cron
  routines** — Anthropic already ships cross-device session control and always-on
  cloud execution, but only for Claude Code. **Decision: mobile control in haex-hive
  must be agent-agnostic (Claude Code, Codex, Gemini, ...), so this is not relied on
  as the control plane, even though it overlaps.**

## Architecture

Two independent planes:

1. **Config plane** (harness definitions, credentials-by-reference, permissions) —
   pure git, pull-based, works fully offline. No relay dependency.
2. **Liveness plane** (status, commands, session continuity) — a self-hosted Nostr
   relay. Requires the relay to be reachable by both ends, but its unavailability
   never blocks local work — only mobile visibility/control pauses.

```
┌─────────────┐   git push/pull    ┌──────────────────────┐
│harness repo │◄──────────────────►│ satellite (laptop A)  │
│(registry,   │                    │  - harness-daemon      │
│ groups,     │                    │  - compiles config →   │
│ global)     │                    │    CLAUDE.md/AGENTS.md/│
└─────────────┘                    │    GEMINI.md/settings  │
      ▲                            │  - runs agent CLIs     │
      │ references (unmodified)    │    locally, autonomous │
┌─────┴──────┐                     └──────────┬─────────────┘
│secana-specs │                               │ nostr events
│(external,   │                               │ (status, session
│ read-only)  │                               │  refs, commands)
└─────────────┘                               ▼
      ┌─────────────┐              ┌──────────────────────┐
      │ satellite B  │◄──nostr─────┤ self-hosted Nostr relay│
      │ (same daemon)│   events    │  (strfry/nostr-rs-relay)│
      └──────────────┘             │  + Blossom blob store  │
                                    └──────────┬─────────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │ mobile app — status,  │
                                    │ instruct, recall hive │
                                    │ memory                │
                                    └──────────────────────┘
```

Commands are not mobile-specific: any authorized identity (mobile, or another
satellite) can address any registered satellite over the relay. This is what lets
device A trigger heavy work on device B's hardware (e.g. GPU) for free, without a
separate mechanism.

## Harness / Config Layer

Repo shape:

```
harness-registry/              (private root git repo)
  registry.yaml                 # project-identity → group(s) mapping
  global/
    instructions.md             # thin, always applies
    permissions.base.yaml
  groups/
    private-oss/
      instructions.md
      permissions.yaml
      mcp-servers.yaml
      identity: personal-github  (alias, not a secret)
    experiments/
      ...
  external-groups.yaml
    - name: itemis-secana
      repo: gitlab.com/itemis/solutions/secana-specs
      identity: work-gitlab
      mode: unmodified            # cloned/updated, never compiled/rewritten
```

**Project identity is device-independent, and never carries a raw filesystem path:**
- Git-backed project → identity = git remote URL. Identical on Windows and Linux
  regardless of local clone path.
- Non-git, folder-only project → a small opaque id (`.harness-id`) dropped in the
  folder once, carried along when copied. Only carries identity, not group
  membership (that stays entirely in `registry.yaml`).

`registry.yaml` maps `project-identity → group(s)` and is identical on every
device. Each satellite daemon keeps its own **local, unsynced** table of
`project-identity → local path on this machine`. Raw paths never cross a device
boundary; where a specific device's copy needs to be addressed (routing, resuming),
the unit is `(device-pubkey, project-identity)`, never a path.

**Compiler**: for own groups, resolves `global + group(s) + project override`
(later layers win, arrays merge) into an effective spec, then produces per-tool
output:
- Pure-instruction files (CLAUDE.md/AGENTS.md/GEMINI.md) are **symlinked** to the
  compiled canonical file — filesystem-level pointer, no per-tool import-syntax
  dependency, zero drift risk. (Needs Developer Mode/admin for symlinks on Windows.)
- Permissions/MCP-server config (`settings.json`, `config.toml`, ...) are
  structurally incompatible formats between tools, so these are genuinely
  **compiled**, not symlinked — but always generated from the one canonical YAML,
  never hand-edited per tool.

External groups (e.g. secana-specs) are cloned and used exactly as their owning
team maintains them; only the *identity* used to clone them comes from this system.

## Execution & Dev Environment

- Every satellite runs the same daemon: watches the harness repo, compiles configs,
  launches/wraps agent CLI processes, publishes/subscribes to the relay.
- **Dev environment provisioning is Nix-first**: each project's harness references a
  Nix flake as the canonical, reproducible environment definition (compilers,
  libraries, package managers). A prebuilt container image is a narrow fallback for
  the rare project where Nix doesn't fit well — not a fully parallel devcontainer
  system.
- **Platform support**: Nix runs natively on Linux and macOS. It has no native
  Windows port — on Windows it requires **WSL2**. This means a Windows satellite's
  daemon runs as a Linux process inside WSL2, not as a native Windows process
  (pairs fine with VSCode's Remote-WSL support, so "familiar tools" still holds).
  Bare-Windows-without-WSL2 is not a supported satellite target for Nix-based
  projects — the container fallback is the only option there.
- **Capability tags**: satellites advertise capabilities (e.g. `gpu`, `android-sdk`)
  in their relay status events. Commands can target a specific satellite explicitly,
  or request "any satellite with capability X" — needed both for hardware routing
  and for picking a satellite actually able to run a given project.

## Secrets

The harness repo (git) only ever contains **references** to identities (e.g.
`identity: work-github`), never secret material.

- **Store**: OS keychain per device, never ambiently synced. Each satellite is
  provisioned once with the credentials it needs; nothing leaves a device by
  default.
- **Provisioning/rotation transport**: the Nostr relay, used narrowly — NIP-44
  (ECDH-derived, pubkey-to-pubkey encryption) to push a new/rotated secret to a
  specific device's pubkey, using ephemeral events or relay-side deletion after
  delivery so it isn't retained. This is a one-shot delivery pipe, not an always-on
  synced store — the relay must not become a place where secrets sit long-term
  (harvest-now-decrypt-later risk), and each device's Nostr identity key is itself a
  secret requiring the same keychain protection.
- Reusing haex-vault for this was considered and explicitly declined, in favor of
  keeping haex-hive fully independent — a deliberate trade-off, not an oversight.

## Relay & Hive Memory

- Self-hosted Nostr relay (strfry/nostr-rs-relay), single-tenant, not the public
  social graph.
- Event kinds: `status` (satellite heartbeat/capabilities/current work), `command`
  (instruction, targeted by device-pubkey or capability), `session-ref` (pointer to
  a transcript), plus the narrow secrets-provisioning events above.
- Bulky content (full session transcripts) goes through **Blossom** blob storage;
  events themselves stay small (references/summaries), matching how Buzz already
  uses this pairing.
- **Hive memory serves two distinct needs**, not one:
  - *Resume exactly where I left off* on another device → needs the **raw
    transcript** (Blossom).
  - *Recall what happened/was decided* across sessions → needs something
    **queryable**, not just replayable. Transcripts are ingested into a
    **graphify** knowledge graph (already used for codebase/doc graphs elsewhere)
    so recall works via `graphify query`/`path`/`explain` rather than re-reading raw
    logs.

## Self-Learning / Reflection

On session end, the daemon triggers a reflection pass over the transcript: extract
"what was the problem, what was the fix, is this reusable." The output is **not**
written into the knowledge graph (that's passive recall) — it's drafted as a diff
to the actual harness (a new/updated skill or instruction snippet), at project level
by default, promotable to group/global if broadly applicable.

The diff is **proposed, not auto-merged** — a real commit/PR against the harness
repo, surfaced for review (naturally via the mobile control channel: not just "give
instructions" but also "approve what the agent just learned"). Auto-merging was
considered and rejected: self-modifying instructions without a review gate will
drift — overfitting to one-off incidents, accumulating contradictions — the review
step is what keeps this signal instead of noise.

## Data Flow (example: mobile instructs a satellite)

1. Mobile publishes a signed `command` event (target = device-pubkey or
   `capability:gpu`, payload = "continue on project-id X: fix pipeline").
2. Relay delivers to matching satellite(s). An offline satellite misses it unless
   the relay retains that event kind long enough to catch up on reconnect (must be
   configured explicitly, not assumed).
3. Target daemon resolves `project-id → local path`, applies the compiled harness
   (Nix env, permissions, credentials from OS keychain), launches/resumes the agent
   CLI.
4. Daemon publishes periodic `status` events and, on completion, a `session-ref`
   pointing at the full transcript.
5. Mobile subscribes to status/session-ref events for that project and updates
   live.

## Error Handling

- Relay unreachable → satellites keep working locally; only mobile
  visibility/control pauses.
- Target satellite offline when commanded → not silently lost nor magically
  executed; on reconnect the daemon checks for missed commands within a bounded
  retention window, older ones are dropped with a notification rather than queued
  indefinitely.
- Two devices editing the harness registry concurrently → plain git merge conflict,
  surfaced normally.
- Agent crashes mid-session → status flips to `error` with last-known state;
  session-ref still points at the partial transcript.

## Testing

Mirror secana-specs' `harness-evaluator`/`evals` pattern:
- Evals asserting the compiler renders correct, valid output per target tool (e.g.
  does the compiled `.claude/settings.json` actually restrict what it should).
- Integration tests for the relay round-trip (publish command → daemon receives →
  status observable).

## Open Questions / Deferred

- Local-model support (via a 4th compiler target, e.g. pi, specifically for
  local/self-hosted models) — explicitly deferred, not designed in now.
- Exact reflection-agent prompt design and skill file format.
- Mobile app UI/UX design.
- Relay event retention/expiry policy specifics (how long to hold `command` and
  `status` events for offline-catch-up).
- Windows symlink permission handling (Developer Mode requirement) — needs
  verification as part of implementation, not just assumed to work.
- Windows satellites require WSL2 for the Nix-first execution path; whether that's
  an acceptable prerequisite to require, or whether Windows-without-WSL2 needs
  first-class container-based support rather than treating it as a narrow fallback,
  depends on how much real Windows-without-WSL2 usage actually happens.
