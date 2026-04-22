#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

# Auto-load .env from repo root if present
$SCRIPT_DIR = Split-Path -Parent $PSCommandPath
$REPO_ROOT = Resolve-Path (Join-Path $SCRIPT_DIR "../..")
if (Test-Path (Join-Path $REPO_ROOT ".env")) {
    Get-Content (Join-Path $REPO_ROOT ".env") | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$level = "level5"
$concurrency = "1"
$node_heap_mb = "8192"

uv run python "$REPO_ROOT.Path/scripts/bcplus_eval/run_bcplus_eval_100.py" --dataset "$REPO_ROOT.Path/data/bcplus_sampled_100_qa_with_gold_doc.jsonl" --output-root "$REPO_ROOT.Path/outputs/bcplus_eval_100/anthropic_$level_limit10_concurrency$concurrency" --corpus-dir "$REPO_ROOT.Path/corpus/bc_plus_docs" --package-dir "$REPO_ROOT.Path/pi-mono/packages/coding-agent" --agent-dir "$REPO_ROOT.Path/pi-mono/.pi/agent" --provider anthropic --model claude-sonnet-4-20250514 --tools read,bash --max-turns 100 --limit 10 --max-concurrency "$concurrency" --runtime-context-level "$level" --node-max-old-space-size-mb "$node_heap_mb"
