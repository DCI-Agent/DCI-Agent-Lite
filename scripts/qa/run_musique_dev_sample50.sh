#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

set -a; source "$REPO_ROOT/.env"; set +a

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval_100.py" \
  --dataset "$REPO_ROOT/data/musique/musique_dev_sample50.jsonl" \
  --output-root "$REPO_ROOT/outputs/qa/openai_musique_dev_sample50" \
  --corpus-dir "/lambda/nfs/demo/GDPval/wiki_corpus" \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --provider openai \
  --model gpt-5.4-nano \
  --tools read,bash \
  --max-turns 300 \
  --max-concurrency 5 \
  --runtime-context-level level3 \
  --pi-thinking-level high \
  --node-max-old-space-size-mb 8192
