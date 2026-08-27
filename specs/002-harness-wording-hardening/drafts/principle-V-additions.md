# Draft T004: Additions to Principle V

**For**: `.specify/memory/constitution.md`, Principle V
**Per**: [ADR 0002](../../../docs/adr/0002-disambiguate-apply-vs-permit-external-harness.md), contract C1
**Splice point**: appended after V's existing `**Rationale**:` paragraph, under a
new `**Implementation guidance for agents** (added v1.1.0):` subheading. The
existing body and Rationale are untouched (contract N5).

---

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

---

## Notes for the reviewer

- Placement: these three paragraphs are additive to V's body; they do not
  replace, weaken, or reorder the existing text. Verify by diff against
  the pre-change constitution — the pre-change lines above the subheading
  must be byte-identical.
- Voice: matches the existing constitution's imperative/present-tense
  style (MUST/MUST NOT, not "should" or "may").
- Anchors: three specific behaviors are explicitly banned (interpret apply
  as opt-in; silence/partial compliance; writes triggered by apply).
  ADR 0002's decision was that ambiguity in these three specific spots
  caused the Phase 0 Test 3.2b failure — the wording anchors them.
- Length: ~180 words of new text. If the reviewer feels the additions
  should be shorter, tightening options are: fold "silence, or partial
  compliance" into the previous sentence; drop the parenthetical examples
  in the third paragraph. Recommended not to tighten further — Codex's
  Phase 0 failure was specifically a "resolve ambiguity by acting" pattern,
  and terser wording gives ambiguity back.
