# Implementation Plan: External Skill References

**Branch**: `018-skills-externalization` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

## Summary

Add a typed `external_skills` metadata field to v4 molecule manifests, reject
the retired `skill` and `skills` atom categories, and document that external
installation remains an existing `install_hook` responsibility. Skills may
remain co-located with molecules in `haexmas/atoms`; no repository split is
required. No new runtime dependency or installer is introduced.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: Existing `jsonschema`; Python standard library
**Storage**: JSON molecule manifests and existing install lock
**Testing**: pytest, schema contract tests, integration tests
**Target Platform**: Local repository CLI on supported Python platforms
**Project Type**: Python CLI/library
**Constraints**: No network or subprocess work at import/parse time; no skill
registry dependency; preserve deterministic manifest parsing
**Scale/Scope**: Molecule manifest schema/model, docs, focused fixtures

## Constitution Check

- Spec-Kit contract is present before implementation.
- No new dependency is needed.
- Existing install-hook trust and failure boundary is reused.
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
```

**Structure Decision**: Extend the existing molecule model and v4 schema in
place. The external reference is metadata, not an atom path, so it must not
enter the existing materialization pipeline.

## Complexity Tracking

No constitution violations.
