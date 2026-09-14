# Implementation Plan: External Skill References

**Branch**: `018-skills-externalization` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

## Summary

Add a typed, structured `external_skills` metadata field to v4 molecule
manifests, reject the retired `skill` and `skills` atom categories, and
document that external installation remains an existing `install_hook`
responsibility. Each reference records a repository, full revision SHA, and
repository-relative skill path. Skills may remain co-located with molecules in
`haexmas/atoms`; no repository split is required. The default hook adapter is
the independently maintained Python `skillsmd` package invoked through `uvx`.
spaex core does not depend on or execute that installer directly.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: Existing `jsonschema`; Python standard library;
publisher hooks may invoke pinned PyPI `skillsmd` through `uvx`
**Storage**: JSON molecule manifests and existing install lock
**Testing**: pytest, schema contract tests, integration tests
**Target Platform**: Local repository CLI on supported Python platforms
**Project Type**: Python CLI/library
**Constraints**: No network or subprocess work at import/parse time; no skill
registry dependency in spaex core; preserve deterministic manifest parsing;
install hooks retain the existing consumer-user trust boundary
**Scale/Scope**: Molecule manifest schema/model, docs, focused fixtures

## Constitution Check

- Spec-Kit contract is present before implementation.
- No new dependency is added to spaex core; the publisher-owned hook may
  resolve a pinned external adapter through the user's uv runtime.
- Existing install-hook trust and failure boundary is reused.
- Cross-repository skill references use a full revision SHA and
  repository-relative path.
- The change is split into small schema/model/documentation slices under the
  500-LoC source-file boundary.
- The external `atoms` repository is not modified from this checkout.

## Project Structure

```text
specs/018-skills-externalization/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/molecule-manifest-external-skills.v1.md
└── tasks.md

src/spaex/model/molecule_manifest.py
src/spaex/schema/data/molecule-manifest.v4.schema.json
tests/contract/test_molecule_manifest_external_skills.py
tests/unit/test_external_skills_parser.py
tests/unit/test_hook_runner.py
tests/integration/test_external_skill_hook.py
src/spaex/install/hook_runner.py
```

**Structure Decision**: Extend the existing molecule model and v4 schema in
place. The external reference is metadata, not an atom path, so it must not
enter the existing materialization pipeline.

## Complexity Tracking

No constitution violations.
