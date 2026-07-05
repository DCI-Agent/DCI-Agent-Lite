#!/usr/bin/env bash

# Auto-load .env from repo root if present
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    while [ "$REPO_ROOT" != "/" ] && [ ! -d "$REPO_ROOT/.git" ]; do
        REPO_ROOT="$(dirname "$REPO_ROOT")"
    done
fi
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
level=${1:-"level3"}
concurrency="10"
node_heap_mb="8192"
thinking_level=${2:-""}
output_root="$REPO_ROOT/outputs/bcplus_eval/groq_${level}_concurrency${concurrency}"
if [[ -n "$thinking_level" ]]; then
  output_root="${output_root}_thinking${thinking_level}"
fi

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval.py" \
  --dataset "$REPO_ROOT/data/bcplus_qa.jsonl" \
  --output-root "$output_root" \
  --corpus-dir "$REPO_ROOT/corpus/bc_plus_docs" \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --provider groq \
  --model llama-3.3-70b-versatile \
  --tools read,bash \
  --max-turns 100 \
  --max-concurrency "$concurrency" \
  --pi-thinking-level "$thinking_level" \
  --runtime-context-level "$level" \
  --node-max-old-space-size-mb "$node_heap_mb"
