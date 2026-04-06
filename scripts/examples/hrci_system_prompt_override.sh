#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUESTION="Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."

cd "$REPO_ROOT"
uv run hrci-run-pi-rpc \
  --system-prompt-file "$REPO_ROOT/prompts/system_prompt.txt" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --cwd "$REPO_ROOT/corpus/bc_plus_docs" \
  --tools read,bash \
  --max-turns 6 \
  "$QUESTION"
