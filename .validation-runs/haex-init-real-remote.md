# Real-Remote Smoke Test: `haex-init` external-ref mode

**Purpose**: exercise the external-ref verification path against a
public git remote — proves that the tool's `git fetch` +
`git cat-file` sequence works over the network, not just against a
`file://` fixture. Per FR-039 this test is manual and MUST NOT be
part of `tests/haex-init/run-all.sh`.

**Suggested remote**: `https://github.com/octocat/Hello-World.git` (or
any small public repo). Pick any SHA that resolves and any tracked
path.

## Invocation

```
cd /tmp
mkdir haex-init-real-remote-$$
cd haex-init-real-remote-$$
git init --quiet -b main .
../<path-to>/haex-init
# Choose all tools (or none), then choose external-ref (2).
# Enter the URL, SHA, and path when prompted.
```

## Expected prompts

```
External repository URL: https://github.com/octocat/Hello-World.git
Fetch latest HEAD SHA from remote? [y/N]:
SHA (7-40 lowercase hex): 7fd1a60b01f91b314f59955a4e4d4e80d8edf11d
Path within repository [default: .specify/memory/constitution.md]: README

Verifying reference…
  ✓ reference verified at 7fd1a60b…:README
```

## Expected `.haex-hive.json` shape

```json
{
  "haex_hive_version": "1",
  "identity": "local:haex-init-real-remote-…",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "https://github.com/octocat/Hello-World.git",
      "revision": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
      "path": "README"
    }
  ]
}
```

## Post-condition

```
.specify/scripts/spec-resolve resolve --role constitution
```

Should return the exact byte content of `README` at the pinned SHA in
the octocat/Hello-World remote.

## Cleanup

```
cd ..
rm -rf haex-init-real-remote-$$
rm -rf ~/.cache/haex-init/verify/
```

## Actual run log

_Fill this section in after running the smoke test manually. Include
the invocation timestamp, exact SHA used, and the observed
`spec-resolve resolve` output. When updated, this file serves as
evidence for FR-039._
