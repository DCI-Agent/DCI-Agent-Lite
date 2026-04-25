# Setup Guide

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and `npm`
- `rg` (ripgrep)

## One-Click Setup

### Unix / macOS

```bash
bash setup.sh
```

## Manual Setup

### 1. Clone HRCI

```bash
git clone <your-hrci-repo-url> HRCI
cd HRCI
```

### 2. Create the Python environment

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

brew install ripgrep   # macOS
# sudo apt-get install ripgrep            # Linux

uv sync
```

### 3. Get and build Pi locally

This repo does not vendor the full npm workspace. Keep a local Pi checkout at `./pi-mono`.

```bash
git clone https://github.com/jdf-prog/pi-mono.git pi-mono
cd pi-mono
git checkout codex/context-management-ablation
npm install
npm run build
cd ..
```

Verify the CLI exists:

```bash
node pi-mono/packages/coding-agent/dist/cli.js --version
```

### 4. Configure model access

The easiest way is to copy `.env.template` to `.env` and fill in your keys:

```bash
cp .env.template .env
# edit .env with your favorite editor
```

`setup.sh` automatically loads `.env` if it exists. For manual runs, source it first:

```bash
# Unix / macOS
export $(grep -v '^#' .env | xargs)
```

You can also set keys inline:

```bash
export ANTHROPIC_API_KEY=your_key_here
# or
export OPENAI_API_KEY=your_key_here
```

or use an existing local Pi auth directory:

```bash
export PI_CODING_AGENT_DIR=$PWD/pi-mono/.pi/agent
```

### 5. Optional: configure a local vLLM provider

`vLLM` is not a built-in provider slug. In `pi-mono`, add it as a custom OpenAI-compatible provider through `~/.pi/agent/models.json`:

```json
{
  "providers": {
    "vllm": {
      "baseUrl": "http://localhost:8000/v1",
      "api": "openai-completions",
      "apiKey": "VLLM_API_KEY",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [
        { "id": "Qwen/Qwen2.5-Coder-32B-Instruct" }
      ]
    }
  }
}
```

**Important:** vLLM must be started with tool-calling support enabled. The server requires `--enable-auto-tool-choice` and `--tool-call-parser`:

```bash
# For Qwen-based models (e.g., Qwen2.5-Coder)
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --enable-auto-tool-choice \
  --tool-call-parser hermes

# For Llama 3.x models
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json
```

If these flags are missing, Pi will fail with a `400 status code (no body)` error because the default `tool_choice: "auto"` is rejected.

If your local server ignores auth:

```bash
export VLLM_API_KEY=dummy
```

## Corpus Preparation

All corpora are downloaded from the [DCI-Agent/corpus](https://huggingface.co/datasets/DCI-Agent/corpus) HuggingFace dataset (gated — requires login).

### Automated (recommended)

`setup.sh` automatically downloads all subsets if `corpus/` does not exist.

To download manually:

```bash
uv run python scripts/download_corpus.py
```

To skip the BrowseComp-Plus export step:

```bash
uv run python scripts/download_corpus.py --skip-export
```

### Manual download

If you prefer to download individual subsets directly:

```bash
# Login first (one-time)
huggingface-cli login

# Download BrowseComp-Plus
uv run python -c "
from huggingface_hub import snapshot_download
snapshot_download('DCI-Agent/corpus', repo_type='dataset', local_dir='corpus', allow_patterns=['browsecomp_plus/*'], local_dir_use_symlinks=False)
"
```

### Export BrowseComp-Plus to domain-first docs

After downloading, export the BrowseComp-Plus parquet into domain-first text folders:

```bash
uv run hrci-export-bc-plus-docs --source-dir "$PWD/corpus/browsecomp_plus" --output-dir "$PWD/corpus/bc_plus_docs"
```

This creates `corpus/bc_plus_docs` where:

- first-level folder = URL domain
- file name = document title when available

### Available subsets

| Subset | Path after download | Used for |
|--------|---------------------|----------|
| `browsecomp_plus` | `corpus/browsecomp_plus/` | BrowseComp-Plus eval |
| `bright_biology` | `corpus/bright_biology/` | BRIGHT biology benchmark |
| `bright_earth_science` | `corpus/bright_earth_science/` | BRIGHT earth science benchmark |
| `bright_economics` | `corpus/bright_economics/` | BRIGHT economics benchmark |
| `bright_robotics` | `corpus/bright_robotics/` | BRIGHT robotics benchmark |
| `wiki` | `corpus/wiki/` | Wikipedia corpus for QA benchmarks |
