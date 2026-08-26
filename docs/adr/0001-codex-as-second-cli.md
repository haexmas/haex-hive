# ADR 0001: Codex as the second validation CLI

**Status**: Accepted
**Date**: 2026-08-26

Codex CLI 0.147.0 was chosen as the second validation CLI for the Phase 0
pilot harness per [research.md](../../specs/001-phase-0-pilot-harness/research.md)
Decision 1. `codex doctor` reports a healthy standalone install on the
validation machine, and Codex was verified working end-to-end on 2026-08-26
(see `.validation-runs/2026-08-26.md`). This satisfies spec FR-006 with
the spec's default choice rather than the documented `goose` fallback.

The exact install location is a per-operator local concern and is
intentionally not recorded here (Principle II).
