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

### 1. Clone DCI

```bash
git clone <your-dci-repo-url> DCI
cd DCI
```

### 2. Create the Python environment

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

brew install ripgrep   # macOS
# sudo apt-get install ripgrep            # Linux

uv sync
```

### 3. Get and build customized Pi locally

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
```

If these flags are missing, Pi will fail with a `400 status code (no body)` error because the default `tool_choice: "auto"` is rejected.

If your local server ignores auth:

```bash
export VLLM_API_KEY=dummy
```

### 6. Optional: Groq

Groq is configured like vLLM: add an OpenAI-compatible provider entry to Pi `models.json`, then pass `--provider groq`. See [groq.md](groq.md).

## Data Preparation

All benchmark datasets are downloaded from the [DCI-Agent/dci-bench](https://huggingface.co/datasets/DCI-Agent/dci-bench) HuggingFace dataset.

### Automated (recommended)

`setup.sh` automatically downloads and preprocesses benchmark data into `data/dci-bench/` if it does not exist, then extracts `data/bcplus_qa.jsonl` if it is missing.

### Manual

To prepare the benchmark data by hand, first download the `DCI-Agent/dci-bench` dataset into `data/dci-bench/`:

```bash
uv run python scripts/download_dci_bench.py
```

Then extract the BrowseComp-Plus parquet files under `data/dci-bench/data/browsecomp-plus/` into the `data/bcplus_qa.jsonl` file used by the eval scripts:

```bash
uv run python scripts/bcplus_eval/extract_bcplus_qa.py
```

This creates `data/bcplus_qa.jsonl` with `query_id`, `query`, and `answer` fields for BrowseComp-Plus evaluation.

## Corpus Preparation

All corpus subsets are downloaded from the [DCI-Agent/corpus](https://huggingface.co/datasets/DCI-Agent/corpus) HuggingFace dataset. The default workflow also exports BrowseComp-Plus into document-style folders for local retrieval.

### Automated (recommended)

`setup.sh` automatically downloads and processes the corpus bundle if `corpus/browsecomp_plus` does not exist.

### Manual

To prepare the corpus by hand, run the downloader below. It fetches all supported subsets into `corpus/` and exports BrowseComp-Plus into `corpus/bc_plus_docs/`:

```bash
uv run python scripts/download_corpus.py
```

If you only want a specific subset, log in to HuggingFace and download it directly:

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

If you downloaded BrowseComp-Plus separately, export the parquet files into domain-first text folders with:

```bash
uv run dci-export-bc-plus-docs --source-dir "$PWD/corpus/browsecomp_plus" --output-dir "$PWD/corpus/bc_plus_docs"
```

This creates `corpus/bc_plus_docs` where:

- first-level folder = URL domain
- file name = document title when available

### Benchmark and Corpus Overview

The benchmark scripts use the following dataset and retrieval-corpus pairs. `Avg. len.` is the mean document length measured in whitespace-split words.

| Retrieval corpus | Used by | # Docs | Avg. len. (words) | Dataset path(s) | Corpus path |
|------------------|---------|--------|-------------------|-----------------|-------------|
| BrowseComp-Plus | BrowseComp-Plus | 100,195 | 5,179 | `data/bcplus_qa.jsonl` (generated from `data/dci-bench/data/browsecomp-plus/`) | `corpus/bc_plus_docs/` (exported from `corpus/browsecomp_plus/`) |
| BRIGHT-Biology | BRIGHT-Biology | 57,359 | 48 | `data/dci-bench/data/bright_biology/bright_biology.jsonl` | `corpus/bright_corpus/biology/` |
| BRIGHT-Earth Science | BRIGHT-Earth Science | 121,249 | 28 | `data/dci-bench/data/bright_earth_science/bright_earth_science.jsonl` | `corpus/bright_corpus/earth_science/` |
| BRIGHT-Economics | BRIGHT-Economics | 50,220 | 52 | `data/dci-bench/data/bright_economics/economics_full.jsonl` | `corpus/bright_corpus/economics/` |
| BRIGHT-Robotics | BRIGHT-Robotics | 61,961 | 25 | `data/dci-bench/data/bright_robotics/bright_robotics.jsonl` | `corpus/bright_corpus/robotics/` |
| Wikipedia-18 | NQ, TriviaQA, Bamboogle, HotpotQA, 2WikiMultiHopQA, MuSiQue | 21,015,324 | 100 | `data/dci-bench/data/{nq,triviaqa,bamboogle,hotpotqa,2wikimultihopqa,musique}/test.jsonl` | `corpus/wiki_corpus/` |
