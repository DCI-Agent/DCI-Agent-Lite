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

$logDir = Join-Path $REPO_ROOT "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$cmds = @(
    @("level0", "medium"),
    @("level1", "high"),
    @("level1", "xhigh"),
    @("level3", "xhigh")
)

foreach ($cmd in $cmds) {
    $level = $cmd[0]
    $thinking = $cmd[1]
    $logFile = Join-Path $logDir "bcplus_eval_100_openai_${level}_${thinking}.log"
    $scriptPath = Join-Path $REPO_ROOT "scripts\bcplus_eval\ps\run_bcplus_eval_100_openai.ps1"
    Write-Host "Running: $scriptPath $level $thinking > $logFile"
    & $scriptPath $level $thinking *| Tee-Object -FilePath $logFile
}
