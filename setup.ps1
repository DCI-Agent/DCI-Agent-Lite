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
    Write-Host "==> Building Pi (npm run build)..." -ForegroundColor Cyan
    npm run build
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
