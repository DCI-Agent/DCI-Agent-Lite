#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

# Auto-load .env from repo root if present
$SCRIPT_DIR = Split-Path -Parent $PSCommandPath
$REPO_ROOT = Resolve-Path (Join-Path $SCRIPT_DIR "../../..")
if (Test-Path (Join-Path $REPO_ROOT ".env")) {
    Get-Content (Join-Path $REPO_ROOT ".env") | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$level = if ($args[0]) { $args[0] } else { "level5" }
$concurrency = "10"
$node_heap_mb = "8192"
$thinking_level = if ($args[1]) { $args[1] } else { "" }
$output_root = "$($REPO_ROOT.Path)/outputs/bcplus_eval_100/openai_${level}_concurrency${concurrency}"
if ($thinking_level) {
    $output_root = "${output_root}_thinking${thinking_level}"
}

uv run python "$($REPO_ROOT.Path)/scripts/bcplus_eval/run_bcplus_eval_100.py" `
  --dataset "$($REPO_ROOT.Path)/data/bcplus_sampled_100_qa_with_gold_doc.jsonl" `
  --output-root "$output_root" `
  --corpus-dir "$($REPO_ROOT.Path)/corpus/bc_plus_docs" `
  --package-dir "$($REPO_ROOT.Path)/pi-mono/packages/coding-agent" `
  --agent-dir "$($REPO_ROOT.Path)/pi-mono/.pi/agent" `
  --provider openai `
  --model gpt-5.4-nano `
  --tools read,bash `
  --max-turns 100 `
  --max-concurrency "$concurrency" `
  --pi-thinking-level="$thinking_level" `
  --runtime-context-level "$level" `
  --node-max-old-space-size-mb "$node_heap_mb"
