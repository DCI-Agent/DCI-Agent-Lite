# Running Pi

## Python RPC Wrapper

Main entry point:

```bash
uv run dci-agent-lite
```

The runner assumes your built Pi checkout is at `./pi-mono` unless you override `--package-dir` and `--agent-dir`.

`dci-run-pi-rpc` remains available as a legacy alias.

By default:

- Pi uses its own dynamically generated system prompt
- Run artifacts go under `outputs/runs/<timestamp>/`
- Non-empty `--output-dir` values are rejected unless you pass `--resume`

### Basic example

```bash
uv run dci-agent-lite \
  --provider openai \
  --model gpt-5.4-nano \
  --package-dir "$PWD/pi-mono/packages/coding-agent" \
  --agent-dir "$PWD/pi-mono/.pi/agent" \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --extra-arg="--thinking low" \
  "your question here"
```

Provider-specific runnable examples live under `scripts/examples/`:

- Anthropic: `dci_basic_anthropic_example.sh`
- OpenAI: `dci_basic_openai_example.sh`
- Groq: `dci_basic_groq_example.sh` (see [groq.md](groq.md))
- vLLM: `dci_basic_vllm_example.sh`

### Interactive terminal

Use `--terminal` to launch Pi's interactive terminal UI through the same wrapper:

```bash
uv run dci-agent-lite --terminal \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "$PWD/corpus/wiki_corpus" \
  --tools read,bash \
  --extra-arg="--thinking high"
```

Optional positional text or `--question-file` is forwarded as the initial message. Terminal mode does not write RPC runner artifacts, so it cannot be combined with runner-only flags such as `--output-dir`, `--resume`, `--max-turns`, `--show-tools`, or `--eval-answer`.

### Resume a run

Resume by pointing directly at a run directory:

```bash
uv run dci-agent-lite \
  --resume "$PWD/outputs/runs/bonang-test" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6
```

Or resume the same directory named in `--output-dir`:

```bash
uv run dci-agent-lite \
  --output-dir "$PWD/outputs/runs/bonang-test" \
  --resume \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6
```

`--resume` reuses the artifact directory and validates that run settings match. True agent continuity also requires `--keep-session`.

### Override system prompt

```bash
uv run dci-agent-lite \
  --system-prompt-file "$(git rev-parse --show-toplevel)/prompts/system_prompt.txt" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your system prompt"
```

## Runtime Context-Management Levels

The forked `pi-mono` checkout supports runtime context-management profiles that change what Pi sends back into the model during long tool-heavy runs. This is the layer that matters for model behavior and ablations.

Quick decision rule:

- Use runtime levels for **experiments, ablations, and model-behavior comparisons** (for artifact-only levels see [artifacts.md](artifacts.md#optimize-levels))
- Use conversation artifact compaction (see [artifacts.md](artifacts.md#artifact-only-transcript-compaction)) only when you want smaller saved files

### Through `dci-agent-lite`

Use `--extra-arg` to forward the runtime profile into Pi:

```bash
# level0: current upstream runtime behavior
uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level0" \
  "your question here"

# level1: only truncate very large tool results
uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level1" \
  "your question here"

# level2: stricter truncation
uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level2" \
  "your question here"

# level3: truncation + micro-compaction
uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level3" \
  "your question here"

# legacy / level4: closest to the older pi runtime
uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level legacy" \
  "your question here"

# level5: most aggressive runtime profile
uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level5" \
  "your question here"
```

Runnable example for all levels: `scripts/examples/dci_runtime_context_example.sh`

```bash
bash scripts/examples/dci_runtime_context_example.sh level3
```

Recommended meanings:

| Level | Behavior |
|-------|----------|
| `level0` | Current upstream baseline |
| `level1` | Mild ablation, only clamp very large tool outputs |
| `level2` | Stronger truncation-only baseline |
| `level3` | Adds micro-compaction but avoids inline full compaction |
| `legacy` / `level4` | Best match to old runtime behavior |
| `level5` | Strongest runtime pressure relief |

What to inspect after a run: `latest_model_context.json` (most recent context actually prepared for the next model call).

### Directly with `pi` (Node)

```bash
node packages/coding-agent/dist/cli.js --context-management-level level0
node packages/coding-agent/dist/cli.js --context-management-level legacy
node packages/coding-agent/dist/cli.js --context-management-level level5
```

## Running Pi Directly From Node

If you want the raw CLI instead of the Python RPC wrapper:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT/corpus/bc_plus_docs/thefourwallmag.wordpress.com"

PI_CODING_AGENT_DIR="$REPO_ROOT/pi-mono/.pi/agent" \
node "$REPO_ROOT/pi-mono/packages/coding-agent/dist/cli.js" \
  --model claude-sonnet-4-20250514 \
  --thinking off \
  --tools read,bash \
  --max-turns 6 \
  --no-session \
  -p "your question here"
```

Direct examples in `scripts/examples/`:

- Anthropic: `pi_direct_anthropic_example.sh`
- OpenAI: `pi_direct_openai_example.sh`
- vLLM: `pi_direct_vllm_example.sh`
