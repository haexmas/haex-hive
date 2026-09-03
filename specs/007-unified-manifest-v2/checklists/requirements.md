# Specification Quality Checklist: Unified Manifest v3 (Compound + Molecule + Atom)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-03 (v3 amendment)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No unnecessary implementation details; required contract-level names (`compounds`, `molecules`, `atoms`, diagnostic keys, `molecule-manifest.v3.schema.json`) are included only where needed for interoperability
- [x] Focused on user value (rename that reflects actual semantics + multi-artifact molecules + explicit compound adoption layer)
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
- [x] `contributes.<category>: <path>` explicitly retired in favour of `atoms`
- [x] `kind` discriminator field explicitly NOT introduced; category presence in `atoms` fully identifies what a molecule ships
- [x] "Molecule" (bundle sense from Spec 010 preview) explicitly retired without a replacement term (compound + `.haex-hive.json` collection cover the bundle concept)
- [x] "Assembly" explicitly NOT introduced; retired from earlier v3 drafts to keep the vocabulary at three levels
- [x] Compound layer introduced as the consumer-manifest adoption entry (source + revision + molecule refs)
- [ ] `atom-manifest.v2.schema.json` explicitly retired; `molecule-manifest.v3.schema.json` replaces it (pending the replacement schema and loader update)
- [x] `.haex-hive.json.atoms[]` explicitly renamed to `.compounds[]`; each entry's `includes[]` renamed to `molecules[]`
- [x] Seven new diagnostic keys enumerated (`molecule-manifest-schema-invalid`, `atoms-path-escape`, `atoms-path-duplicate`, `atoms-category-overlap`, `atoms-cardinality-violation`, `atoms-target-invalid`, `unknown-atoms-category`)
- [x] Admitted atoms-category set closed at `{constitution, workflow, extensions, hooks}` at v3 landing; downstream specs may add categories only together with their publication contract
- [x] Every delivered path is checked for an existing regular-file target before staging
- [x] Migration of haex-hive-self molecules explicitly required by FR-008
- [x] Migration of haex-hive-self `.haex-hive.json` (compounds rename) explicitly required by FR-008 + US4 AS4
- [x] Constitution version bump to 1.5.0 flagged in FR-009
- [x] ADR 0010 requirement flagged in §Assumptions
- [x] Cross-molecule dependency graph explicitly out of scope
- [x] Keep-artifacts UX explicitly out of scope
- [x] Category set extensibility model documented (additive, by-spec, no schema re-version)

## Notes

- The simplified spec has 10 FRs, 4 user stories (US1 MVP + US2/US3/US4 P2/P3), 6 SCs, 7 new diagnostic keys, and 4 initially admitted categories. The kind discriminator was considered and explicitly rejected in favour of category-driven identification.
- The rename sweep is large; the actual sweep lands in the plan/tasks phase (this spec only defines that the sweep MUST happen and enumerates the touch surface).
- Items marked incomplete require spec updates before `/speckit-plan`.
