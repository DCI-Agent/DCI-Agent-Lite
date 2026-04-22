# Analysis Scripts

Analysis scripts live under `src/hrci/analysis`.

By default they read logs from:

```text
cc-analysis/eval_logs
```

and write figures to:

```text
outputs/figures/claude_code
```

## Quick commands

```bash
uv run python -m hrci.analysis.tool_analysis
uv run python -m hrci.analysis.bash_analysis
uv run python -m hrci.analysis.metrics_matrix
```

## Custom log location

```bash
HRCI_ANALYSIS_BASE=/absolute/path/to/log-repo \
uv run python -m hrci.analysis.tool_analysis
```

## Available modules

| Module | Description |
|--------|-------------|
| `tool_analysis` | Overall tool usage patterns |
| `bash_analysis` | Bash command analysis |
| `metrics_matrix` | Metrics matrix generation |
| `chain_analysis` | Chain-of-thought / reasoning chain analysis |
| `grep_tool_analysis` | ripgrep-specific tool analysis |
| `python_analysis` | Python tool execution analysis |
| `tool_call_distribution` | Tool call frequency distributions |
