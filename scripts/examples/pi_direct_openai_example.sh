#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUESTION=$'Read the files in the current directory. Do not use web search. Use rg instead of grep when searching.\nQuestion: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer\'s first name?\nAnswer with just the first name and one supporting file path.'

cd "$REPO_ROOT/corpus/bc_plus_docs"
PI_CODING_AGENT_DIR="$REPO_ROOT/pi-mono/.pi/agent" \
node "$REPO_ROOT/pi-mono/packages/coding-agent/dist/cli.js" \
  --provider openai \
  --model gpt-5.4 \
  --thinking off \
  --tools read,bash \
  --no-session \
  -p "$QUESTION"
