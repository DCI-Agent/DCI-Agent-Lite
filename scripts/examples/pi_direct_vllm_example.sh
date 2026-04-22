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

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUESTION=$'Read the files in the current directory. Do not use web search. Use rg instead of grep when searching.\nQuestion: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer\'s first name?\nAnswer with just the first name and one supporting file path.'

# This example expects ~/.pi/agent/models.json to define a custom provider named
# "vllm" and a matching model id. See README for a minimal models.json snippet.
cd "$REPO_ROOT/corpus/bc_plus_docs"
PI_CODING_AGENT_DIR="$REPO_ROOT/pi-mono/.pi/agent" \
node "$REPO_ROOT/pi-mono/packages/coding-agent/dist/cli.js" \
  --provider vllm \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --thinking off \
  --tools read,bash \
  --no-session \
  -p "$QUESTION"
