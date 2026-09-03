# ADR 0010: Drop the Multi-Source LLM Constitution Merge

**Status**: Proposed
**Date**: 2026-09-03
**Related**: [Scope Realignment design](../plans/2026-09-03-scope-realignment-design.md) §Decision 9;
[Spec 007 Unified Manifest](../../specs/007-unified-manifest-v2/spec.md),
[Spec 008 install CLI contract](../../specs/008-install-transaction/contracts/haex-install.cli.md);
`.specify/memory/constitution.md` §Principle VI

## Context

The landed assembly implementation supports two modes. Single-source
assembly is a deterministic byte-for-byte copy. Multi-source assembly loads
every contributing constitution, asks a model to reconcile them, and requires
an operator to review and accept the result interactively. The surface being
retired is:

- `haex install --llm {stdio,file,none}` and `--accept-merged <path>`
- `src/haex_hive/constitution/llm.py` (186 lines) and
  `src/haex_hive/constitution/pending.py` (164 lines), plus the multi-source
  branches of `assemble.py`
- error keys `llm-required-for-multi-source`, `merge-not-confirmed`,
  `pending-merge-inputs-mismatch`
- exit code 4 partly meaning "multi-source with `--llm=none`" and exit code 5
  partly meaning "assemble wrote a pending merge and exited"
- `tests/install/integration/test_install_multi_source.py`,
  `tests/unit/test_stdio_protocol.py`, and multi-source cases in
  `tests/unit/test_assemble.py`

Two developments make this mechanism a liability rather than a feature.

**It makes `haex install` non-automatable.** A command that can prompt cannot be
called by CI, by a Buzz workflow trigger, or by a delegating device that wants
to publish the harness before starting an agent. The
[scope realignment](../plans/2026-09-03-scope-realignment-design.md) makes
exactly that call the integration point with every execution plane, in both
directions. As long as assembly can block on an operator, haex-hive cannot be
integrated by the ecosystem it wants to join.

**It makes `haex install` require model access and therefore network access.**
The project's remaining differentiator against Claude Code Remote Control is
that it works without a vendor cloud. Multi-source assembly contradicts that on
the config plane: a satellite without model access cannot assemble, and one
with model access needs the network. Single-source assembly and lockfile
verification are already fully offline; multi-source is the only part that is
not.

A third, smaller point: the operator can obtain the same outcome without any
tooling. Handing several constitutions to a model and asking for a reconciled
document is a thing any operator can do in a chat window, and the result is
then adoptable as an ordinary single-source molecule at a pinned SHA.

## Decision

Remove the multi-source LLM merge, and align with the operator's one-workflow /
one-constitution rule that this document was written under.

**A repository adopts exactly one prose atom with `binding: non-negotiable`.**
That atom is the constitution. `.haex-hive/constitution.md` is a byte-for-byte
copy of its source file, byte-identical on every satellite that resolves the
same pinned SHA. No merge, no concatenation, no reconciliation.

`haex install` refuses when the resolved atom graph carries two or more prose
atoms with `binding: non-negotiable`. The refusal is
`key=multiple-non-negotiable-prose-refused`, analogous to Spec 011's
`multiple-workflow-molecules-refused`, and names the conflicting atoms and
their sources. The exit code is the existing `INPUT_REFUSE` (2). An operator
who wants a reconciled document produces it themselves and adopts the result
as a single-source molecule.

Any number of prose atoms with `binding: recommended` remain permitted; they
compile into per-tool prose files (`CLAUDE.md` / `AGENTS.md` / ...), not into
the constitution. Spec 011's `## Workflow-Contributed Rules` fragment becomes
recommended prose under Decision 6 and stops touching the constitution.

Concretely:

- Remove `--llm` and `--accept-merged` from `haex install`.
- Remove `constitution/llm.py` and `constitution/pending.py`; remove the
  multi-source merge branches from `constitution/assemble.py`.
- Remove the error keys `llm-required-for-multi-source`, `merge-not-confirmed`
  and `pending-merge-inputs-mismatch`.
- Add the refusal key `multiple-non-negotiable-prose-refused` alongside
  Spec 011's `multiple-workflow-molecules-refused`.
- Narrow exit code 4 to validation refusals and exit code 5 to system refusals;
  both keep their other meanings and neither is renumbered. Code 7 remains
  exclusively the incomplete-transaction result; it is not a second system
  refusal. The complete retained mapping and precedence are defined in the
  [Spec 008 install CLI contract](../../specs/008-install-transaction/contracts/haex-install.cli.md).
- Remove the pending-merge sidecar state and its recovery path.

### Byte identity: git, not a separate hash

Earlier drafts of this ADR specified a byte-level serialization format for the
concatenated constitution and stated the resulting `install.lock.constitution.content_integrity`
digest for a golden acceptance vector. Both are obsolete under the current
model:

