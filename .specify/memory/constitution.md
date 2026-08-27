# haex-hive Constitution

Hard, non-negotiable invariants of the haex-hive system. Every spec, plan, and
implementation MUST respect them. A change to any of these principles requires
an explicit constitution amendment (see Governance below), not a per-spec
exception.

## Core Principles

### I. No Secrets in Git (NON-NEGOTIABLE)

The harness repo and any repo consuming its harness carry only **references** to
identities — aliases like `identity: work-github`. Key material (SSH private
keys, OAuth tokens, API keys, passwords, encrypted-at-rest secret blobs) MUST
NEVER be committed, in any form. Secrets live in the OS keychain of each device
and are transported between devices only through the NIP-44 one-shot
provisioning path (see Principle VII); the Nostr relay MUST NOT be used as a
long-lived encrypted secret store.

**Rationale**: encrypted secrets in git are permanent — rotation ≠ deletion, and
harvest-now-decrypt-later remains a live threat. The only safe rule is that the
plaintext never enters the repository history in any form.

### II. No Local Absolute Paths in Versioned Config (NON-NEGOTIABLE)

Anything committed to a harness or consuming repo MUST resolve identically on
Linux, macOS, and WSL2. No `/home/haex/...`, no `C:\Users\...`, no
`~/anything`. Cross-repo references use `repository + revision + repo-relative
path` (see Principle IV). Machine-local mappings from `project-identity → local
path` are kept per-device, unsynced, outside version control.

**Rationale**: satellites run on different OSes with different folder layouts.
Any committed path that assumes one layout will silently break on another —
usually mid-session, hard to diagnose.

### III. Project Identity Is Device-Independent (NON-NEGOTIABLE)

A project's identity is its git remote URL, or (for non-git folder projects) an
opaque id file (`.harness-id`) inside the folder — never a filesystem path.
When one satellite addresses another over the relay, the unit is
`(device-pubkey, project-identity)`, never a raw path. Path resolution is
strictly a local, private concern of the device that owns the copy.

**Rationale**: same as II, applied to the runtime addressing scheme rather than
the versioned config. Raw paths that cross a device boundary are always a
mistake.

### IV. Cross-Repo References Pin Immutable Revisions (NON-NEGOTIABLE)

When a project's harness references content in an external harness repo, the
reference format is `repository + full commit SHA + repo-relative path`, and
the SHA MUST be an immutable git object reference. Branch or `HEAD` references
are not the normal case — they are permitted only for explicit "living
document" cases, never for anything a spec, plan, or task consumes.

**Rationale**: satellite A resolving on Monday and satellite B resolving on
Wednesday MUST see byte-identical spec content. Anything else creates silent
cross-device drift that only surfaces as inconsistent agent behavior later.

### V. External Sources Are Opt-in Per Project (NON-NEGOTIABLE)

A project without an explicit `.specify/system.yaml` — or with an empty
`external_sources.allowed` list — MUST inherit no external harness content,
regardless of what the registry, sibling directories, sibling repos, or any
global agent instruction file says. The registry describes what is *available*;
the per-project file grants *use*.

**Rationale**: private/personal repos accidentally picking up work or team
constraints (or vice versa) is a real failure mode, not a theoretical one. The
allowlist is a trust boundary, not a convention. Isolation is the default;
inheritance is explicit.

**Implementation guidance for agents** (added v1.1.0):

**Apply is not authorization.** A user prompt asking an agent to "apply",
"use", "follow", "adopt", or "conform to" constraints, rules, or a harness
from an external source MUST NOT be interpreted as authorization to opt the
project into that source. The opt-in is a separate, review-gated act — never
a side effect of an apply-shaped request.

