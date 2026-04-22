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

