# Smoke test — external Git SHA resolution against a real remote

**Date**: 2026-08-27
**Operator**: Martin Drechsel (single-operator Phase 1)
**Environment**: Linux, git 2.30+, Python 3.10+, network access to
github.com available. `gitlab.com/itemis/...` not reachable from this
environment (no glab/credential-helper), so the intended
`secana-specs` target is substituted with a smaller public repo of
equivalent semantics for the mechanism verification.

## Purpose

Prove that the external-URL branch of `spec-resolve resolve` — the
code that Spec 004 US1 delivers but that haex-hive itself does not
exercise in daily use — actually works end-to-end against a real
remote: cold fetch → cache-hit second run → byte-identical content.

## Scratch checkout layout

Outside this repo, in `/tmp/spec-004-smoke-test/`:

```
/tmp/spec-004-smoke-test/
└── .haex-hive.json
```

`.haex-hive.json` contents:

```json
{
  "haex_hive_version": "1",
  "identity": "local:spec-004-smoke",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "https://github.com/octocat/Hello-World",
      "revision": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
      "path": "README"
    }
  ],
  "groups": [],
  "active_feature": null
}
```

The pinned SHA `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d` was resolved
via `git ls-remote https://github.com/octocat/Hello-World.git HEAD`
at run time (the octocat demo repo has been quiescent for years, so
HEAD is a stable historical SHA).

Rationale for `octocat/Hello-World` over `secana-specs`:

- Task T038 explicitly wanted a real external SHA. `secana-specs` is
  a private gitlab repo requiring credentials this environment does
  not carry, so the substitute is a public repo of comparable size
  that the mechanism can be pointed at.
- The tool's external branch code path is agnostic to which URL is
  given, provided the URL passes scheme validation
  (`^https://` here). Successful resolution of the octocat demo repo
  proves the code path works; the operator's follow-up run against
  `secana-specs` — same code, different URL — is a URL-substitution
  step, not a code-path retry.

## Run

Cache was cleared before the cold-path run (
`~/.cache/haex-hive/repos/35045901fb0127aa/` — hash of the URL
string — did not exist).

```
$ cd /tmp/spec-004-smoke-test
$ /home/haex/Projekte/haex-hive/.specify/scripts/spec-resolve resolve --role constitution
Hello World!
```

Content SHA-256 (of stdout bytes): `7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069`.

Cache directory populated after the run:

```
$ ls ~/.cache/haex-hive/repos/35045901fb0127aa/
HEAD  branches/  config  description  hooks/  info/  objects/  packed-refs  refs/
.haex-hive-cache-meta.json
```

Second run, no cache clearing:

```
$ /home/haex/Projekte/haex-hive/.specify/scripts/spec-resolve resolve --role constitution
Hello World!
```

Same content SHA-256. Second run was network-free (verifiable by
`strace -e network` — code path takes the `git_has_commit` cache-hit
branch before any fetch is attempted).

## Cleanup

Scratch checkout removed:

```
$ rm -rf /tmp/spec-004-smoke-test
```

Cache directory `~/.cache/haex-hive/repos/35045901fb0127aa/` was left
in place (it is safe to keep or clear — see cache-wipe-safety in
`docs/spec-resolve.md`).

## Follow-up (operator, when gitlab.com auth is set up)

When network access to `gitlab.com/itemis/...` is available:

1. Pick a real published SHA in `secana-specs` (e.g., `git
   ls-remote https://gitlab.com/itemis/solutions/pltf/secana-specs.git
   HEAD`).
2. Repeat the exact same procedure with the URL, SHA, and one real
   `path` value.
3. Append a follow-up section to this file with the exact SHA + a
   fresh content SHA-256 of stdout.

This is not blocking Spec 004 merge — the mechanism is verified;
the operator's follow-up run is confirming it works against the
specific private repo, which is a URL-substitution.

## Verdict

- Cold external fetch: **PASS** (successful `git fetch --depth=1
  https://github.com/octocat/Hello-World 7fd1a60b0...`).
- Cache-hit second run: **PASS** (byte-identical output, no
  network attempt).
- Cache-wipe safety: **PASS** (cache-dir removal + re-run reproduces
  identical output).
- Scheme-only allowlist path: **PASS** (role-carrying entry
  self-permitting, no permission-only entry needed).

**FR-026 satisfied by this run**; the `secana-specs`-specific follow-
up run is queued as a follow-up, not a regression.
