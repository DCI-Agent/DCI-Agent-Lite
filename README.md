# HRCI

HRCI is a standalone experiment repo for:

- BrowseComp-Plus style local corpus search with Pi
- corpus reshaping and export helpers
- local analysis scripts for Pi and Claude Code evaluation logs

Large assets and local-only checkouts stay out of git. The tracked code lives under [`src/hrci`](/Users/dongfuj/Workspace/HRCI/src/hrci), with prompts and example benchmark questions kept in [`prompts`](/Users/dongfuj/Workspace/HRCI/prompts) and [`docs`](/Users/dongfuj/Workspace/HRCI/docs).

## Quickstart

If you want the shortest path from a clean machine to a working Pi run:

```bash
git clone <your-hrci-repo-url> HRCI
cd HRCI
curl -LsSf https://astral.sh/uv/install.sh | sh
brew install ripgrep
uv sync

git clone https://github.com/jdf-prog/pi-mono.git pi-mono
cd pi-mono
git checkout codex/context-management-ablation
npm install
npm run build
cd ..

export ANTHROPIC_API_KEY=your_key_here

mkdir -p corpus/
hf download --repo-type dataset --local-dir corpus/bc-plus-corpus Tevatron/browsecomp-plus-corpus

uv run hrci-export-bc-plus-docs

uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --show-tools \
  "your question here"
```

Provider-specific runnable examples also live in [`scripts/examples`](/Users/dongfuj/Workspace/HRCI/scripts/examples):

