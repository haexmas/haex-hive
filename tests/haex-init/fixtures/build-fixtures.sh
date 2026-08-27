#!/usr/bin/env bash
# Deterministic fixture builder for haex-init tests.
#
# Produces a fresh tree under tests/haex-init/fixtures/.tmp/ containing:
#
#   family-spec-repo/          — synthetic non-bare git repo with a committed
#                                .specify/memory/constitution.md at a stable
#                                SHA. `file://` URL to this repo is used by
#                                external-ref negative-scheme tests; the bare
#                                mirror family-spec-repo.git/ is used with an
#                                `ssh://`-shaped URL by the happy-path test
#                                (via GIT_SSH_COMMAND redirection is out of
#                                scope; happy-path in T038 uses `file://` +
#                                a documented `--test-allow-file-url` shim
#                                is NOT the choice — we redirect via
#                                `file://` and the test asserts BOTH the
#                                scheme-rejection code path AND the
#                                verification code path in isolation).
#
#   seeded-claude-md.txt       — byte-known payload for marker-safety tests.
#
# Emits fixtures.env inside .tmp/ recording every load-bearing SHA and URL
# so test scripts can `source` it.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$HERE/.tmp"

export GIT_AUTHOR_NAME="haex-init-tests"
export GIT_AUTHOR_EMAIL="tests@haex-init.invalid"
export GIT_COMMITTER_NAME="haex-init-tests"
export GIT_COMMITTER_EMAIL="tests@haex-init.invalid"
export GIT_AUTHOR_DATE="2026-08-27T12:00:00+0000"
export GIT_COMMITTER_DATE="2026-08-27T12:00:00+0000"

rm -rf "$TMP"
mkdir -p "$TMP"

# ---------------------------------------------------------------------------
# family-spec-repo: single-commit repo with .specify/memory/constitution.md
# ---------------------------------------------------------------------------
REPO="$TMP/family-spec-repo"
git init --quiet -b main "$REPO"
(
    cd "$REPO"
    mkdir -p .specify/memory
    printf 'Family spec repo constitution (fixture).\n' > .specify/memory/constitution.md
    git add .specify/memory/constitution.md
    git commit --quiet -m "seed constitution"
)
SHA_FAMILY="$(git -C "$REPO" rev-parse HEAD)"

BARE="$TMP/family-spec-repo.git"
git clone --quiet --bare "$REPO" "$BARE"

# ---------------------------------------------------------------------------
# seeded-claude-md.txt — pre-existing operator content used to prove
# byte-safety outside the marker range.
# ---------------------------------------------------------------------------
cat >"$TMP/seeded-claude-md.txt" <<'EOF'
# My personal notes

Line A
Line B
Line C — meaningful content

## Preferences

- Prefer terse commit messages.
- Never open files in TextEdit.
EOF

# ---------------------------------------------------------------------------
# fixtures.env — sourced by test scripts.
# ---------------------------------------------------------------------------
cat >"$TMP/fixtures.env" <<EOF
FAMILY_REPO_DIR="$REPO"
FAMILY_BARE_DIR="$BARE"
FAMILY_REPO_URL_FILE="file://$BARE"
FAMILY_REPO_URL_HTTPS="https://fixtures.invalid/family-spec-repo.git"
FAMILY_REPO_SHA="$SHA_FAMILY"
FAMILY_REPO_PATH=".specify/memory/constitution.md"
SEEDED_CLAUDE_MD="$TMP/seeded-claude-md.txt"
EOF

echo "haex-init fixtures built under $TMP"
