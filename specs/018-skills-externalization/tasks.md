# Tasks: External Skill References

**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Tests**: Required for schema/model behavior and compatibility.

- [x] T001 Write the Phase-A Spec-Kit spec, plan, data model, contract,
  quickstart, and requirements checklist, including the co-located-skill
  ownership/delivery boundary.
- [x] T002 Add red contract tests for accepted external references and retired
  skill categories in `tests/contract/test_molecule_manifest_external_skills.py`.
- [x] T003 Add red parser tests for immutable ordered references and the
  install-hook requirement in `tests/unit/test_external_skills_parser.py`.
- [x] T004 Extend `molecule-manifest.v4.schema.json` with `external_skills`,
  the hook condition, and retired-category rejection.
- [x] T005 Extend `MoleculeManifest` with immutable `external_skills` parsing.
- [x] T006 Update fixtures and docs that used `atoms.skills` as a generic test
  category; preserve historical specs as historical records.
- [x] T007 Update README and behavior-alignment documentation for the external
  skill boundary.
- [x] T008 Bump the package metadata to the planned 5.0.0 Phase-A line and
  refresh the lock metadata.
- [x] T009 Run focused tests, full tests, Ruff, and mypy; update this checklist
  eagerly with the evidence.
