#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

set -a; source "$REPO_ROOT/.env"; set +a

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval_100.py" \
  --dataset "$REPO_ROOT/data/bcplus_sampled_100_qa.jsonl" \
  --output-root "$REPO_ROOT/outputs/bcplus_eval_100/anthropic_level0" \
  --corpus-dir "$REPO_ROOT/corpus/bc_plus_docs" \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --tools read,bash \
  --max-turns 100 \
  --max-concurrency 1 \
  --runtime-context-level level0 \
  --node-max-old-space-size-mb 8192