- With one non-negotiable prose atom per repository the constitution is a copy,
  not an assembly. There is no serialization to specify and no golden vector
  to hash.
- The [2026-09-01 trust-git amendment](../../specs/008-install-transaction/research.md)
  retired `content_integrity` on every participating root, including
  `.haex-hive/constitution.md`. Git's own tree object already covers byte
  identity for committed content; a separate SHA-256 field would be strictly
  weaker and duplicates work git already does. The
  [install-lock schema](../../src/haex_hive/schema/data/install-lock.v2.schema.json)
  and [visibility-marker schema](../../src/haex_hive/schema/data/visibility-marker.v1.schema.json)
  already reflect that removal.

The remaining `d15_one_file_tree_digest` implementation in
[src/haex_hive/io/file_hash.py](../../src/haex_hive/io/file_hash.py) is dead
code under the current schema and should be removed as part of the code work
implementing Decision 9.


Principle VI stays intact: `.haex-hive/constitution.md` is written from a
single pinned source, its byte identity is provided by git per the trust-git
amendment, and the operator reviews it as a normal diff. There is no in-place
rewrite of versioned config.

The single-source publication path MUST retain the FR-038 safety boundary:
validate the resolved source for plaintext secrets before copying, validate the
complete generated lock payload before staging, and validate the publication
body for Principle-VIII concealment instructions before staging. These checks
happen before `_publish_constitution` starts its journal or replaces a target.
A refusal uses exit 10 for plaintext secrets or exit 8 for concealment
instructions, leaves the journal and output files unchanged, and never echoes
the matched value. The code removal and implementation of this path are
follow-up work; this ADR changes no executable behaviour by itself.

## Consequences

- **Positive**: `haex install` becomes fully deterministic and requires no model
  access. Two satellites resolving the same pins produce byte-identical output
  in every case, not only the single-source case.
- **Positive**: `haex install` becomes non-interactive, which is the
  precondition for CI use, for Buzz workflow triggers, and for the harness
  handoff contract.
- **Positive**: roughly 350 lines of implementation plus an interactive stdio
  protocol and its tests leave the codebase, including the only component that
  depends on an external model.
- **Negative**: an operator wanting a reconciled document from two publishers
  produces it themselves and adopts the result as a single non-negotiable prose
  atom. `haex install` no longer performs that reconciliation, and refuses when
  the resolved atom graph carries two or more non-negotiable prose atoms.
- **Neutral**: this changes behaviour that has already landed. Per the project's
  pre-adopter status there is no compatibility shim; the removal is a clean
  break, and consumers on an older pin are unaffected until they bump it.

## Alternatives Considered

- **Keep the merge but make it optional and non-blocking**: rejected. An
  optional interactive path is still an interactive path; a caller cannot know
  in advance whether a given manifest will trigger it, so every automated caller
  must treat `haex install` as possibly-blocking anyway.
- **Keep the merge but run it only in `haex constitution assemble`, never in
  `haex install`**: rejected. It splits the assembly contract in two and leaves
  the model dependency in the tree for a command that would then be optional.
- **Deterministic merge without a model** (structural section merge, conflict
  markers): rejected as complexity for a case the operator can resolve better
  by hand. Concatenation with provenance headers conveys the same information
  and cannot produce a wrong reconciliation.
- **Defer the removal until Spec 010**: rejected. The compiler work in Spec 010
  is the first consumer of a non-interactive install; removing the blocker
  afterwards would mean building against a surface that is about to change.

## Follow-up

- Revise [Spec 007's feature requirements and acceptance scenarios](../../specs/007-unified-manifest-v2/spec.md)
  and the authoritative [Spec 008 install CLI contract](../../specs/008-install-transaction/contracts/haex-install.cli.md)
  to state the one-non-negotiable-prose rule, add the
  `multiple-non-negotiable-prose-refused` diagnostic key, drop the merge
  requirements, and preserve the FR-038 checks and exit-code precedence.
- The README and [Spec 008 quickstart](../../specs/008-install-transaction/quickstart.md)
  are aligned with the deterministic install path in this change.
- [Spec 011](../../specs/011-speckit-workflow-atom/spec.md) still mandates the
  retired flags: FR-004 requires the review-gated `haex install --llm=file` /
  `--accept-merged` flow, and its User Story 1 independent test invokes them.
  Both need rewriting. Under this decision Spec 011's constitution fragment
  becomes recommended prose that lands in `CLAUDE.md` / `AGENTS.md`, not in
  the constitution; the `## Workflow-Contributed Rules` section moves with it.
- [Spec 012's adoption flow](../plans/2026-09-02-spec-012-speckit-session-hopper-atom-design.md)
  is aligned with the deterministic install path in this change; any remaining
  consumer instructions must not use the retired `--llm` or `--accept-merged`
  flags.
- Remove the dead `d15_one_file_tree_digest` implementation and its tests as
  part of implementing this decision.
