# ADR 0006: Development Workflow — PR Flow, Merge Strategy, and Conventional Commits

**Status**: Accepted
**Date**: 2026-08-28
**Related**: `.specify/memory/constitution.md` §Development Workflow;
constitution version bump 1.1.1 → 1.2.0

## Context

Two workflow conventions have emerged organically and need to be codified
before further growth of the operator base:

1. **Branch protection on `main`.** The remote at `github.com/haexmas/haex-hive`
   is configured with branch protection: direct pushes to `main` are
   rejected. Every change must land through a pull request. This was not
   documented anywhere in-repo; a session on 2026-08-28 wrote a commit
   directly to `main` locally and had to be redirected to a feature
   branch retroactively.
2. **Commit-message style is not standardized.** Existing commits use
   ad-hoc prefixes (`roadmap:`, `identity:`, `verify:`, `implement:`,
   `spec:`, `design:`, `analyze:`, `merge:`) that read as
   Conventional-Commits-shaped but do not conform to the spec. This
   blocks automated tooling for changelogs, MAJOR/MINOR/PATCH decisions,
   and release notes.

## Decision

Codify three linked conventions in the constitution's Development
Workflow section:

- **PR flow.** All work lands on `main` through a pull request from a topic
  branch. This ADR deliberately does not standardize topic-branch names:
  project tooling retains its configured naming convention. In particular,
  SpecKit's sequential and timestamp branch modes remain supported. Create the
  pull request with `gh pr create --base main --head <branch>`; merging is a
  separate action.
- **Merge strategy.** Rebase-merge OR merge-commit are permitted;
  squash-merge is forbidden because it collapses the individual
  Conventional-Commits messages into one auto-composed message and
  destroys the per-commit type information downstream tooling reads.
  Rebase-merge is the preferred default for its linear history and
  cleaner `git bisect`; merge-commit is a defensible choice when
  PR-boundary visibility in `git log --graph` is wanted for a specific
  PR. When using merge-commit, the maintainer replaces GitHub's generated
  `Merge pull request ...` subject with a Conventional-Commits header before
  merging (for example, `feat(init): add config validation`). With the GitHub
  CLI, use `gh pr merge <number> --merge --subject "<type>[optional
  scope][!]: <description>"`. Commit-message validation and changelog tooling
  must validate and process merge commits rather than exempt generated merge
  subjects.
- **Conventional Commits v1.0.0** (https://www.conventionalcommits.org/en/v1.0.0/)
  as the commit-message standard. Breaking changes are marked with `!`
  after the type/scope (e.g. `feat(api)!: ...`) and — when a written
  explanation adds value — a `BREAKING CHANGE:` footer. The spec's
  standard types apply; no custom `break:` type.

## Consequences

**Immediate**:
- The GitHub repo settings need adjustment: enable rebase-merge and
  merge-commit, disable squash-merge. Operator action, outside this
  repo's files.
- Existing commits are grandfathered (not rewritten). From v1.2.0
  onward, commits must conform.

**Downstream**:
- Automated changelog / release-notes tooling can be introduced without
  a second convention change. Not scoped to this ADR.
- Consumer repos that adopt haex-hive via `haex-init` are NOT bound by
  this ADR — this is haex-hive's own repo policy. `haex-init` does not
  scaffold PR flow, merge strategy, or commit conventions into consumer
  projects; those repos choose their own.

## Alternatives considered

- **Ad-hoc prefixes as-is.** Rejected: readable to humans, opaque to
  tooling. The moment we want automated changelogs, the migration cost
  compounds.
- **Squash-merge kept.** Rejected: destroys the per-commit type
  information Conventional Commits depends on. Would require rebuilding
  it in the squash message every time.
- **Rebase-merge only, merge-commit forbidden.** Rejected: overreach.
  Merge-commit preserves individual Conventional-Commits messages just
  as well as rebase; the real problem is Squash, not merge-commit. A
  rebase-only rule would ban a valid option for no gain.
- **Custom `break:` commit type.** Rejected: not part of the spec.
  Loses compatibility with `semantic-release`, `standard-version`,
  `git-cliff`, and every other off-the-shelf tool.
- **PATCH-only version bump (1.1.2).** Rejected: three new binding
  rules is more than "wording, clarifications, typo fixes" and
  materially changes what future commits and merges must look like.
  MINOR fits.
