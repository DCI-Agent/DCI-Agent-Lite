# DCI-Agent-Lite CLI Reference

```bash
dci-agent-lite [options] [message...]
uv run dci-agent-lite [options] [message...]
```

`dci-agent-lite` is the lightweight DCI wrapper around Pi. It can launch Pi's interactive TUI or run a question programmatically and save artifacts under `outputs/runs/<timestamp>/`.

If no positional message is provided, the runner reads from `--question-file` or stdin.

```bash
cat question.txt | uv run dci-agent-lite --provider openai --model gpt-5.4-nano
```

## Modes

| Option | Description |
|--------|-------------|
| `(default)` | Programmatic RPC runner. Runs the task, prints the final answer, and writes artifacts. |
| `--terminal` | Launch Pi's interactive terminal UI through DCI-Agent-Lite. |

Terminal mode forwards positional text or `--question-file` as the initial message, but it does not write runner artifacts. It cannot be combined with runner-only options such as `--output-dir`, `--resume`, `--max-turns`, `--show-tools`, conversation compaction flags, or evaluation flags.

## Input Options

| Option | Description |
|--------|-------------|
| `[message...]` | Question or task text. Multiple words are joined into one message. |
| `--question-file <path>` | Read the question from a UTF-8 text file. |
| stdin | Used as the question when no positional message or `--question-file` is provided. |

## Model Options

| Option | Description |
|--------|-------------|
| `--provider <name>` | Provider passed to Pi, such as `openai`, `anthropic`, or a custom provider like `vllm`. |
| `--model <id>` | Model ID or pattern passed to Pi. |
| `--extra-arg <arg>` | Extra CLI argument forwarded to Pi. Repeatable. Useful for Pi options not modeled directly by DCI-Agent-Lite, such as `--thinking high` or `--context-management-level level3`. |

Examples:

```bash
uv run dci-agent-lite \
  --provider openai \
  --model gpt-5.4-nano \
  --extra-arg="--thinking high" \
  "your question"

uv run dci-agent-lite \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --extra-arg="--context-management-level level3" \
  "your question"
```

## Runtime Options

| Option | Description |
|--------|-------------|
| `--cwd <dir>` | Working directory for the agent subprocess. Defaults to the DCI repo root. |
| `--tools <list>` | Comma-separated built-in tools to enable. Default: `read,bash`. |
| `--max-turns <n>` | Client-side cap on agent turns. The runner aborts before turn `n + 1` starts. |
| `--keep-session` | Persist Pi session history. By default, programmatic runs use ephemeral `--no-session` behavior. |
| `--show-tools` | Print tool start/end events to stderr while the agent runs. |

## Pi Checkout Options

| Option | Description |
|--------|-------------|
| `--package-dir <dir>` | Path to the built `packages/coding-agent` directory inside a Pi checkout. Defaults to `pi-mono/packages/coding-agent`. |
| `--agent-dir <dir>` | Pi agent config directory. Defaults to `pi-mono/.pi/agent`. |

Most users can leave these at their defaults after running setup.

## Prompt Options

| Option | Description |
|--------|-------------|
| `--system-prompt-file <path>` | Replace Pi's default system prompt with the contents of a file. Relative paths are resolved against the current directory first, then the DCI repo root. |
| `--append-system-prompt-file <path>` | Append an additional system prompt file. Relative paths use the same resolution rule. |

## Artifact Options

| Option | Description |
|--------|-------------|
| `--output-dir <dir>` | Directory for run artifacts. Default: `outputs/runs/<timestamp>/`. Non-empty directories require `--resume`. |
| `--conversation-clear-tool-results` | Compact `conversation.json` by replacing older tool results with placeholders. |
| `--conversation-clear-tool-results-keep-last <n>` | Keep the last `n` tool result messages inline when clearing tool results. Default: `3`. |
| `--conversation-externalize-tool-results` | Write full tool results to `tool_results/*.json` and keep pointers in `conversation.json`. |
| `--conversation-strip-thinking` | Remove assistant thinking blocks from `conversation.json`. |
| `--conversation-strip-usage` | Remove assistant usage metadata from `conversation.json`. |

Each programmatic run writes files such as:

```text
outputs/runs/<timestamp>/
  question.txt
  final.txt
  conversation_full.json
  conversation.json
  latest_model_context.json
  events.jsonl
  state.json
  stderr.txt
```

See [artifacts.md](artifacts.md) for artifact details.

## Resume Options

| Option | Description |
|--------|-------------|
| `--resume <dir>` | Resume from an existing output directory. |
| `--resume --output-dir <dir>` | Resume the directory provided by `--output-dir`. |

If the resume directory does not exist or is empty, DCI-Agent-Lite prints a warning and starts a new run there. Reusing the same artifact directory does not automatically preserve Pi's model session; use `--keep-session` when you want Pi session history to persist.

## Evaluation Options

| Option | Description |
|--------|-------------|
| `--eval-answer <text>` | Gold answer used to grade `final.txt` with an OpenAI judge. Writes `eval_result.json`. |
| `--eval-answer-file <path>` | UTF-8 file containing the gold answer. |
| `--eval-judge-model <id>` | OpenAI judge model. Default: `gpt-5.4-nano`. |
| `--eval-judge-api-key-env <name>` | Environment variable containing the OpenAI API key for judging. Default: `OPENAI_API_KEY`. |
| `--eval-judge-timeout-seconds <n>` | HTTP timeout for the judge call. Default: `120`. |
| `--eval-judge-input-price-per-1m <price>` | Judge input token price per 1M tokens. Default: `0.20`. |
| `--eval-judge-cached-input-price-per-1m <price>` | Judge cached-input token price per 1M tokens. Default: `0.02`. |
| `--eval-judge-output-price-per-1m <price>` | Judge output token price per 1M tokens. Default: `1.25`. |

## Help

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show CLI help generated from the current implementation. |

