# HRCI

HRCI is the standalone experiment repo for:

- BrowseComp-Plus style corpus search with `pi`
- corpus reshaping/export helpers
- local analysis scripts for Pi / Claude Code evaluation logs

This repo intentionally keeps large or local-only assets out of git. The tracked code that used to live under ignored folders has been moved into [`src/hrci`](/Users/dongfuj/Workspace/HRCI/src/hrci) and [`docs`](/Users/dongfuj/Workspace/HRCI/docs).

## Layout

```text
src/hrci/
  benchmark/
    export_bc_plus_docs.py   # Export parquet corpus into domain-first txt folders
    pi_rpc_runner.py         # Python RPC runner for pi
  analysis/
    *.py                     # Figure / log analysis scripts
docs/
  pi_agent_benchmark.md      # Sample BrowseComp-Plus prompts
```

Local-only directories that are still expected during experiments:

- `long-horizon-pi/`: local checkout of the Pi monorepo, built with npm
- `corpus/`: local corpus parquet shards and exported docs
- `cc-analysis/`: optional local log storage such as `cc-analysis/eval_logs`
- `*.log`: run logs

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- `npm`
- `rg` (ripgrep)

## 1. Clone HRCI

```bash
git clone <your-hrci-repo-url> HRCI
cd HRCI
```

## 2. Create the Python environment

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## 3. Get and build Pi locally

This repo does not vendor the entire npm workspace. Instead, keep a local checkout at `./long-horizon-pi` and build it there.

```bash
git clone https://github.com/badlogic/pi-mono.git long-horizon-pi
cd long-horizon-pi
npm install
npm run build
cd ..
```

Verify the CLI exists:

```bash
node long-horizon-pi/packages/coding-agent/dist/cli.js --version
```

## 4. Configure model access

Choose one of these:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

or, if you already use a local Pi auth directory:

```bash
export PI_CODING_AGENT_DIR=$PWD/long-horizon-pi/.pi/agent
```

If your key normally lives in `~/.bashrc`, you can also do:

```bash
source ~/.bashrc
```

## 5. Place the BrowseComp-Plus parquet corpus locally

Expected input location:

```text
corpus/bc-plus-corpus/data/*.parquet
```

Create the directory if needed:

```bash
mkdir -p corpus/bc-plus-corpus/data
```

Then copy your parquet shards into that folder.

## 6. Export the corpus into domain-first docs

This creates the `bc plus docs` layout:

- first-level folder = URL domain
- file name = document title when available

```bash
uv run hrci-export-bc-plus-docs
```

Equivalent explicit form:

```bash
uv run python -m hrci.benchmark.export_bc_plus_docs \
  --source-dir "$PWD/corpus/bc-plus-corpus/data" \
  --output-dir "$PWD/corpus/bc plus docs"
```

## 7. Run a BrowseComp-Plus style question through Pi

The Python runner assumes your built Pi checkout is at `./long-horizon-pi`.

Example:

```bash
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --package-dir "$PWD/long-horizon-pi/packages/coding-agent" \
  --agent-dir "$PWD/long-horizon-pi/.pi/agent" \
  --cwd "$PWD/corpus/bc plus docs/thefourwallmag.wordpress.com" \
  --show-tools \
  "Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."
```

Sample benchmark prompts are in [docs/pi_agent_benchmark.md](/Users/dongfuj/Workspace/HRCI/docs/pi_agent_benchmark.md).

## 8. Run Pi directly from Node

If you want the raw CLI instead of the Python RPC wrapper:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
source ~/.bashrc
cd "$REPO_ROOT/corpus/bc plus docs/thefourwallmag.wordpress.com"

PI_CODING_AGENT_DIR="$REPO_ROOT/long-horizon-pi/.pi/agent" \
node "$REPO_ROOT/long-horizon-pi/packages/coding-agent/dist/cli.js" \
  --model claude-sonnet-4-20250514 \
  --thinking off \
  --tools read,bash \
  --max-turns 6 \
  --no-session \
  -p "$(cat <<'"'"'EOF'"'"'
Read the files in the current directory. Do not use web search. Use rg instead of grep when searching.
Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name?
Answer with just the first name and one supporting file path.
EOF
)"
```

## 9. Analyze local evaluation logs

The migrated analysis scripts now live under [`src/hrci/analysis`](/Users/dongfuj/Workspace/HRCI/src/hrci/analysis).

By default they look for logs under:

```text
cc-analysis/eval_logs
```

and write figures to:

```text
outputs/figures/claude_code
```

Example commands:

```bash
uv run python -m hrci.analysis.tool_analysis
uv run python -m hrci.analysis.bash_analysis
uv run python -m hrci.analysis.metrics_matrix
```

If your logs live somewhere else:

```bash
HRCI_ANALYSIS_BASE=/absolute/path/to/log-repo \
uv run python -m hrci.analysis.tool_analysis
```

## 10. Rebuild checklist

If you are starting from a clean machine, the shortest working sequence is:

```bash
git clone <your-hrci-repo-url> HRCI
cd HRCI
uv sync
git clone https://github.com/badlogic/pi-mono.git long-horizon-pi
cd long-horizon-pi
npm install
npm run build
cd ..
export ANTHROPIC_API_KEY=your_key_here
mkdir -p corpus/bc-plus-corpus/data
# copy parquet shards into corpus/bc-plus-corpus/data
uv run hrci-export-bc-plus-docs
uv run hrci-run-pi-rpc --provider anthropic --model claude-sonnet-4-20250514 --show-tools "your question here"
```
