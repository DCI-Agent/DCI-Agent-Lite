#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

cd "$REPO_ROOT"
uv run hrci-print-pi-system-prompt \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --cwd "$REPO_ROOT/corpus/bc_plus_docs" \
  --tools read,bash
