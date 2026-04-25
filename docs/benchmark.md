# Benchmark Evaluation

## BrowseComp-Plus Eval

The evaluator is `scripts/bcplus_eval/run_bcplus_eval.py`.

Provider-specific launchers:

```bash
# Anthropic (default provider)
uv run python scripts/bcplus_eval/run_bcplus_eval.py

# OpenAI
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh

# OpenAI with custom runtime level
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level1
```

### Runtime-context-level evals

```bash
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level0   # level0
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level1   # level1
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level3   # level3

# Fixed level3 (non-parameterized)
bash scripts/bcplus_eval/run_L3.sh
```

### Parameters

Common parameters used in the eval scripts:

| Parameter | Typical Value | Description |
|-----------|--------------|-------------|
| `--dataset` | `data/bcplus_qa.jsonl` | QA dataset |
| `--output-root` | `outputs/bcplus_eval/...` | Results directory |
| `--corpus-dir` | `corpus/bc_plus_docs` | Exported corpus |
| `--provider` | `anthropic` / `openai` | LLM provider |
| `--model` | `claude-sonnet-4-20250514` | Model identifier |
| `--tools` | `read,bash` | Enabled tools |
| `--max-turns` | `100` | Max conversation turns |
| `--max-concurrency` | `1` | Concurrent runs |
| `--runtime-context-level` | `level3` | Context management level |
| `--node-max-old-space-size-mb` | `8192` | Node heap size |
| `--limit` | `10` | Limit to first N questions (optional) |

## Benchmark Prompts

Sample BrowseComp-Plus prompts are in [`docs/pi_agent_benchmark.md`](pi_agent_benchmark.md).

For DCI local runs, replace any original corpus placeholder path with:

```text
$REPO_ROOT/corpus/bc_plus_docs
```
