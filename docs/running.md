# Running Pi

## Python RPC Wrapper

Main entry point:

```bash
uv run hrci-run-pi-rpc
```

The runner assumes your built Pi checkout is at `./pi-mono` unless you override `--package-dir` and `--agent-dir`.

By default:

- Pi uses its own dynamically generated system prompt
- Run artifacts go under `outputs/runs/<timestamp>/`
- Non-empty `--output-dir` values are rejected unless you pass `--resume`

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
  "your question here"
```

Provider-specific runnable examples live under `scripts/examples/`:

- Anthropic: `hrci_basic_anthropic_example.sh`
- OpenAI: `hrci_basic_openai_example.sh`
- vLLM: `hrci_basic_vllm_example.sh`

### Resume a run

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

`--resume` reuses the artifact directory and validates that run settings match. True agent continuity also requires `--keep-session`.

### Override system prompt

```bash
uv run hrci-run-pi-rpc \
  --system-prompt-file "$PWD/prompts/system_prompt.txt" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your system prompt"
```

## Runtime Context-Management Levels

The forked `pi-mono` checkout supports runtime context-management profiles that change what Pi sends back into the model during long tool-heavy runs. This is the layer that matters for model behavior and ablations.

Quick decision rule:

- Use runtime levels for **experiments, ablations, and model-behavior comparisons** (for artifact-only levels see [artifacts.md](artifacts.md#optimize-levels))
- Use conversation artifact compaction (see [artifacts.md](artifacts.md#artifact-only-transcript-compaction)) only when you want smaller saved files

### Through `hrci-run-pi-rpc`

Use `--extra-arg` to forward the runtime profile into Pi:

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
