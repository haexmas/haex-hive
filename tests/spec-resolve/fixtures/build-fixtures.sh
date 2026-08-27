#!/usr/bin/env bash
# Deterministic fixture builder for spec-resolve tests.
#
# Produces a fresh tree under tests/spec-resolve/fixtures/.tmp/ containing:
#
#   external-repo-a/       — synthetic repo with two commits, README + docs/
#   external-repo-a.git/   — bare mirror of external-repo-a (fetch target)
#   external-repo-b/       — unrelated one-commit repo (used to name a URL
#                            that is deliberately NOT on the consumer's
#                            allowlist)
#
#   consumer-with-role-only/            — minimum-shape config: one self
#                                         constitution entry, no external
#                                         permissions.
#   consumer-with-external-permitted/   — self + repository-only permission
#                                         entry naming external-repo-a.
#   consumer-with-external-narrow/      — self + SHA+paths-constrained
#                                         permission entry for external-repo-a.
#   consumer-with-spec-ref/             — self + permission entry + a
#                                         specs/foo/spec-ref.json naming an
#                                         external ref (used by prefetch
#                                         --dry-run tests).
#
# Emits fixtures.env inside .tmp/ recording every load-bearing SHA and URL
# so test scripts can `source` it.
#
# The consumer fixtures put a two-commit history in place so their .haex-
# hive.json can pin the SHA of an EARLIER commit — resolution reads the file
# at that pinned SHA, which is the behaviour Principle IV requires.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$HERE/.tmp"

# Deterministic author/committer identity + dates. Same-input → same-SHA
# every run.
export GIT_AUTHOR_NAME="haex-hive-tests"
export GIT_AUTHOR_EMAIL="tests@haex-hive.invalid"
export GIT_COMMITTER_NAME="haex-hive-tests"
export GIT_COMMITTER_EMAIL="tests@haex-hive.invalid"
export GIT_AUTHOR_DATE="2026-08-27T12:00:00+0000"
export GIT_COMMITTER_DATE="2026-08-27T12:00:00+0000"

rm -rf "$TMP"
mkdir -p "$TMP"

# ---------------------------------------------------------------------------
# external-repo-a: two commits touching README and docs/
# ---------------------------------------------------------------------------
REPO_A="$TMP/external-repo-a"
git init --quiet -b main "$REPO_A"
(
    cd "$REPO_A"
    printf 'Fixture A — commit 1\n' > README.md
    git add README.md
    git commit --quiet -m "commit-1"
    mkdir -p docs
    printf 'Fixture A — commit 2 docs\n' > docs/pinned.md
    git add docs/pinned.md
    git commit --quiet -m "commit-2"
)
SHA_A1="$(git -C "$REPO_A" rev-list --max-parents=0 HEAD)"
SHA_A2="$(git -C "$REPO_A" rev-parse HEAD)"

BARE_A="$TMP/external-repo-a.git"
git clone --quiet --bare "$REPO_A" "$BARE_A"

# ---------------------------------------------------------------------------
# external-repo-b: one-commit distinct repo.
# ---------------------------------------------------------------------------
REPO_B="$TMP/external-repo-b"
git init --quiet -b main "$REPO_B"
(
    cd "$REPO_B"
    printf 'Fixture B\n' > README.md
    git add README.md
    git commit --quiet -m "commit-1"
)
SHA_B1="$(git -C "$REPO_B" rev-parse HEAD)"

# ---------------------------------------------------------------------------
# Consumer fixtures.
#
# Each consumer is a git repo. Commit sequence:
#   commit-1  seeds .specify/memory/constitution.md and a placeholder
#             .haex-hive.json whose revision is all-zeros.
#   commit-2  overwrites .haex-hive.json to pin the SHA of commit-1 —
#             so `resolve --role constitution` returns the exact contents
#             of .specify/memory/constitution.md as they existed at
#             commit-1.
# ---------------------------------------------------------------------------

seed_and_pin() {
    local dir="$1"
    local final_json_template="$2"

    git init --quiet -b main "$dir"
    (
        cd "$dir"
        mkdir -p .specify/memory
        printf 'Consumer constitution — %s\n' "$(basename "$dir")" > .specify/memory/constitution.md
        # Placeholder .haex-hive.json — real content committed at commit-2.
        printf '{"haex_hive_version":"1","identity":"local:seed","harness_sources":[]}\n' > .haex-hive.json
        git add .haex-hive.json .specify/memory/constitution.md
        git commit --quiet -m "commit-1: seed"
        PIN_SHA="$(git rev-parse HEAD)"
        # Substitute PIN_SHA into the template and commit as commit-2.
        printf '%s\n' "${final_json_template//__PIN_SHA__/$PIN_SHA}" > .haex-hive.json
        git add .haex-hive.json
        git commit --quiet -m "commit-2: pin constitution"
    )
}

