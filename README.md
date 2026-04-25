<a name="readme-top"></a>

<h1 align="center">DCI</h1>

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

## Prerequisites

| Tool | Recommended version | Notes |
|------|-------------------|-------|
| **Node / npm** | Node >= 20, npm >= 10 | `setup.sh` auto-installs via nvm if Node < 20 |
| **Python** | >= 3.10 | managed by [uv](https://github.com/astral-sh/uv) |
| **Linux bash** | bash >= 5 (Ubuntu 20.04+) | `setup.sh` is the recommended entry point |

---

## 🌟 Key Features

- 🔍 **BrowseComp-Plus Corpus Search** — Export parquet shards into domain-first text folders for local agentic retrieval.
- 🤖 **Pi RPC Runner** — Python wrapper around the Pi CLI with real-time event logging, resume support, and artifact compaction.
- 🧪 **A/B Evaluation Scripts** — BrowseComp-Plus eval with provider-specific launchers (Anthropic, OpenAI).
- ⚙️ **Context Management Ablations** — Runtime levels (`level0`–`level5`) and artifact-only transcript compaction for controlled experiments.

---

## 📑 Table of Contents

- [⚙️ Setup](#setup)
- [⚡ Quick Start](#quick-start)
- [CLI Reference](docs/cli-reference.md)
- [🚀 Running Experiments](#running-experiments)
- [🎯 Benchmark Evaluation](#benchmark-evaluation)
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
<summary>Manual Steps</summary>

See [`docs/setup.md`](docs/setup.md) for detailed prerequisites, repo build instructions, API-key configuration, and vLLM provider setup.

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
#    Corpus: https://huggingface.co/datasets/DCI-Agent/corpus
uv run python scripts/download_corpus.py

#    Benchmark datasets: https://huggingface.co/datasets/DCI-Agent/dci-bench
uv run python scripts/download_dci_bench.py
```

</details>

### Configuration

Copy the template to `.env`, then fill in the variables you need. To get DCI running, set at least one of `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`:

```bash
cp .env.template .env
```

Common variables:

- `OPENAI_API_KEY` for OpenAI model runs and benchmark judging by default.
- `ANTHROPIC_API_KEY` for Anthropic model runs.

<a name="quick-start"></a>
## ⚡ Quick Start

**Prerequisites**: Install dependencies and configure an OpenAI API key (see [Setup](#setup)).

The example below illustrates DCI-Agent-Lite in action: the deep research agent searches the corpus, inspects relevant documents, and produces evidence-grounded answers entirely within the given wikipedia corpus.

1. **Open the DCI-Agent-Lite TUI**:

```bash
# load keys from .env if not already in environment
set -a; source .env 2>/dev/null; set +a

uv run dci-agent-lite --terminal \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "corpus/wiki_corpus" \
  --extra-arg="--thinking high"
```

2. **Run your first task**. In the TUI, type:

```text
Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?
```

3. (Optional) **Run Programmatically from the CLI**. Remove the `--terminal` flag and pass your task as the final argument:

```bash
set -a; source .env 2>/dev/null; set +a

uv run dci-agent-lite \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "corpus/wiki_corpus" \
  --extra-arg="--thinking high" \
  "Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?"
```

Programmatic runs save artifacts under `outputs/runs/<timestamp>/`. The final answer is in `final.txt`, the original question is in `question.txt`, and the full trajectory is in `conversation_full.json`. To choose a specific location, pass `--output-dir path/to/run`. 

More runnable examples for OpenAI, Anthropic and vLLM are available in [`scripts/examples/`](scripts/examples/) as `dci_basic_*.sh`. See the [setup guide](docs/setup.md#5-optional-configure-a-local-vllm-provider) for vLLM configuration.


## 🚀 Context Management Strategies

DCI-Agent-Lite includes a lightweight runtime context-management layer for long-horizon deep research runs.

It uses three simple strategies:

- **Truncation** shortens large tool results in each turn.
- **Compaction** keeps recent turns and replaces older tool results with placeholders.
- **Summarization** summarizes older history when the context gets crowded.

The runtime levels move from no context management to more aggressive compression:

| Level | Behavior |
|-------|----------|
| `level0` | No context management. |
| `level1` | Light truncation. |
| `level2` | Stronger truncation. |
| `level3` | Truncation and compaction. |
| `level4` | Truncation, compaction, and summarization. |

Pass a level through Pi with `--extra-arg`:

```bash
set -a; source .env 2>/dev/null; set +a

uv run dci-agent-lite \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "corpus/wiki_corpus" \
  --extra-arg="--thinking high" \
  --extra-arg="--context-management-level level4" \
  "Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?"
```


<a name="running-experiments"></a>
## 🎯 Benchmark DCI-Agent-Lite 

We benchmark DCI-Agent-Lite on the following benchmark suites using OpenAI `gpt-5.4-nano` with `--thinking high`, context management set to `level3`, and a maximum turn budget of 300.

| Data | Data Size | Retrieval Corpus | Corpus Size | Avg. Corpus Len. (words) | Corpus Path |
|------|-----------|------------------|-------------|--------------------------|-------------|
| BrowseComp-Plus | 830 | BrowseComp-Plus | 100,195 docs | 5,179 | `corpus/bc_plus_docs/` |
| BRIGHT-Biology | 103 | BRIGHT-Biology | 57,359 docs | 48 | `corpus/bright_corpus/biology/` |
| BRIGHT-Earth Science | 116 | BRIGHT-Earth Science | 121,249 docs | 28 | `corpus/bright_corpus/earth_science/` |
| BRIGHT-Economics | 103 | BRIGHT-Economics | 50,220 docs | 52 | `corpus/bright_corpus/economics/` |
| BRIGHT-Robotics | 101 | BRIGHT-Robotics | 61,961 docs | 25 | `corpus/bright_corpus/robotics/` |
| NQ, TriviaQA, Bamboogle, HotpotQA, 2WikiMultiHopQA, MuSiQue | 50 each / 300 total | Wikipedia-18 | 21,015,324 docs | 100 | `corpus/wiki_corpus/` |


### Agentic Search (BrowseComp-Plus)

```bash
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh
```

### Knowledge-Intensive QA

```bash
bash scripts/qa/run_hotpotqa_dev_sample50.sh
bash scripts/qa/run_musique_dev_sample50.sh
bash scripts/qa/run_nq_test_sample50.sh
bash scripts/qa/run_triviaqa_test_sample50.sh
bash scripts/qa/run_2wikimultihopqa_dev_sample50.sh
bash scripts/qa/run_bamboogle_test_sample50.sh
```

### IR Ranking

```bash
# BRIGHT
bash scripts/bright/run_bio.sh
bash scripts/bright/run_earth_science.sh
bash scripts/bright/run_economics.sh
bash scripts/bright/run_robotics.sh
```

<a name="acknowledgements"></a>
## 🙏 Acknowledgements

<!-- TODO: fill in acknowledgements -->

---

<a name="citation"></a>
## 📚 Citation

```bibtex
@misc{dci2025,
  title = {DCI: High-Resolution Corpus Interaction},
  author = {Placeholder},
  year = {2025}
}
```

<p align="right"><a href="#readme-top">↑ Back to Top ↑</a></p>
