# Draft T007: Preamble line for `.specify/templates/tasks-template.md`

**For**: `.specify/templates/tasks-template.md`
**Per**: FR-005; [ADR 0004](../../../docs/adr/0004-eager-checkbox-update-rule.md)
**Splice point**: as a new bold note between the "Tests: … OPTIONAL" line
and the "Organization: … grouped by user story" line near the top of the
template. This puts it above the fold where an implementer reading the
template will see it before starting to fill it in.

---

Insert this block after the existing "**Tests**:" note and before the
existing "**Organization**:" note:

```markdown
**Checkbox freshness is load-bearing.** When a task is completed, tick its
checkbox in the same commit as the task's output — or at the latest in the
next commit, before starting the next task. Handoff queries ("what was just
done, what remains, what is the next step?") read this file's checkbox
state as the primary state document; stale ticks systematically drift the
answers toward pending items that are secretly done. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).
```

---

## Notes for the reviewer

- Placement rationale: the template's top matter documents expectations
  the implementer needs before filling anything in. Tests-optional and
  Organization-by-user-story are already there. Checkbox-freshness sits
  naturally alongside them.
- Link resolution: the `../../docs/adr/0004-...` path is relative to
  `.specify/templates/`. Once instantiated into a `specs/<feature>/tasks.md`,
  the same relative path from `specs/<feature>/` also resolves correctly
  because both are two levels deep from the repo root — this is the same
  reason `[FEATURE NAME]` template placeholders work identically in both
  locations.
- No verbatim principle text: this note is about a workflow rule
  documented in an ADR, not a constitutional principle. FR-002
  no-duplication doesn't apply here — there's nothing in the
  constitution about tasks.md hygiene.
- Length: ~90 words. Deliberately concise; the ADR carries the full
  reasoning, this preamble states the operational rule.
- Backward compatibility: existing tasks.md files (specs/001, specs/002)
  don't get the preamble retroactively — the template change affects
  only newly-generated tasks.md files from spec-kit skills going
  forward. Existing files are correct as-is.