# consumer-with-role-only
seed_and_pin "$TMP/consumer-with-role-only" '{
  "haex_hive_version": "1",
  "identity": "local:consumer-with-role-only",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "__PIN_SHA__",
      "path": ".specify/memory/constitution.md"
    }
  ],
  "groups": [],
  "active_feature": null
}'

# consumer-with-external-permitted (repository-only scope permission)
seed_and_pin "$TMP/consumer-with-external-permitted" "$(cat <<JSON
{
  "haex_hive_version": "1",
  "identity": "local:consumer-with-external-permitted",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "__PIN_SHA__",
      "path": ".specify/memory/constitution.md"
    },
    {
      "repository": "ssh://git@fixtures.invalid/external-repo-a"
    }
  ],
  "groups": [],
  "active_feature": null
}
JSON
)"

# consumer-with-external-narrow (SHA+paths scope permission — permits
# exactly external-repo-a@SHA_A1 restricted to README.md).
seed_and_pin "$TMP/consumer-with-external-narrow" "$(cat <<JSON
{
  "haex_hive_version": "1",
  "identity": "local:consumer-with-external-narrow",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "__PIN_SHA__",
      "path": ".specify/memory/constitution.md"
    },
    {
      "repository": "ssh://git@fixtures.invalid/external-repo-a",
      "revision": "$SHA_A1",
      "paths": ["README.md"]
    }
  ],
  "groups": [],
  "active_feature": null
}
JSON
)"

# consumer-with-spec-ref — permission entry plus a spec-ref.json naming an
# external reference. Used by prefetch --dry-run tests. The URL uses an
# SCP-style pattern the resolver accepts syntactically but that never
# resolves (fictional host), so dry-run reports MISSING without any real
# network attempt.
seed_and_pin "$TMP/consumer-with-spec-ref" "$(cat <<JSON
{
  "haex_hive_version": "1",
  "identity": "local:consumer-with-spec-ref",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "__PIN_SHA__",
      "path": ".specify/memory/constitution.md"
    },
    {
      "repository": "ssh://git@fixtures.invalid/external-repo-a"
    }
  ],
  "groups": [],
  "active_feature": null
}
JSON
)"
mkdir -p "$TMP/consumer-with-spec-ref/specs/example-feature"
cat > "$TMP/consumer-with-spec-ref/specs/example-feature/spec-ref.json" <<JSON
{
  "docs-pinned": {
    "repository": "ssh://git@fixtures.invalid/external-repo-a",
    "revision": "$SHA_A2",
    "path": "docs/pinned.md"
  }
}
JSON
(
    cd "$TMP/consumer-with-spec-ref"
    git add specs/example-feature/spec-ref.json
    git commit --quiet -m "commit-3: add spec-ref"
)

# Read each consumer's pinned SHA back out and emit fixtures.env.
CONS_ROLE_ONLY_PIN="$(python3 -c 'import json; print(json.load(open("'"$TMP"'/consumer-with-role-only/.haex-hive.json"))["harness_sources"][0]["revision"])')"
CONS_EXT_PERM_PIN="$(python3 -c 'import json; print(json.load(open("'"$TMP"'/consumer-with-external-permitted/.haex-hive.json"))["harness_sources"][0]["revision"])')"
CONS_EXT_NARROW_PIN="$(python3 -c 'import json; print(json.load(open("'"$TMP"'/consumer-with-external-narrow/.haex-hive.json"))["harness_sources"][0]["revision"])')"
CONS_SPEC_REF_PIN="$(python3 -c 'import json; print(json.load(open("'"$TMP"'/consumer-with-spec-ref/.haex-hive.json"))["harness_sources"][0]["revision"])')"

cat > "$TMP/fixtures.env" <<ENV
SHA_A1=$SHA_A1
SHA_A2=$SHA_A2
SHA_B1=$SHA_B1
EXT_A_URL=ssh://git@fixtures.invalid/external-repo-a
EXT_A_BARE=$BARE_A
CONS_ROLE_ONLY_PIN=$CONS_ROLE_ONLY_PIN
CONS_EXT_PERM_PIN=$CONS_EXT_PERM_PIN
CONS_EXT_NARROW_PIN=$CONS_EXT_NARROW_PIN
CONS_SPEC_REF_PIN=$CONS_SPEC_REF_PIN
ENV

echo "fixtures built at $TMP"
cat "$TMP/fixtures.env"
