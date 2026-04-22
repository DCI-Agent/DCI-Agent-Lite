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
level="level5"
concurrency="1"
node_heap_mb="8192"

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval_100.py" \
  --dataset "$REPO_ROOT/data/bcplus_sampled_100_qa_with_gold_doc.jsonl" \
  --output-root "$REPO_ROOT/outputs/bcplus_eval_100/anthropic_${level}_limit10_concurrency${concurrency}" \
  --corpus-dir "$REPO_ROOT/corpus/bc_plus_docs" \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --tools read,bash \
  --max-turns 100 \
  --limit 10 \
  --max-concurrency "$concurrency" \
  --runtime-context-level "$level" \
  --node-max-old-space-size-mb "$node_heap_mb"
