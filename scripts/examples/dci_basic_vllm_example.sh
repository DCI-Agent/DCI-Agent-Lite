#!/usr/bin/env bash

set -euo pipefail

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

QUESTION="Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?"

# This example expects ~/.pi/agent/models.json to define a custom provider named
# "vllm" and a matching model id. See assets/docs/setup.md for vLLM configuration.
cd "$REPO_ROOT"
uv run dci-agent-lite \
  --provider vllm \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --cwd "$REPO_ROOT/corpus/wiki_corpus" \
  "$QUESTION"
