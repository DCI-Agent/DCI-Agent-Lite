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

uv run python "$REPO_ROOT.Path/scripts/bcplus_eval/run_bcplus_eval_100.py" --dataset "$REPO_ROOT.Path/data/bcplus_sampled_100_qa.jsonl" --output-root "$REPO_ROOT.Path/outputs/bcplus_eval_100/openai_level4_read_grep" --corpus-dir "$REPO_ROOT.Path/corpus/bc_plus_docs" --package-dir "$REPO_ROOT.Path/pi-mono/packages/coding-agent" --agent-dir "$REPO_ROOT.Path/pi-mono/.pi/agent" --provider openai --model gpt-5.4-nano --tools read,grep --max-turns 300 --max-concurrency 10 --runtime-context-level level4 --node-max-old-space-size-mb 8192
