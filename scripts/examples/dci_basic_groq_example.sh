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

# Expects ~/.pi/agent/models.json (or pi-mono/.pi/agent/models.json) to define provider "groq"
# and a matching model id. See assets/docs/groq.md.
cd "$REPO_ROOT"
uv run dci-agent-lite \
  --provider groq \
  --model llama-3.3-70b-versatile \
  --cwd "$REPO_ROOT/corpus/wiki_corpus" \
  "$QUESTION"
