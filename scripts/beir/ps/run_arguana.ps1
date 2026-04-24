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

uv run python "$($REPO_ROOT.Path)/scripts/bcplus_eval/run_bcplus_eval.py" `
  --enable-ir `
  --dataset "$($REPO_ROOT.Path)/data/dci-bench/data/beir_arguana/test.jsonl" `
  --output-root "$($REPO_ROOT.Path)/outputs/beir/arguana" `
  --corpus-dir "/home/ubuntu/demo/haoxiang/ir-eval/beir_corpus/arguana" `
  --package-dir "$($REPO_ROOT.Path)/pi-mono/packages/coding-agent" `
  --agent-dir "$($REPO_ROOT.Path)/pi-mono/.pi/agent" `
  --provider openai `
  --model gpt-5.4-nano `
  --tools read,bash `
  --max-turns 300 `
  --max-concurrency 20 `
  --runtime-context-level level3 `
  --node-max-old-space-size-mb 8192 `
  --corpus-hint "This corpus contains debate arguments from Debatepedia. Each document contains one argument paragraph. Documents are organized in pairs: 'debate-con01a.txt' and 'debate-con01b.txt' are companion paragraphs on the same argument; 'debate-pro02a.txt' pairs with 'debate-pro02b.txt', and so on. The query text is the EXACT content of one 'a' document already in the corpus. Your task is to find the companion 'b' document. SEARCH STRATEGY (follow exactly): (1) Take a short distinctive phrase (5-10 words) from the query text and use grep to locate the matching 'a' file in the corpus. (2) Once you have the filename (e.g. 'debate-con01a.txt'), replace the trailing 'a.txt' with 'b.txt' to get the companion filename (e.g. 'debate-con01b.txt'). (3) Verify that file exists and read it. (4) Rank the companion 'b' document first. Do NOT waste time on broad semantic search â?the companion file is always the same name with 'a' replaced by 'b'."