**Refuse-then-propose is the required shape.** When an agent receives a
request to apply constraints from a source that is not listed in
`.specify/system.yaml`'s `external_sources.allowed`, the agent MUST (a)
refuse the apply in this session, (b) name the mechanical reason (empty or
missing allowlist entry for the source), and (c) offer the two legitimate
paths: either add a pinned entry (`repository + full commit SHA +
repo-relative path(s)`) through a reviewable commit or PR under Principle
VI's amendment procedure, or treat the constraints as the operator's direct
instructions rather than as sourced from the external harness. Silence, or
partial compliance ("I'll apply just some of them"), is not permitted.

**Modifying `.specify/system.yaml` requires an explicit "modify the
allowlist" request.** The word "apply" or its synonyms MUST NEVER trigger a
write to `.specify/system.yaml` or to any other harness configuration file.
Only a request that explicitly asks the agent to edit the file (e.g. "add
X to the allowlist", "update system.yaml to permit Y") may trigger a diff
— and even then, per Principle VI, the diff is presented for review, not
committed unilaterally.

### VI. Self-Modifying Instructions Are Always Review-Gated (NON-NEGOTIABLE)

The reflection pipeline produces proposed diffs against the harness repo — a
commit or PR — never in-place auto-writes. A human reviews and merges. Applies
to skill files, instruction snippets, permissions, constitutions themselves,
and any other artifact the agent consumes on future runs.

**Rationale**: unreviewed self-modification drifts. Instructions overfit to
one-off incidents, accumulate contradictions, and quietly change how agents
behave in ways nobody chose. The review gate is what keeps the signal from
turning into noise.

### VII. Relay Unavailability Never Blocks Local Work (NON-NEGOTIABLE)

The Nostr relay is used only for the **liveness plane**: status, commands,
session refs, one-shot secret provisioning. Its unreachability MUST NOT prevent
an agent CLI on a satellite from doing local work against local disk — only
mobile visibility/control pauses. All spec content, harness content, and
project state resolve from git and local files, not from the relay.

**Rationale**: the whole point of autonomous satellites is that they keep
working when the network doesn't. A design that quietly makes the relay a
critical dependency for anything real defeats that.

## Scope

- Applies to: the haex-hive repository (this repo), any harness registry repo
  built for haex-hive use, and any project repo that declares itself as
  haex-hive-managed via a `.specify/system.yaml`.
- Does NOT apply to: external harness repos referenced in `unmodified` mode
  (e.g. secana-specs). Those follow their own owning team's rules; haex-hive
  only governs how they are *referenced*, not their internal contents.

## Development Workflow

- Every feature/spec created via `/speckit-specify` MUST be checked against
  these principles during `/speckit-plan`. Any conflict is either resolved by
  changing the plan or escalated to a constitution amendment — never silently
  accepted as an exception.
- The phasing discipline from the design doc (`docs/plans/2026-08-26-haex-hive-design.md`)
  is binding: features MUST be sequenced by phase (0 → 7). Features for later
  phases MAY be specified in advance, but MUST NOT be implemented before their
  phase's prerequisites are actually in daily use.
- Design decisions that materially affect any of the 7 principles above MUST be
  captured as ADRs under `docs/adr/`, not left in commit messages or chat
  history.

## Governance

- This constitution supersedes local per-spec preferences. Where a spec, plan,
  or task appears to conflict with a principle, the principle wins by default.
- **Amendments** require: (a) an ADR in `docs/adr/` stating what changes and
  why, (b) an update to this file, and (c) explicit version bump per the rules
  below. All three land in the same commit.
- **Version bump rules** (semantic versioning):
  - MAJOR: a principle removed, a NON-NEGOTIABLE relaxed, or governance model
    materially changed.
  - MINOR: a new principle added, or an existing one materially expanded.
  - PATCH: wording, clarifications, typo fixes, non-semantic refinements.
- **Enforcement**: `/speckit-plan` and `/speckit-analyze` MUST check plans and
  cross-artifact consistency against this document. CI (once introduced under
  Phase 7) validates that no committed file violates Principles I, II, or IV
  mechanically.

**Version**: 1.1.0 | **Ratified**: 2026-08-26 | **Last Amended**: 2026-08-27
