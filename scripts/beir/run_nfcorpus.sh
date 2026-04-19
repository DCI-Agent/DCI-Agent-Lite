#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

set -a; source "$REPO_ROOT/.env"; set +a

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval_100.py" \
  --enable-ir \
  --dataset "/home/ubuntu/demo/haoxiang/ir-eval/data/beir/nfcorpus/beir_nfcorpus_sample50.jsonl" \
  --output-root "$REPO_ROOT/outputs/beir/nfcorpus" \
  --corpus-dir "/home/ubuntu/demo/haoxiang/ir-eval/beir_corpus/nfcorpus" \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --provider openai \
  --model gpt-5.4-nano \
  --tools read,bash \
  --max-turns 300 \
  --max-concurrency 20 \
  --runtime-context-level level3 \
  --node-max-old-space-size-mb 8192
