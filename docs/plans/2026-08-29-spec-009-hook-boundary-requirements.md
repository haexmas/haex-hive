# Spec 009 — Hook Boundary Contract

**Status**: Draft (extracted from [Spec 007 design doc](2026-08-28-spec-007-unified-manifest-design.md) 2026-08-29 to keep the Spec 007 doc focused on the manifest-v2 architecture)
**Author**: haex-hive constitution v1.3.0 process
**Related**: [Spec 007 — Unified Manifest & harness_sources v2 design](2026-08-28-spec-007-unified-manifest-design.md);
[Constitution §Principle I, VI](../../.specify/memory/constitution.md)

## Purpose

Spec 009 delivers `haex hook run <trigger>` — the sole consumer-side
execution surface for publisher-authored code — and is therefore
load-bearing for the operator's trust model. The requirements captured here
are non-negotiable for the Spec 009 landing. When Spec 009 is drafted via
`/speckit-specify`, this document is its authoritative source for the hook
boundary contract; Spec 009's plan/tasks reference this file rather than
restating.

## Hook-boundary requirements

`haex hook run` is the sole consumer-side execution surface for
publisher-authored code and is therefore load-bearing for the operator's
trust model:

- **Filesystem cwd + advisory allowlist**. The subprocess cwd is the consumer
  repo root. The dispatcher contract enumerates a hook's readable and writable
  paths; at minimum, dispatcher-mediated reads are limited to the consumer
  repo tree and `.haex-hive/generated/`, and dispatcher-mediated writes go to
  a per-invocation scratch directory. The dispatcher refuses requests through
  its own file APIs that fall outside this allowlist. Because hooks run under
  the consumer's user account and Spec 007 provides no OS-level sandbox,
  direct filesystem syscalls outside the allowlist cannot be technically
  prevented; this requirement MUST NOT claim kernel-enforced confinement.
- **Environment isolation**. The subprocess starts from an explicit
  allow-list of environment variables (`PATH`, `HOME`, `LANG`, plus a
  named `HAEX_HOOK_*` set); the caller's other environment does not
  leak in, and the hook cannot read the operator's shell state.
- **Process-group reaping**. On Windows, the dispatcher assigns the hook and
  all inherited descendants to a Job Object configured with
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`; timeout or failure closes the job,
  waits for termination, and reaps every process. On Linux, it uses a
  dedicated cgroup v2 subtree and kills the subtree, which also contains
  descendants that create new sessions. On other POSIX platforms, process
  groups alone are explicitly insufficient: the dispatcher MUST use an
  equivalent OS-level descendant container or refuse to run the hook until
  one is available. Tests MUST spawn a descendant that creates a new session
  and prove that timeout and failure terminate and reap it, with no stray
  process remaining.
- **No-follow reads of hook outputs**. The dispatcher establishes a handle to
  the permitted output root and resolves the declared relative path beneath
  that boundary, without following symlinks or reparse points in any parent
  component. On Linux this uses an `openat2`-style beneath/no-symlink resolve;
  POSIX fallbacks open and validate each component relative to a directory
  handle, and Windows uses a constrained directory handle with reparse-point
  rejection. It reads from the opened handle rather than reopening the path,
  verifies the handle's device+inode identity (or Windows volume serial/file
  ID) before and after reading, and rejects any identity change. Tests MUST
  replace a parent directory or output during a read and prove the result is
  rejected. This is the TOCTOU-closure rule.
- **Timeout contract**. Every trigger declares a max wall-clock
  duration; exceeding it marks the invocation as failed and cleans up through
  the platform containment object above: it closes the Windows Job Object,
  kills the Linux cgroup v2 subtree, or uses the required equivalent POSIX
  descendant container. The dispatcher then waits for termination and reaps
  every contained process. No hook can hang the dispatcher indefinitely.

## Runtime secret access

Blueprints that need runtime secrets (API tokens, passwords, private keys)
obtain them out-of-band via the OS keychain at hook-runtime, not through
committed config. See Spec 007 D7 for the "no schema-level secret surface"
principle. The Spec 009 hook dispatcher populates the `HAEX_HOOK_*`
environment variable allow-list with values sourced from the OS keychain
based on aliases declared by the publisher; the hook reads them through
the standard Python `keyring` module or from the pre-populated environment.

## Non-Goals

- Kernel-enforced sandboxing (seccomp/AppArmor/gVisor). See Spec 007
  Non-Goals; this is intentionally out of scope for Spec 009.
- Cross-platform native containment beyond the process-group-reaping
  contract above. Docker-based isolation is not part of the hook boundary.
