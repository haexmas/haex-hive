# ADR 0001: Codex as the second validation CLI

**Status**: Accepted
**Date**: 2026-08-26

Codex CLI 0.147.0 was chosen as the second validation CLI for the Phase 0
pilot harness per [research.md](../../specs/001-phase-0-pilot-harness/research.md)
Decision 1. It is installed at `~/.local/bin/codex`, `codex doctor` reports a
healthy install, and it was verified working on 2026-08-26. This satisfies
spec FR-006 with the spec's default choice rather than the documented
`goose` fallback.
