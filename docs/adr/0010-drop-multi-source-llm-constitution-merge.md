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

Remove the multi-source LLM merge. Multi-source constitution assembly becomes
deterministic concatenation of the contributing sources in canonical order:
ascending bytewise UTF-8 order of the resolved atom ID, which is also the
required order of `install.lock.constitution.sources[]`. Each section is
preceded by a provenance header naming the contributing atom (molecule) ID,
its canonical source URL and its pinned revision.

### Normative multi-source serialization

The assembled body is a UTF-8 byte sequence. Contributions that are not valid
UTF-8 are validation refusals; otherwise their raw bytes are not normalized.
Sort contributions by `source.id.encode("utf-8")`, then serialize each one in
that order using this exact grammar (all line endings are LF, and the header is
ASCII):

```text
<!-- haex-hive:constitution-source:v1
id=<percent-encoded UTF-8 value>
source=<percent-encoded UTF-8 value>
revision=<percent-encoded UTF-8 value>
length=<ASCII decimal body-byte length>
-->
<exactly length body bytes>
\n<!-- haex-hive:constitution-source-end:v1 -->\n
```

In this grammar, each displayed `\n` denotes one LF byte; it is not the two
literal characters backslash and `n`.

Percent encoding operates on UTF-8 bytes; unreserved RFC 3986 bytes
(`A-Z`, `a-z`, `0-9`, `-`, `.`, `_`, `~`) remain literal and every other
byte is encoded as uppercase `%HH`. The fields are always emitted in the
order `id`, `source`, `revision`, `length`; the length counts only the raw
body bytes. After the body, emit one LF, the end marker, and one final LF.
Thus a body-ending LF is retained and the framing LF is additional. The
resulting complete body, including all framing, is the value hashed by the
existing D15 `haex-hive-tree-v1` `content_integrity` rule.

Golden-byte acceptance case: for the sorted inputs
`com.example.base` / `https://example.com/harness` / 40 `1` digits / `# Base\n`
and `com.example.overlay` / `https://example.com/team` / 40 `2` digits /
`# Overlay`, the exact output is:

```text
<!-- haex-hive:constitution-source:v1
id=com.example.base
source=https%3A%2F%2Fexample.com%2Fharness
revision=1111111111111111111111111111111111111111
length=7
-->
# Base

<!-- haex-hive:constitution-source-end:v1 -->
<!-- haex-hive:constitution-source:v1
id=com.example.overlay
source=https%3A%2F%2Fexample.com%2Fteam
revision=2222222222222222222222222222222222222222
length=9
-->
# Overlay
<!-- haex-hive:constitution-source-end:v1 -->
```

It is 438 bytes and its D15 content hash is
`sha256-yqVNMTQov4yIGtDcWPo/IOxiFSiecbVnv7ZxT0Wf6Hg=`. The acceptance test
MUST compare exact bytes and this hash, not just rendered text.

Specifically:

- Remove `--llm` and `--accept-merged` from `haex install`.
- Remove `constitution/llm.py` and `constitution/pending.py`; remove the
  multi-source merge branches from `constitution/assemble.py`.
- Remove the error keys `llm-required-for-multi-source`, `merge-not-confirmed`
  and `pending-merge-inputs-mismatch`.
- Narrow exit code 4 to validation refusals and exit code 5 to system refusals;
  both keep their other meanings and neither is renumbered. Code 7 remains
  exclusively the incomplete-transaction result; it is not a second system
  refusal. The complete retained mapping and precedence are defined in the
  [Spec 008 install CLI contract](../../specs/008-install-transaction/contracts/haex-install.cli.md).
- Remove the pending-merge sidecar state and its recovery path.
- Operators wanting a reconciled rather than concatenated document produce it
  out of band and adopt the result as a single-source molecule.

Concatenation keeps Principle VI intact: nothing is rewritten in place, the
output is a generated artifact recorded in `install.lock` with its content
hash, and the operator reviews it as a normal diff.

The direct-concatenation implementation MUST retain the FR-038 safety
boundary: validate every source for plaintext secrets before concatenation,
validate the complete generated lock payload before staging, and validate the
final publication body for Principle-VIII concealment instructions before
staging. These checks happen before `_publish_constitution` starts its journal
or replaces a target. A refusal uses exit 10 for plaintext secrets or exit 8
for concealment instructions, leaves the journal and output files unchanged,
and never echoes the matched value. The code removal and implementation of
this path are follow-up work; this ADR changes no executable behaviour by
itself.

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
- **Negative**: genuinely conflicting constitutions are no longer reconciled by
  the tool. Two molecules that both forbid and permit the same practice produce
  a concatenated document containing both statements. The operator must notice
  and resolve this. Mitigation is a lint that flags duplicate section headings
  across sources; whether that lands is left to the Spec 007 revision.
- **Negative**: the assembled document is longer and more repetitive than a
  merged one, because shared boilerplate is repeated per source.
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
  to state concatenation-with-provenance, drop the merge requirements, and
  preserve the FR-038 checks and exit-code precedence.
- The README and [Spec 008 quickstart](../../specs/008-install-transaction/quickstart.md)
  are aligned with the deterministic install path in this change.
- [Spec 012's adoption flow](../plans/2026-09-02-spec-012-speckit-session-hopper-atom-design.md)
  is aligned with the deterministic install path in this change; any remaining
  consumer instructions must not use the retired `--llm` or `--accept-merged`
  flags.
