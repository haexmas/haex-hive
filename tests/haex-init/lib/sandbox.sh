#!/usr/bin/env bash
# Sandbox helpers for haex-init tests.
#
# Every test runs in complete isolation from the developer's real $HOME:
#   - HOME points into $SANDBOX_ROOT/home
#   - $SANDBOX_ROOT/fake-bin is prepended to PATH
#   - $SANDBOX_ROOT/project is a fresh empty project directory
#
# Tests source this file, call setup_sandbox() at the top, and MUST call
# teardown_sandbox() before exiting (via `trap` in the test).

# NB: This file is intended to be sourced, not executed directly.
# We deliberately do NOT `set -euo pipefail` here — the caller controls
# its own error handling, and setting it in a sourced file affects the
# caller in ways it may not want.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HAEX_INIT="$REPO_ROOT/.specify/scripts/haex-init"
export REPO_ROOT HAEX_INIT

# setup_sandbox — create a fresh sandbox tree and export HOME/PATH.
# Usage: setup_sandbox [name]  (name defaults to the caller script's basename)
setup_sandbox() {
    local name="${1:-haex-init-test}"
    SANDBOX_ROOT="$(mktemp -d -t "haex-init-${name}-XXXXXX")"
    export SANDBOX_ROOT
    mkdir -p "$SANDBOX_ROOT/home" "$SANDBOX_ROOT/fake-bin" "$SANDBOX_ROOT/project"
    # Save the real HOME/PATH so teardown can leave the operator's env intact
    # even if the caller runs many test scripts back-to-back.
    _HAEX_REAL_HOME="${HOME:-}"
    _HAEX_REAL_PATH="${PATH:-}"
    export HOME="$SANDBOX_ROOT/home"
    export PATH="$SANDBOX_ROOT/fake-bin:$_HAEX_REAL_PATH"
    # Isolate the XDG cache so external-ref verification writes into the
    # sandbox instead of the developer's ~/.cache.
    export XDG_CACHE_HOME="$SANDBOX_ROOT/home/.cache"
    mkdir -p "$XDG_CACHE_HOME"
    # Deterministic git identity for scaffolding commits inside the sandbox.
    export GIT_AUTHOR_NAME="haex-init-tests"
    export GIT_AUTHOR_EMAIL="tests@haex-init.invalid"
    export GIT_COMMITTER_NAME="haex-init-tests"
    export GIT_COMMITTER_EMAIL="tests@haex-init.invalid"
    # Change into the fresh project.
    cd "$SANDBOX_ROOT/project"
}

teardown_sandbox() {
    if [[ -n "${SANDBOX_ROOT:-}" && -d "$SANDBOX_ROOT" ]]; then
        rm -rf "$SANDBOX_ROOT"
    fi
    if [[ -n "${_HAEX_REAL_HOME:-}" ]]; then
        export HOME="$_HAEX_REAL_HOME"
    else
        unset HOME || true
    fi
    if [[ -n "${_HAEX_REAL_PATH:-}" ]]; then
        export PATH="$_HAEX_REAL_PATH"
    else
        unset PATH || true
    fi
    unset SANDBOX_ROOT XDG_CACHE_HOME _HAEX_REAL_HOME _HAEX_REAL_PATH
}

# install_fake_bin NAME — drop a stub `NAME` executable into $SANDBOX_ROOT/fake-bin.
install_fake_bin() {
    local name="$1"
    local path="$SANDBOX_ROOT/fake-bin/$name"
    cat >"$path" <<EOF
#!/usr/bin/env bash
echo "$name"
exit 0
EOF
    chmod +x "$path"
}

# create_fake_config_dir TOOL — create the tool's expected user-config dir.
# Recognized TOOL values:
#   claude-code, codex, gemini,
#   vscode, vscode-insiders, cursor, windsurf, jetbrains
create_fake_config_dir() {
    local tool="$1"
    case "$tool" in
        claude-code)     mkdir -p "$HOME/.claude" ;;
        codex)           mkdir -p "$HOME/.codex" ;;
        gemini)          mkdir -p "$HOME/.gemini" ;;
        vscode)          mkdir -p "$HOME/.config/Code" ;;
        vscode-insiders) mkdir -p "$HOME/.config/Code - Insiders" ;;
        cursor)          mkdir -p "$HOME/.config/Cursor" ;;
        windsurf)        mkdir -p "$HOME/.config/Windsurf" ;;
        jetbrains)       mkdir -p "$HOME/.config/JetBrains" ;;
        *)
            echo "sandbox: unknown tool $tool" >&2
            return 1
            ;;
    esac
}

# checksum_tree PATH — print a stable SHA-256 of a directory's contents.
# Hashes each regular file's (relative path, size, sha256) in sorted order and
# summarizes with a single SHA-256 over the concatenation.
checksum_tree() {
    local root="$1"
    if [[ ! -d "$root" ]]; then
        echo "checksum_tree: $root is not a directory" >&2
        return 1
    fi
    (
        cd "$root"
        # Include hidden files, sort deterministically.
        find . -type f -print0 | LC_ALL=C sort -z | while IFS= read -r -d '' f; do
            local sz sha
            sz=$(stat -c '%s' -- "$f" 2>/dev/null || stat -f '%z' -- "$f")
            sha=$(sha256sum -- "$f" | awk '{print $1}')
            printf '%s\t%s\t%s\n' "$f" "$sz" "$sha"
        done
    ) | sha256sum | awk '{print $1}'
}

# assert_eq — small helper for test assertions.
assert_eq() {
    local label="$1"
    local expected="$2"
    local actual="$3"
    if [[ "$expected" != "$actual" ]]; then
        echo "assert_eq FAILED [$label]: expected '$expected' got '$actual'" >&2
        return 1
    fi
}

# assert_contains — assert stdout/haystack contains needle.
assert_contains() {
    local label="$1"
    local haystack="$2"
    local needle="$3"
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "assert_contains FAILED [$label]: needle not found in haystack" >&2
        echo "needle: $needle" >&2
        echo "haystack:" >&2
        echo "$haystack" >&2
        return 1
    fi
}

# assert_not_contains — negative variant.
assert_not_contains() {
    local label="$1"
    local haystack="$2"
    local needle="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "assert_not_contains FAILED [$label]: needle found in haystack" >&2
        echo "needle: $needle" >&2
        return 1
    fi
}
