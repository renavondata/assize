#!/usr/bin/env bash
# Idempotent environment bootstrap; run by the Claude Code SessionStart hook.
# Record this session's id for the role guards in .claude/commands/. Never committed.
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  python3 -c 'import sys,json; print(json.load(sys.stdin).get("session_id",""))' \
    > "$CLAUDE_PROJECT_DIR/.claude/.session_id" 2>/dev/null || true
fi
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null 2>&1; then
  echo "bootstrap: uv is not available; stop and report (brief 0)." >&2
  exit 1
fi
if [ -f uv.lock ]; then
  uv sync --frozen
else
  uv sync
fi
