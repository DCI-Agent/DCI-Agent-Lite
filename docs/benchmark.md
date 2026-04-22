# Benchmark Evaluation

## BrowseComp-Plus 100-Question Eval

The fixed 100-question evaluator is `scripts/bcplus_eval/run_bcplus_eval_100.py`.

Provider-specific launchers:

```bash
# Anthropic
bash scripts/bcplus_eval/run_bcplus_eval_100_anthropic.sh

# OpenAI
bash scripts/bcplus_eval/run_bcplus_eval_100_openai.sh

# vLLM
bash scripts/bcplus_eval/run_bcplus_eval_100_vllm.sh
```

### Runtime-context-level evals

```bash
bash scripts/bcplus_eval/run_level0.sh   # level0
bash scripts/bcplus_eval/run_level1.sh   # level1
bash scripts/bcplus_eval/run_level3.sh   # level3
```

### Parameters

Common parameters used in the eval scripts:

| Parameter | Typical Value | Description |
|-----------|--------------|-------------|
| `--dataset` | `data/bcplus_sampled_100_qa.jsonl` | QA dataset |
| `--output-root` | `outputs/bcplus_eval_100/...` | Results directory |
| `--corpus-dir` | `corpus/bc_plus_docs` | Exported corpus |
| `--provider` | `anthropic` / `openai` / `vllm` | LLM provider |
| `--model` | `claude-sonnet-4-20250514` | Model identifier |
| `--tools` | `read,bash` | Enabled tools |
| `--max-turns` | `100` | Max conversation turns |
| `--max-concurrency` | `1` | Concurrent runs |
| `--runtime-context-level` | `level5` | Context management level |
| `--node-max-old-space-size-mb` | `8192` | Node heap size |
| `--limit` | `10` | Limit to first N questions (optional) |

## Benchmark Prompts

Sample BrowseComp-Plus prompts are in [`docs/pi_agent_benchmark.md`](pi_agent_benchmark.md).

For HRCI local runs, replace any original corpus placeholder path with:

```text
$REPO_ROOT/corpus/bc_plus_docs
```
