#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUESTION="Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."

# This example expects ~/.pi/agent/models.json to define a custom provider named
# "vllm" and a matching model id. See README for a minimal models.json snippet.
cd "$REPO_ROOT"
uv run hrci-run-pi-rpc \
  --provider vllm \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --cwd "$REPO_ROOT/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --show-tools \
  "$QUESTION"
