#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
level=${1:-"level5"}
concurrency="10"
node_heap_mb="8192"

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval_100.py" \
  --dataset "$REPO_ROOT/data/bcplus_sampled_100_qa_with_gold_doc.jsonl" \
  --output-root "$REPO_ROOT/outputs/bcplus_eval_100/openai_${level}_concurrency${concurrency}" \
  --corpus-dir "$REPO_ROOT/corpus/bc_plus_docs" \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --provider openai \
  --model gpt-5.4-nano \
  --tools read,bash \
  --max-turns 100 \
  --max-concurrency "$concurrency" \
  --runtime-context-level "$level" \
  --node-max-old-space-size-mb "$node_heap_mb"


bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh level0 > logs/bcplus_eval_100_openai_level0.log 2>&1 
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh level1 > logs/bcplus_eval_100_openai_level1.log 2>&1
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh level2 > logs/bcplus_eval_100_openai_level2.log 2>&1
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh level3 > logs/bcplus_eval_100_openai_level3.log 2>&1
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh level4 > logs/bcplus_eval_100_openai_level4.log 2>&1
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh level5 > logs/bcplus_eval_100_openai_level5.log 2>&1