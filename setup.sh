#!/usr/bin/env bash
set -euo pipefail

# DCI One-Click Setup (Unix/macOS)
# Usage: bash setup.sh

echo "==> Setting up DCI environment..."

# Load .env if present
if [ -f ".env" ]; then
    echo "==> Loading .env..."
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | xargs)
fi

# 1. Install uv if missing
if ! command -v uv &> /dev/null; then
    echo "==> Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1091
    source "$HOME/.local/bin/env" 2>/dev/null || true
fi

# 2. Install ripgrep if missing
if ! command -v rg &> /dev/null; then
    echo "==> Installing ripgrep..."
    if command -v brew &> /dev/null; then
        brew install ripgrep
    elif command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y ripgrep
    elif command -v pacman &> /dev/null; then
        sudo pacman -S ripgrep
    else
        echo "WARN: Could not auto-install ripgrep. Please install manually: https://github.com/BurntSushi/ripgrep#installation"
    fi
fi

# 3. Sync Python environment
echo "==> Syncing Python dependencies..."
uv sync

# 3b. Ensure Node >= 20 (pi-mono requires node >=20.0.0)
_node_major() { node --version 2>/dev/null | sed 's/v\([0-9]*\).*/\1/'; }
if [ "$(_node_major)" -lt 20 ] 2>/dev/null; then
    echo "==> Node $(_node_major) < 20 detected. Installing Node 20 via nvm..."
    # Load nvm if available
    NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    # shellcheck disable=SC1091
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
    if command -v nvm &>/dev/null; then
        nvm install 20
        nvm use 20
    else
        echo "==> nvm not found. Installing nvm then Node 20..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
        # shellcheck disable=SC1091
        source "$NVM_DIR/nvm.sh"
        nvm install 20
        nvm use 20
    fi
    # Explicitly prepend Node 20 bin to PATH so all subsequent subprocesses use it
    _node20_bin="$(nvm which 20 2>/dev/null | xargs dirname)"
    if [ -n "$_node20_bin" ]; then
        export PATH="$_node20_bin:$PATH"
    fi
    echo "==> Now using Node $(node --version)"
fi

# 4. Clone and build Pi monorepo if CLI is not present
PI_CLI="pi-mono/packages/coding-agent/dist/cli.js"
if [ ! -f "$PI_CLI" ]; then
    if [ ! -d "pi-mono" ]; then
        echo "==> Cloning pi-mono..."
        git clone https://github.com/jdf-prog/pi-mono.git pi-mono
    fi
    cd pi-mono
    git checkout codex/context-management-ablation
    echo "==> Installing Pi dependencies (npm install)..."
    npm install
    echo "==> Building Pi (coding-agent and its deps only)..."
    (cd packages/tui && npm run build)
    (cd packages/ai && npm run build)
    (cd packages/agent && npm run build)
    (cd packages/coding-agent && npm run build)
    cd ..
else
    echo "==> Pi CLI already built, skipping."
fi

# 5. Download datasets from HuggingFace

# 5a. Corpus (DCI-Agent/corpus)
if [ ! -d "corpus/browsecomp_plus" ]; then
    echo ""
    echo "==> Downloading corpus from HuggingFace (DCI-Agent/corpus)..."
    echo "    Note: This dataset is gated. Run 'huggingface-cli login' first if needed."
    uv run python scripts/download_corpus.py || {
        echo ""
        echo "WARN: Corpus download failed."
        echo "      1. Run 'huggingface-cli login' to authenticate"
        echo "      2. Then re-run: uv run python scripts/download_corpus.py"
    }
else
    echo ""
    echo "==> Corpus already present in corpus/, skipping download."
fi

# 5b. Benchmark datasets (DCI-Agent/dci-bench)
if [ ! -d "data/dci-bench" ]; then
    echo ""
    echo "==> Downloading benchmark datasets from HuggingFace (DCI-Agent/dci-bench)..."
    uv run python scripts/download_dci_bench.py || {
        echo ""
        echo "WARN: Benchmark dataset download failed."
        echo "      1. Run 'huggingface-cli login' to authenticate"
        echo "      2. Then re-run: uv run python scripts/download_dci_bench.py"
    }
else
    echo ""
    echo "==> Benchmark datasets already present in data/dci-bench/, skipping download."
fi

# 5c. Extract BrowseComp-Plus QA from parquet to JSONL
if [ ! -f "data/bcplus_qa.jsonl" ]; then
    echo ""
    echo "==> Extracting BrowseComp-Plus QA pairs to data/bcplus_qa.jsonl..."
    uv run python scripts/bcplus_eval/extract_bcplus_qa.py || {
        echo ""
        echo "WARN: QA extraction failed."
        echo "      Make sure data/dci-bench/data/browsecomp-plus/ exists with parquet files."
    }
else
    echo ""
    echo "==> data/bcplus_qa.jsonl already present, skipping extraction."
fi

# 6. Check API key
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
    echo ""
    echo "WARN: No ANTHROPIC_API_KEY or OPENAI_API_KEY detected in environment."
    echo "      Please set one before running experiments:"
    echo "      cp .env.template .env  # then edit .env"
fi

echo ""
echo "==> Setup complete!"
echo "    Next steps:"
echo "    1. Set your API key(s): cp .env.template .env"
echo "    2. Run a test:          bash scripts/examples/dci_basic_anthropic_example.sh"
