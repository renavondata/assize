#!/usr/bin/env bash
# Idempotent environment bootstrap; run by the Claude Code SessionStart hook.
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
