# Specification Quality Checklist: Unified Manifest v3 (Molecule + Kind + Delivers)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-03 (v3 amendment)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No unnecessary implementation details; required contract-level names (`kind`, `delivers`, diagnostic keys, `molecule-manifest.v3.schema.json`) are included only where needed for interoperability
- [x] Focused on user value (rename that reflects actual semantics + multi-artifact molecules)
- [x] Written for the stakeholders (publishers + consumers + haex-hive maintainers)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (or clearly named contract-level names)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No unnecessary implementation details leak into the specification

## v3-amendment audit

- [x] "Atom" (packaging unit) explicitly retired in favour of "Molecule"
- [x] `contributes.<kind>: <path>` explicitly retired in favour of `kind` + `delivers`
- [x] "Molecule" (bundle sense from Spec 010 preview) explicitly retired in favour of "Assembly"
- [ ] `atom-manifest.v2.schema.json` explicitly retired; `molecule-manifest.v3.schema.json` replaces it (pending the replacement schema and loader update)
- [x] `.haex-hive.json.atoms[]` explicitly renamed to `.molecules[]`
- [x] Six new diagnostic keys enumerated in FR-001..FR-004
- [x] Migration of haex-hive-self molecules explicitly required by FR-008
- [x] Constitution version bump to 1.5.0 flagged in FR-009
- [x] ADR 0010 requirement flagged in §Assumptions
- [x] Cross-molecule dependency graph explicitly out of scope
- [x] Keep-artifacts UX explicitly out of scope
- [x] Kind enum extensibility model documented

## Notes

- The simplified spec has 10 FRs, 4 user stories (US1 MVP + US2/US3/US4 P2/P3), 6 SCs, 6 new diagnostic keys, and 2 initially admitted kinds. Roughly the same shape as prior versions but with a materially different mechanism.
- The rename sweep is large; the actual sweep lands in the plan/tasks phase (this spec only defines that the sweep MUST happen and enumerates the touch surface).
- Items marked incomplete require spec updates before `/speckit-plan`.
