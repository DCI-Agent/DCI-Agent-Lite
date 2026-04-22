<a name="readme-top"></a>

<h1 align="center">HRCI</h1>

<p align="center">
  <b>High-Resolution Corpus Interaction</b> — BrowseComp-Plus local corpus search, reshaping, and evaluation for Pi and Claude Code.
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python" alt="Python 3.10+"></a>
  <a href="#"><img src="https://img.shields.io/badge/Node-20%2B-green.svg?logo=nodedotjs" alt="Node 20+"></a>
  <a href="#"><img src="https://img.shields.io/badge/UV-Required-purple.svg?logo=astral" alt="UV Required"></a>
  <a href="docs/setup.md"><img src="https://img.shields.io/badge/Docs-Setup-orange.svg?logo=readthedocs" alt="Docs"></a>
</p>

---

## 🌟 Key Features

- 🔍 **BrowseComp-Plus Corpus Search** — Export parquet shards into domain-first text folders for local agentic retrieval.
- 🤖 **Pi RPC Runner** — Python wrapper around the Pi CLI with real-time event logging, resume support, and artifact compaction.
- 🧪 **A/B Evaluation Scripts** — Fixed 100-question BCPlus eval with provider-specific launchers (Anthropic, OpenAI, vLLM).
- 📊 **Analysis Toolkit** — Log parsers and figure generators for tool usage, bash commands, and metrics matrices.
- ⚙️ **Context Management Ablations** — Runtime levels (`level0`–`level5`) and artifact-only transcript compaction for controlled experiments.

---

## 📑 Table of Contents

