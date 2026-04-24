# HRCI One-Click Setup (Windows PowerShell)
# Usage: .\setup.ps1

Write-Host "==> Setting up HRCI environment..." -ForegroundColor Cyan

# Load .env if present
if (Test-Path ".env") {
    Write-Host "==> Loading .env..." -ForegroundColor Cyan
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

# 1. Install uv if missing
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing uv..." -ForegroundColor Cyan
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
}

# 2. Install ripgrep if missing
if (-not (Get-Command rg -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing ripgrep..." -ForegroundColor Cyan
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install BurntSushi.ripgrep.MSVC
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install ripgrep
    } else {
        Write-Host "WARN: Could not auto-install ripgrep. Please install manually: https://github.com/BurntSushi/ripgrep#installation" -ForegroundColor Yellow
    }
}

# 3. Sync Python environment
Write-Host "==> Syncing Python dependencies..." -ForegroundColor Cyan
uv sync

# 3b. Ensure Node >= 20 (pi-mono requires node >=20.0.0)
$nodeMajor = 0
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeMajor = [int]((node --version) -replace 'v(\d+).*','$1')
}
if ($nodeMajor -lt 20) {
    Write-Host "==> Node $nodeMajor < 20 detected. Installing Node 20 via nvm-windows..." -ForegroundColor Cyan
    if (Get-Command nvm -ErrorAction SilentlyContinue) {
        nvm install 20
        nvm use 20
    } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "==> Installing nvm-windows via winget..." -ForegroundColor Cyan
        winget install CoreyButler.NVMforWindows --silent
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        nvm install 20
        nvm use 20
    } else {
        Write-Host "WARN: nvm-windows not found and winget unavailable." -ForegroundColor Yellow
        Write-Host "      Please install Node 20 manually: https://nodejs.org/en/download" -ForegroundColor Yellow
    }
    # Explicitly prepend Node 20 bin to PATH so all subsequent subprocesses use it
    $node20Path = (nvm which 20 2>$null)
    if ($node20Path) {
        $node20Bin = Split-Path $node20Path -Parent
        $env:Path = "$node20Bin;$env:Path"
    }
    Write-Host "==> Now using Node $(node --version)" -ForegroundColor Green
}

# 4. Clone and build Pi monorepo if not present
$PI_CLI = "pi-mono/packages/coding-agent/dist/cli.js"
if (-not (Test-Path $PI_CLI)) {
    if (-not (Test-Path "pi-mono")) {
        Write-Host "==> Cloning pi-mono..." -ForegroundColor Cyan
        git clone https://github.com/jdf-prog/pi-mono.git pi-mono
    }
    Set-Location pi-mono
    git checkout codex/context-management-ablation
    Write-Host "==> Installing Pi dependencies (npm install)..." -ForegroundColor Cyan
    npm install
    Write-Host "==> Building Pi (coding-agent and its deps only)..." -ForegroundColor Cyan
    Set-Location packages/tui;  npm run build; Set-Location ../..
    Set-Location packages/ai;   npm run build; Set-Location ../..
    Set-Location packages/agent; npm run build; Set-Location ../..
    Set-Location packages/coding-agent; npm run build; Set-Location ../..
    Set-Location ..
} else {
    Write-Host "==> Pi CLI already built, skipping." -ForegroundColor Green
}

# 5. Download datasets from HuggingFace

# 5a. Corpus (DCI-Agent/corpus)
if (-not (Test-Path "corpus/browsecomp_plus")) {
    Write-Host ""
    Write-Host "==> Downloading corpus from HuggingFace (DCI-Agent/corpus)..." -ForegroundColor Cyan
    Write-Host "    Note: This dataset is gated. Run 'huggingface-cli login' first if needed." -ForegroundColor Cyan
    try {
        uv run python scripts/download_corpus.py
    } catch {
        Write-Host ""
        Write-Host "WARN: Corpus download failed." -ForegroundColor Yellow
        Write-Host "      1. Run 'huggingface-cli login' to authenticate" -ForegroundColor Yellow
        Write-Host "      2. Then re-run: uv run python scripts/download_corpus.py" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "==> Corpus already present in corpus/, skipping download." -ForegroundColor Green
}

# 5b. Benchmark datasets (DCI-Agent/dci-bench)
if (-not (Test-Path "data/dci-bench")) {
    Write-Host ""
    Write-Host "==> Downloading benchmark datasets from HuggingFace (DCI-Agent/dci-bench)..." -ForegroundColor Cyan
    try {
        uv run python scripts/download_dci_bench.py
    } catch {
        Write-Host ""
        Write-Host "WARN: Benchmark dataset download failed." -ForegroundColor Yellow
        Write-Host "      1. Run 'huggingface-cli login' to authenticate" -ForegroundColor Yellow
        Write-Host "      2. Then re-run: uv run python scripts/download_dci_bench.py" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "==> Benchmark datasets already present in data/dci-bench/, skipping download." -ForegroundColor Green
}

# 5c. Extract BrowseComp-Plus QA from parquet to JSONL
if (-not (Test-Path "data/bcplus_qa.jsonl")) {
    Write-Host ""
    Write-Host "==> Extracting BrowseComp-Plus QA pairs to data/bcplus_qa.jsonl..." -ForegroundColor Cyan
    try {
        uv run python scripts/bcplus_eval/extract_bcplus_qa.py
    } catch {
        Write-Host ""
        Write-Host "WARN: QA extraction failed." -ForegroundColor Yellow
        Write-Host "      Make sure data/dci-bench/data/browsecomp-plus/ exists with parquet files." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "==> data/bcplus_qa.jsonl already present, skipping extraction." -ForegroundColor Green
}

# 6. Check API key
if (-not $env:ANTHROPIC_API_KEY -and -not $env:OPENAI_API_KEY) {
    Write-Host ""
    Write-Host "WARN: No ANTHROPIC_API_KEY or OPENAI_API_KEY detected in environment." -ForegroundColor Yellow
    Write-Host "      Please set one before running experiments:" -ForegroundColor Yellow
    Write-Host "      cp .env.template .env  # then edit .env" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==> Setup complete!" -ForegroundColor Green
Write-Host "    Next steps:" -ForegroundColor Green
Write-Host "    1. Set your API key(s): cp .env.template .env" -ForegroundColor Green
Write-Host "    2. Run a test:          .\scripts\examples\ps\hrci_basic_anthropic_example.ps1" -ForegroundColor Green
