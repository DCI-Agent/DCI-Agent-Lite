# Groq provider (Pi)

Groq exposes an [OpenAI-compatible HTTP API](https://console.groq.com/docs/openai). DCI-Agent-Lite forwards `--provider` and `--model` to Pi unchanged, so you register Groq as a **custom Pi provider** (same pattern as [vLLM in setup.md](setup.md#5-optional-configure-a-local-vllm-provider)).

## 1. API key

Create a key in the Groq console and export it (or add to `.env`):

```bash
export GROQ_API_KEY=your_key_here
```

## 2. Pi `models.json`

Merge a `groq` entry into the `providers` object Pi loads (for example `pi-mono/.pi/agent/models.json` or `~/.pi/agent/models.json`, depending on your layout). Adjust `models` to match [models Groq currently serves](https://console.groq.com/docs/models); the example below uses `llama-3.3-70b-versatile`:

```json
{
  "providers": {
    "groq": {
      "baseUrl": "https://api.groq.com/openai/v1",
      "api": "openai-completions",
      "apiKey": "GROQ_API_KEY",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [{ "id": "llama-3.3-70b-versatile" }]
    }
  }
}
```

Rebuild or restart Pi-related tooling if your workflow caches config.

## 3. Run DCI-Agent-Lite

```bash
uv run dci-agent-lite \
  --provider groq \
  --model llama-3.3-70b-versatile \
  --cwd "$PWD/corpus/wiki_corpus" \
  "your question"
```

Or use the runnable example:

```bash
bash scripts/examples/dci_basic_groq_example.sh
```

BrowseComp-Plus batch eval (mirrors the OpenAI launcher):

```bash
bash scripts/bcplus_eval/run_bcplus_eval_groq.sh
bash scripts/bcplus_eval/run_bcplus_eval_groq.sh level1
```

## 4. Benchmark judging

BrowseComp-Plus grading still uses the **OpenAI** judge in this repo (`OPENAI_API_KEY`), independent of which provider runs the agent.