- [⚙️ Setup](#setup)
- [⚡ Quick Start](#quick-start)
- [🚀 Running Experiments](#running-experiments)
- [🎯 Benchmark Evaluation](#benchmark-evaluation)
- [📊 Analysis](#analysis)
- [🏗️ Repository Layout](#repository-layout)
- [🙏 Acknowledgements](#acknowledgements)
- [📚 Citation](#citation)

---

<a name="setup"></a>
## ⚙️ Setup

### One-Click Install

**Unix / macOS**

```bash
bash setup.sh
```

<details>
<summary>Windows PowerShell (click to expand)</summary>

```powershell
.\setup.ps1
```

</details>

### Manual Steps

See [`docs/setup.md`](docs/setup.md) for detailed prerequisites, Pi monorepo build instructions, API-key configuration, and vLLM provider setup.

Quick manual path:

```bash
# 1. Install uv + ripgrep, then sync Python deps
uv sync

# 2. Clone and build Pi
git clone https://github.com/jdf-prog/pi-mono.git pi-mono
cd pi-mono && git checkout codex/context-management-ablation && npm install && npm run build && cd ..

# 3. Configure API keys (copy template, edit .env, auto-loaded by setup.sh)
cp .env.template .env
# edit .env, then re-run setup.sh or source it manually

# 4. Download datasets (auto-downloaded by setup.sh, or run manually)
#    Datasets from https://huggingface.co/datasets/DCI-Agent/corpus (gated, login required)
uv run python scripts/download_corpus.py
```

---

<a name="quick-start"></a>
## ⚡ Quick Start

Run a single question through the Python RPC wrapper (scripts auto-load `.env` automatically; for manual CLI, source it first):

```bash
# Optional: load keys from .env if not already in environment
set -a; source .env 2>/dev/null; set +a

uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --package-dir "$PWD/pi-mono/packages/coding-agent" \
  --agent-dir "$PWD/pi-mono/.pi/agent" \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --show-tools \
  "your question here"
```

<details>
<summary>Windows PowerShell (click to expand)</summary>

```powershell
# Optional: load keys from .env if not already in environment
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#][^=]+)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") } }

uv run hrci-run-pi-rpc `
  --provider anthropic `
  --model claude-sonnet-4-20250514 `
  --package-dir "$PWD\pi-mono\packages\coding-agent" `
  --agent-dir "$PWD\pi-mono\.pi\agent" `
  --cwd "$PWD\corpus\bc_plus_docs\thefourwallmag.wordpress.com" `
  --tools read,bash `
  --max-turns 6 `
  --show-tools `
  "your question here"
```

</details>

**Runnable examples** ( Anthropic / OpenAI / vLLM ):

```bash
bash scripts/examples/hrci_basic_anthropic_example.sh
bash scripts/examples/hrci_basic_openai_example.sh
bash scripts/examples/hrci_basic_vllm_example.sh
```

<details>
<summary>PowerShell examples (click to expand)</summary>

```powershell
.\scripts\examples\ps\hrci_basic_anthropic_example.ps1
.\scripts\examples\ps\hrci_basic_openai_example.ps1
.\scripts\examples\ps\hrci_basic_vllm_example.ps1
```

</details>

---

<a name="running-experiments"></a>
## 🚀 Running Experiments

### RPC wrapper (recommended)

| Task | Command | Docs |
|------|---------|------|
| Basic run | `uv run hrci-run-pi-rpc --provider anthropic --model ... "question"` | [`docs/running.md`](docs/running.md) |
| Resume run | `uv run hrci-run-pi-rpc --resume ...` | [`docs/running.md`](docs/running.md/) |
| Override system prompt | `uv run hrci-run-pi-rpc --system-prompt-file prompts/system_prompt.txt ...` | [`docs/running.md`](docs/running.md) |
| Runtime context ablation | `--extra-arg="--context-management-level level5"` | [`docs/running.md`](docs/running.md) |
| Transcript compaction | `--conversation-clear-tool-results --conversation-externalize-tool-results` | [`docs/artifacts.md`](docs/artifacts.md) |

### Direct Pi (Node CLI)

```bash
PI_CODING_AGENT_DIR="$PWD/pi-mono/.pi/agent" \
node "$PWD/pi-mono/packages/coding-agent/dist/cli.js" \
  --model claude-sonnet-4-20250514 \
  --tools read,bash \
  --max-turns 6 \
  -p "your question here"
```

<details>
<summary>Windows PowerShell (click to expand)</summary>

```powershell
$env:PI_CODING_AGENT_DIR = "$PWD\pi-mono\.pi\agent"
node "$PWD\pi-mono\packages\coding-agent\dist\cli.js" `
  --model claude-sonnet-4-20250514 `
  --tools read,bash `
  --max-turns 6 `
  -p "your question here"
```

</details>

Direct examples: `scripts/examples/pi_direct_*`

---

<a name="benchmark-evaluation"></a>
## 🎯 Benchmark Evaluation

Run the fixed 100-question BCPlus evaluator:

```bash
# Anthropic
bash scripts/bcplus_eval/run_bcplus_eval_100_anthropic.sh

# OpenAI
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh

# vLLM
bash scripts/bcplus_eval/run_bcplus_eval_100_vllm.sh
```

Runtime-context-level variants: `scripts/bcplus_eval/run_level{0,1,3}.sh`

See [`docs/benchmark.md`](docs/benchmark.md) for parameters and prompt references.

---

<a name="analysis"></a>
## 📊 Analysis

```bash
# Tool usage patterns
uv run python -m hrci.analysis.tool_analysis

# Bash command analysis
uv run python -m hrci.analysis.bash_analysis

# Metrics matrix
uv run python -m hrci.analysis.metrics_matrix
```

See [`docs/analysis.md`](docs/analysis.md) for all modules and custom log paths.

---

<a name="repository-layout"></a>
## 📁 Repository Layout

```text
HRCI/
|-- src/hrci/
|   |-- benchmark/
|   |   |-- export_bc_plus_docs.py   # Parquet → domain-first txt folders
|   |   |-- pi_rpc_runner.py         # Python RPC runner with event logging
|   |   `-- pi_system_prompt.py      # Print Pi's default system prompt
|   `-- analysis/
|       `-- *.py                     # Figure and log analysis scripts
|-- docs/
|   |-- setup.md                     # Detailed installation guide
|   |-- running.md                   # Running Pi (RPC & direct)
|   |-- artifacts.md                 # Run artifacts & transcript compaction
|   |-- analysis.md                  # Analysis scripts reference
|   |-- benchmark.md                 # Benchmark evaluation guide
|   `-- pi_agent_benchmark.md        # Sample BrowseComp-Plus prompts
|-- scripts/
|   |-- examples/                    # Provider-specific runnable examples (bash)
|   |-- examples/ps/                 # PowerShell examples
|   |-- bcplus_eval/                 # 100-question eval launchers
|   |-- beir/                        # BEIR benchmark scripts
|   |-- bright/                      # BRIGHT benchmark scripts
|   `-- qa/                          # QA benchmark scripts
|-- data/
|   `-- bcplus_sampled_100_qa.jsonl
|-- prompts/
|   `-- system_prompt.txt
|-- setup.sh                         # One-click setup (Unix/macOS)
|-- setup.ps1                        # One-click setup (Windows)
|-- pyproject.toml
`-- uv.lock
```

**Local-only directories** (not tracked):

- `pi-mono/` — Pi monorepo checkout
- `corpus/` — parquet shards and exported `bc_plus_docs`
- `cc-analysis/` — optional evaluation logs
- `outputs/` — run artifacts and generated figures

---

<a name="acknowledgements"></a>
## 🙏 Acknowledgements

<!-- TODO: fill in acknowledgements -->

---

<a name="citation"></a>
## 📚 Citation

```bibtex
@misc{hrci2025,
  title = {HRCI: High-Resolution Corpus Interaction},
  author = {Placeholder},
  year = {2025}
}
```

<p align="right"><a href="#readme-top">↑ Back to Top ↑</a></p>