- Anthropic: [`hrci_basic_anthropic_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/hrci_basic_anthropic_example.sh)
- OpenAI: [`hrci_basic_openai_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/hrci_basic_openai_example.sh)
- vLLM: [`hrci_basic_vllm_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/hrci_basic_vllm_example.sh)

## Repository Layout

Tracked code:

```text
src/hrci/
  benchmark/
    export_bc_plus_docs.py   # Export parquet corpus into domain-first txt folders
    pi_rpc_runner.py         # Python RPC runner for Pi with realtime event logging
  analysis/
    *.py                     # Figure and log analysis scripts
docs/
  pi_agent_benchmark.md      # Sample BrowseComp-Plus prompts
prompts/
  system_prompt.txt          # Optional example system prompt override
```

Expected local-only directories during experiments:

- `pi-mono/`: local checkout of the Pi monorepo
- `corpus/`: parquet shards and exported `bc_plus_docs`
- `cc-analysis/`: optional evaluation logs such as `cc-analysis/eval_logs`
- `outputs/`: run artifacts and generated figures

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- `npm`
- `rg` (ripgrep)
  Install it from the official instructions: [ripgrep installation](https://github.com/burntsushi/ripgrep?tab=readme-ov-file#installation)

## Setup

### 1. Clone HRCI

```bash
git clone <your-hrci-repo-url> HRCI
cd HRCI
```

### 2. Create the Python environment

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
brew install ripgrep
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

Verify that the CLI exists:

```bash
node pi-mono/packages/coding-agent/dist/cli.js --version
```

### 4. Configure model access

Use either an API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

or for OpenAI:

```bash
export OPENAI_API_KEY=your_key_here
```

or an existing local Pi auth directory:

```bash
export PI_CODING_AGENT_DIR=$PWD/pi-mono/.pi/agent
```

If your shell config already exports these, you can load it first:

```bash
source ~/.bashrc
```

### 5. Optional: configure a local vLLM provider

`vLLM` is not a built-in provider slug like `anthropic` or `openai`. In `pi-mono`, it is typically added as a custom OpenAI-compatible provider through `~/.pi/agent/models.json`.

A minimal starting point is:

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
        {
          "id": "Qwen/Qwen2.5-Coder-32B-Instruct"
        }
      ]
    }
  }
}
```

If your local server ignores auth, any non-empty value works:

```bash
export VLLM_API_KEY=dummy
```

Background docs for this flow are in [`models.md`](/Users/dongfuj/Workspace/HRCI/pi-mono/packages/coding-agent/docs/models.md).

## Corpus Preparation

### 1. Place the BrowseComp-Plus parquet corpus locally

Expected input location:

```text
corpus/bc-plus-corpus/data/*.parquet
```

One way to populate it:

```bash
mkdir -p corpus/
hf download --repo-type dataset --local-dir corpus/bc-plus-corpus Tevatron/browsecomp-plus-corpus
```

### 2. Export the corpus into domain-first docs

This creates `corpus/bc_plus_docs`:

- first-level folder = URL domain
- file name = document title when available

Default command:

```bash
uv run hrci-export-bc-plus-docs
```

Equivalent explicit form:

```bash
uv run python -m hrci.benchmark.export_bc_plus_docs \
  --source-dir "$PWD/corpus/bc-plus-corpus/data" \
  --output-dir "$PWD/corpus/bc_plus_docs"
```

## Running Pi Through The Python RPC Wrapper

The main entry point is:

```bash
uv run hrci-run-pi-rpc
```

The runner assumes your built Pi checkout is at `./pi-mono` unless you override `--package-dir` and `--agent-dir`.

By default:

- Pi uses its own dynamically generated system prompt
- the runner writes run artifacts under `outputs/runs/<timestamp>/`
- non-empty `--output-dir` values are rejected unless you pass `--resume`

Runnable copies of the README examples live under [`scripts/examples`](/Users/dongfuj/Workspace/HRCI/scripts/examples).

### Run artifacts

Each run produces:

```text
outputs/runs/<timestamp>/
  events.jsonl
  state.json
  conversation_full.json
  conversation.json
  latest_model_context.json
  final.txt
  stderr.txt
  question.txt
```

Artifact roles:

- `events.jsonl`: raw RPC event stream, appended in real time
- `state.json`: low-level debug snapshot, rewritten after each event
- `conversation_full.json`: full normalized transcript without HRCI-side transcript compaction
- `conversation.json`: cleaner transcript view, optionally compacted by HRCI conversation features
- `latest_model_context.json`: only the most recent context snapshot actually prepared for the next model call
- `final.txt`: final assistant answer
- `stderr.txt`: Pi stderr capture
- `question.txt`: question text used for the run

If you pass `--system-prompt-file`, both `conversation_full.json` and `conversation.json` include a single `system` message built from that file and any appended system prompt file.

### Basic example

```bash
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --package-dir "$PWD/pi-mono/packages/coding-agent" \
  --agent-dir "$PWD/pi-mono/.pi/agent" \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --show-tools \
  "Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."
```

Provider-specific single-run examples:

- Anthropic: [`hrci_basic_anthropic_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/hrci_basic_anthropic_example.sh)
- OpenAI: [`hrci_basic_openai_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/hrci_basic_openai_example.sh)
- vLLM: [`hrci_basic_vllm_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/hrci_basic_vllm_example.sh)

Direct OpenAI example:

```bash
uv run hrci-run-pi-rpc \
  --provider openai \
  --model gpt-5.4 \
  --package-dir "$PWD/pi-mono/packages/coding-agent" \
  --agent-dir "$PWD/pi-mono/.pi/agent" \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --show-tools \
  "Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."
```

Direct vLLM example after configuring `~/.pi/agent/models.json`:

```bash
uv run hrci-run-pi-rpc \
  --provider vllm \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --package-dir "$PWD/pi-mono/packages/coding-agent" \
  --agent-dir "$PWD/pi-mono/.pi/agent" \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --show-tools \
  "Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."
```

Direct `pi` examples in [`scripts/examples`](/Users/dongfuj/Workspace/HRCI/scripts/examples):

- Anthropic: [`pi_direct_anthropic_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/pi_direct_anthropic_example.sh)
- OpenAI: [`pi_direct_openai_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/pi_direct_openai_example.sh)
- vLLM: [`pi_direct_vllm_example.sh`](/Users/dongfuj/Workspace/HRCI/scripts/examples/pi_direct_vllm_example.sh)

### Resume an existing run directory

Resume by pointing directly at a run directory:

```bash
uv run hrci-run-pi-rpc \
  --resume "$PWD/outputs/runs/bonang-test" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6
```

Or resume the same directory named in `--output-dir`:

```bash
uv run hrci-run-pi-rpc \
  --output-dir "$PWD/outputs/runs/bonang-test" \
  --resume \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6
```

`--resume` reuses the artifact directory and validates that the run settings match. True agent continuity also requires `--keep-session`; otherwise only the artifact directory is reused.

### Override Pi's system prompt

```bash
uv run hrci-run-pi-rpc \
  --system-prompt-file "$PWD/prompts/system_prompt.txt" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"
```

### Runtime context-management levels

The forked `pi-mono` checkout supports runtime context-management profiles that change what Pi actually sends back into the model during long tool-heavy runs.

This is the context-management layer that matters for model behavior and ablations.

This is separate from the `conversation.json` artifact compaction flags below:

- runtime context management: changes live model context
- conversation artifact compaction: only changes what HRCI writes to `conversation.json`

If your goal is to measure how context management changes agent behavior, use the runtime levels below and compare `latest_model_context.json`.

Quick decision rule:

- use runtime levels for experiments, ablations, and model-behavior comparisons
- use conversation artifact compaction only when you want smaller saved files

#### Directly with `pi`

From the `pi-mono/` checkout:

```bash
# current upstream behavior
node packages/coding-agent/dist/cli.js --context-management-level level0

# restore the older runtime behavior
node packages/coding-agent/dist/cli.js --context-management-level legacy

# strongest runtime profile
node packages/coding-agent/dist/cli.js --context-management-level level5
```

#### Through `hrci-run-pi-rpc`

Use `--extra-arg` to forward the runtime profile into Pi. A single quoted value can expand to multiple Pi CLI args:

```bash
# level0: current upstream runtime behavior
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level0" \
  "your question here"

# level1: only truncate very large tool results
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level1" \
  "your question here"

# level2: stricter truncation
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level2" \
  "your question here"

# level3: truncation + micro-compaction
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level3" \
  "your question here"

# legacy / level4: closest to the older pi runtime
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level legacy" \
  "your question here"

# level5: most aggressive runtime profile
uv run hrci-run-pi-rpc \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level5" \
  "your question here"
```

Recommended meanings:

- `level0`: current upstream baseline
- `level1`: mild ablation, only clamp very large tool outputs
- `level2`: stronger truncation-only baseline
- `level3`: adds micro-compaction but avoids inline full compaction
- `legacy` or `level4`: best match to the old runtime behavior
- `level5`: strongest runtime pressure relief

What to inspect after a run:

- `conversation_full.json`: full normalized transcript
- `conversation.json`: artifact-only compacted transcript view
- `latest_model_context.json`: most recent context actually prepared for the next model call

For runtime ablations, the most important artifact is `latest_model_context.json`.

### Fixed-set BCPlus eval scripts

The fixed 100-question evaluator lives in [`run_bcplus_eval_100.py`](/Users/dongfuj/Workspace/HRCI/scripts/bcplus_eval/run_bcplus_eval_100.py). Provider-specific launcher scripts are:

- Anthropic: [`run_bcplus_eval_100_anthropic.sh`](/Users/dongfuj/Workspace/HRCI/scripts/bcplus_eval/run_bcplus_eval_100_anthropic.sh)
- OpenAI: [`run_bcplus_eval_100_openai.sh`](/Users/dongfuj/Workspace/HRCI/scripts/bcplus_eval/run_bcplus_eval_100_openai.sh)
- vLLM: [`run_bcplus_eval_100_vllm.sh`](/Users/dongfuj/Workspace/HRCI/scripts/bcplus_eval/run_bcplus_eval_100_vllm.sh)

The compatibility wrapper [`run_bcplus_eval_100.sh`](/Users/dongfuj/Workspace/HRCI/scripts/bcplus_eval/run_bcplus_eval_100.sh) currently forwards to the Anthropic version.

### Inspect Pi's default generated system prompt

```bash
uv run hrci-print-pi-system-prompt \
  --package-dir "$PWD/pi-mono/packages/coding-agent" \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash
```

## Artifact-Only Transcript Compaction

The runner also supports Claude Code-inspired transcript compaction features for `conversation.json`. These are independent and all off by default.

Important: this section does not change Pi's runtime behavior.

It only changes how HRCI stores the processed transcript view on disk. In particular:

- it does not change what the model sees
- it does not change `conversation_full.json`
- it does not change `latest_model_context.json`

So if your question is "does context management affect performance or behavior?", this layer is usually not the one you want.

Use it only when you want:

- smaller artifacts
- easier-to-read saved transcripts
- separate archival/debug views where full tool output lives outside `conversation.json`

### Available features

- `--conversation-clear-tool-results`
  Replaces older `toolResult` payloads inside `conversation.json` with short placeholders.

- `--conversation-clear-tool-results-keep-last N`
  When clearing is enabled, keep the most recent `N` tool results inline. Default: `3`.

- `--conversation-externalize-tool-results`
  Saves each full `toolResult` to `tool_results/*.json` and keeps a pointer in `conversation.json`.

- `--conversation-strip-thinking`
  Removes assistant `thinking` blocks from `conversation.json`.

- `--conversation-strip-usage`
  Removes assistant token and cost metadata from `conversation.json`.

### Design intent

This split mirrors the most useful artifact-focused parts of Claude Code-style context management:

- tool-result clearing: shrink stale shell output in the main transcript
- tool-result externalization: preserve full data outside the main transcript
- thinking stripping: keep the transcript focused on visible conversation
- usage stripping: keep the transcript focused on semantics rather than cost accounting

### Optimize levels

Use these combinations when you want a simple “more compression” ladder for saved transcript files:

| Level | Goal | Recommended flags |
| --- | --- | --- |
| `level1` | Minimal compaction, safest for debugging | `--conversation-clear-tool-results --conversation-externalize-tool-results` |
| `level2` | Keep only the most recent tool result inline | `--conversation-clear-tool-results --conversation-clear-tool-results-keep-last 1 --conversation-externalize-tool-results` |
| `level3` | Aggressive tool-output compaction | `--conversation-clear-tool-results --conversation-clear-tool-results-keep-last 0 --conversation-externalize-tool-results` |
| `level4` | Aggressive tool compaction plus remove hidden reasoning | `--conversation-clear-tool-results --conversation-clear-tool-results-keep-last 0 --conversation-externalize-tool-results --conversation-strip-thinking` |
| `level5` | Maximum current compression | `--conversation-clear-tool-results --conversation-clear-tool-results-keep-last 0 --conversation-externalize-tool-results --conversation-strip-thinking --conversation-strip-usage` |

Practical guidance:

- `level1`: best starting point if you still want `conversation.json` to feel close to the original run
- `level2`: good default when tool output is the main source of bloat
- `level3`: best current option when shell output is flooding the transcript
- `level4`: use when you do not need hidden reasoning in the artifact
- `level5`: smallest current transcript; best for archival, dataset generation, or replay pipelines that only need visible content

If you do not specifically care about saved transcript size, you can ignore this whole section.

### Example commands by optimize level

```bash
# level1
uv run hrci-run-pi-rpc \
  --conversation-clear-tool-results \
  --conversation-externalize-tool-results \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"

# level2
uv run hrci-run-pi-rpc \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 1 \
  --conversation-externalize-tool-results \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"

# level3
uv run hrci-run-pi-rpc \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 0 \
  --conversation-externalize-tool-results \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"

# level4
uv run hrci-run-pi-rpc \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 0 \
  --conversation-externalize-tool-results \
  --conversation-strip-thinking \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"

# level5
uv run hrci-run-pi-rpc \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 0 \
  --conversation-externalize-tool-results \
  --conversation-strip-thinking \
  --conversation-strip-usage \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"
```

### Suggested defaults

If tool outputs are bloating `conversation.json`, start with `level1`.

If the transcript is still too large, move to `level3`.

If you want the leanest current artifact, use `level5`.

## Running Pi Directly From Node

If you want the raw CLI instead of the Python RPC wrapper:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
source ~/.bashrc
cd "$REPO_ROOT/corpus/bc_plus_docs/thefourwallmag.wordpress.com"

PI_CODING_AGENT_DIR="$REPO_ROOT/pi-mono/.pi/agent" \
node "$REPO_ROOT/pi-mono/packages/coding-agent/dist/cli.js" \
  --model claude-sonnet-4-20250514 \
  --thinking off \
  --tools read,bash \
  --max-turns 6 \
  --no-session \
  -p "$(cat <<'EOF'
Read the files in the current directory. Do not use web search. Use rg instead of grep when searching.
Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name?
Answer with just the first name and one supporting file path.
EOF
)"
```

## Analysis Scripts

The analysis scripts live under [`src/hrci/analysis`](/Users/dongfuj/Workspace/HRCI/src/hrci/analysis).

By default they read logs from:

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

To point analysis at a different log location:

```bash
HRCI_ANALYSIS_BASE=/absolute/path/to/log-repo \
uv run python -m hrci.analysis.tool_analysis
```

## Benchmark Prompt References

Sample BrowseComp-Plus prompts are in [pi_agent_benchmark.md](/Users/dongfuj/Workspace/HRCI/docs/pi_agent_benchmark.md).

For HRCI local runs, replace any original corpus placeholder path with:

```text
$REPO_ROOT/corpus/bc_plus_docs
```

or the absolute local equivalent:

```text
/Users/dongfuj/Workspace/HRCI/corpus/bc_plus_docs
```
