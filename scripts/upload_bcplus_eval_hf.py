"""
Upload bcplus_eval_100 outputs to HuggingFace as a dataset.

Each level becomes a split. Each row is one query's result.json,
plus the conversation messages from conversation.json.
"""

import json
import os
from pathlib import Path

from datasets import Dataset, DatasetDict
from huggingface_hub import HfApi

OUTPUT_DIR = Path("/lambda/nfs/demo/HRCI/outputs/bcplus_eval_100")
REPO_ID = "ZhuofengLi/bcplus-eval-100"

LEVELS = [
    "openai_level0",
    "openai_level1",
    "openai_level2",
    "openai_level3",
    "openai_level3_full",
    "openai_level4",
    "openai_level4_read_grep",
    "openai_level5",
]


def load_level(level_dir: Path, level_name: str) -> list[dict]:
    rows = []
    for query_dir in sorted(level_dir.iterdir()):
        if not query_dir.is_dir():
            continue

        result_file = query_dir / "result.json"
        conv_file = query_dir / "conversation.json"

        if not result_file.exists():
            print(f"  [skip] no result.json in {query_dir}")
            continue

        with open(result_file) as f:
            result = json.load(f)

        # Load conversation messages if available
        messages = None
        if conv_file.exists():
            with open(conv_file) as f:
                conv = json.load(f)
            messages = json.dumps(conv.get("messages", []), ensure_ascii=False)

        judge = result.get("judge_result", {}) or {}

        row = {
            "level": level_name,
            "query_id": result.get("query_id", ""),
            "question": result.get("question", ""),
            "gold_answer": result.get("gold_answer", ""),
            "predicted_answer": result.get("final_text", ""),
            "is_correct": result.get("is_correct"),
            "normalized_prediction": judge.get("normalized_prediction", ""),
            "judge_reason": judge.get("reason", ""),
            "provider": result.get("judge_result", {}) and None,  # from conv
            "model": None,
            "tools": None,
            "run_status": result.get("run_status", ""),
            "wall_time_seconds": result.get("wall_time_seconds"),
            "turn_count": result.get("turn_count"),
            "tool_call_count": (result.get("tool_metrics") or {}).get("call_count"),
            "tool_error_count": (result.get("tool_metrics") or {}).get("error_count"),
            "agent_input_tokens": (result.get("agent_usage") or {}).get("input_tokens"),
            "agent_output_tokens": (result.get("agent_usage") or {}).get("output_tokens"),
            "agent_cost_total": (result.get("agent_usage") or {}).get("cost_total"),
            "conversation_messages": messages,
        }

        # Pull provider/model/tools from conversation.json if available
        if conv_file.exists():
            with open(conv_file) as f:
                conv = json.load(f)
            row["provider"] = conv.get("provider")
            row["model"] = conv.get("model")
            row["tools"] = conv.get("tools")

        rows.append(row)

    return rows


def main():
    api = HfApi()
    who = api.whoami()
    print(f"Logged in as: {who['name']}")

    # Create repo if needed
    api.create_repo(repo_id=REPO_ID, repo_type="dataset", exist_ok=True)
    print(f"Dataset repo: {REPO_ID}")

    splits = {}
    for level in LEVELS:
        level_dir = OUTPUT_DIR / level
        if not level_dir.exists():
            print(f"[skip] {level} not found")
            continue
        split_name = level.replace("openai_", "")
        print(f"Loading {level} -> split '{split_name}' ...")
        rows = load_level(level_dir, split_name)
        print(f"  {len(rows)} rows")
        splits[split_name] = Dataset.from_list(rows)

    dataset_dict = DatasetDict(splits)
    print(f"\nDatasetDict: {dataset_dict}")

    print(f"\nPushing to {REPO_ID} ...")
    dataset_dict.push_to_hub(REPO_ID, private=False)
    print("Done!")


if __name__ == "__main__":
    main()
