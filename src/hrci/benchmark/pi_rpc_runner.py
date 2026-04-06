#!/usr/bin/env python3
"""
Run one BrowseComp-style prompt against pi in RPC mode.

This variant is optimized for experiments:
- stream assistant text live
- optionally print tool boundaries to stderr
- append every raw RPC event to `events.jsonl`
- rewrite `state.json` after each event for real-time inspection
- rewrite `conversation.json` after each event for a cleaner transcript
- save the final answer to `final.txt`
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_PI_REPO = REPO_ROOT / "pi-mono"
DEFAULT_PACKAGE_DIR = DEFAULT_PI_REPO / "packages" / "coding-agent"
DEFAULT_AGENT_DIR = DEFAULT_PI_REPO / ".pi" / "agent"
DEFAULT_RUNS_DIR = REPO_ROOT / "outputs" / "runs"
DEFAULT_EVAL_JUDGE_MODEL = "gpt-5.4-nano"
DEFAULT_EVAL_INPUT_PRICE_PER_1M = 0.20
DEFAULT_EVAL_CACHED_INPUT_PRICE_PER_1M = 0.02
DEFAULT_EVAL_OUTPUT_PRICE_PER_1M = 1.25


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_text_if_exists(path: Optional[Path]) -> Optional[str]:
    if not path:
        return None
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def is_directory_empty(path: Path) -> bool:
    if not path.exists():
        return True
    return not any(path.iterdir())


def build_default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DEFAULT_RUNS_DIR / stamp


def clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def sanitize_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "item"


def count_text_stats(text: str) -> Dict[str, int]:
    return {
        "chars": len(text),
        "lines": text.count("\n") + (1 if text else 0),
    }


def expand_extra_args(values: List[str]) -> List[str]:
    expanded: List[str] = []
    for value in values:
        parts = shlex.split(value)
        if parts:
            expanded.extend(parts)
    return expanded


def load_eval_answer(
    *,
    eval_answer: Optional[str],
    eval_answer_file: Optional[Path],
) -> Optional[str]:
    if eval_answer_file:
        return eval_answer_file.read_text(encoding="utf-8").strip()
    if eval_answer:
        return eval_answer.strip()
    return None


def estimate_judge_cost(
    usage: Dict[str, Any],
    *,
    input_price_per_1m: float,
    cached_input_price_per_1m: float,
    output_price_per_1m: float,
) -> Dict[str, float]:
    input_tokens = float(usage.get("input_tokens", 0) or 0)
    output_tokens = float(usage.get("output_tokens", 0) or 0)
    input_details = usage.get("input_tokens_details") or {}
    cached_input_tokens = float(input_details.get("cached_tokens", 0) or 0)
    non_cached_input_tokens = max(0.0, input_tokens - cached_input_tokens)
    input_cost = (non_cached_input_tokens / 1_000_000.0) * input_price_per_1m
    cached_input_cost = (cached_input_tokens / 1_000_000.0) * cached_input_price_per_1m
    output_cost = (output_tokens / 1_000_000.0) * output_price_per_1m
    return {
        "input_cost": input_cost,
        "cached_input_cost": cached_input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + cached_input_cost + output_cost,
    }


def extract_openai_response_text(response_payload: Dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts: List[str] = []
    for item in response_payload.get("output", []):
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text_value = block.get("text")
            if isinstance(text_value, str):
                texts.append(text_value)
            elif isinstance(text_value, dict) and isinstance(text_value.get("value"), str):
                texts.append(text_value["value"])
    return "\n".join(part.strip() for part in texts if part and part.strip()).strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Judge response did not contain a JSON object")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Judge response JSON was not an object")
    return payload


def judge_answer_sync(
    *,
    api_key: str,
    model: str,
    timeout_seconds: int,
    question: str,
    gold_answer: str,
    predicted_answer: str,
    input_price_per_1m: float,
    cached_input_price_per_1m: float,
    output_price_per_1m: float,
) -> Dict[str, Any]:
    system_prompt = (
        "You are grading a question-answer benchmark. "
        "Mark the prediction correct only if it identifies the same final answer as the gold answer. "
        "Ignore case, surrounding punctuation, whitespace, and extra explanation or supporting file paths. "
        "Do not give partial credit. Return exactly one compact JSON object."
    )
    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Gold answer:\n{gold_answer}\n\n"
        f"Predicted answer:\n{predicted_answer or '[empty]'}\n\n"
        'Return JSON with keys "is_correct" (boolean), "normalized_prediction" (string), and "reason" (string).'
    )
    request_payload = {
        "model": model,
        "reasoning": {"effort": "low"},
        "text": {"verbosity": "low"},
        "max_output_tokens": 180,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    request_body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=request_body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI judge request failed with HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI judge request failed: {exc}") from exc

    response_text = extract_openai_response_text(response_payload)
    parsed = extract_json_object(response_text)
    usage = response_payload.get("usage") or {}
    cost_estimate = estimate_judge_cost(
        usage,
        input_price_per_1m=input_price_per_1m,
        cached_input_price_per_1m=cached_input_price_per_1m,
        output_price_per_1m=output_price_per_1m,
    )

    return {
        "judge_model": model,
        "judged_at": utc_now(),
        "question": question,
        "gold_answer": gold_answer,
        "predicted_answer": predicted_answer,
        "is_correct": bool(parsed.get("is_correct")),
        "normalized_prediction": str(parsed.get("normalized_prediction", "")),
        "reason": str(parsed.get("reason", "")),
        "usage": usage,
        "cost_estimate_usd": cost_estimate,
        "raw_response_text": response_text,
        "raw_response": response_payload,
    }


def maybe_reuse_existing_eval(
    *,
    eval_result_path: Path,
    judge_model: str,
    question: str,
    gold_answer: str,
    predicted_answer: str,
) -> Optional[Dict[str, Any]]:
    existing = read_json_if_exists(eval_result_path)
    if not existing:
        return None
    if existing.get("judge_model") != judge_model:
        return None
    if existing.get("question") != question:
        return None
    if existing.get("gold_answer") != gold_answer:
        return None
    if existing.get("predicted_answer") != predicted_answer:
        return None
    return existing


def evaluate_run_output(
    *,
    output_dir: Path,
    question: str,
    gold_answer: str,
    predicted_answer: str,
    judge_model: str,
    judge_api_key_env: str,
    judge_timeout_seconds: int,
    judge_input_price_per_1m: float,
    judge_cached_input_price_per_1m: float,
    judge_output_price_per_1m: float,
) -> Dict[str, Any]:
    eval_result_path = output_dir / "eval_result.json"

    def persist_eval_summary(eval_result: Dict[str, Any]) -> None:
        state_path = output_dir / "state.json"
        state = read_json_if_exists(state_path)
        if state is None:
            return
        state["evaluation"] = {
            "judge_model": eval_result.get("judge_model"),
            "judged_at": eval_result.get("judged_at"),
            "is_correct": eval_result.get("is_correct"),
            "normalized_prediction": eval_result.get("normalized_prediction"),
            "reason": eval_result.get("reason"),
            "cost_estimate_usd": eval_result.get("cost_estimate_usd"),
        }
        write_json(state_path, state)

    reusable = maybe_reuse_existing_eval(
        eval_result_path=eval_result_path,
        judge_model=judge_model,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
    )
    if reusable is not None:
        persist_eval_summary(reusable)
        return reusable

    api_key = os.environ.get(judge_api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"Missing OpenAI API key in environment variable {judge_api_key_env}")

    eval_result = judge_answer_sync(
        api_key=api_key,
        model=judge_model,
        timeout_seconds=judge_timeout_seconds,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
        input_price_per_1m=judge_input_price_per_1m,
        cached_input_price_per_1m=judge_cached_input_price_per_1m,
        output_price_per_1m=judge_output_price_per_1m,
    )
    write_json(eval_result_path, eval_result)
    persist_eval_summary(eval_result)
    return eval_result


class ConversationFeatures:
    def __init__(
        self,
        *,
        clear_tool_results: bool,
        clear_tool_results_keep_last: int,
        externalize_tool_results: bool,
        strip_thinking: bool,
        strip_usage: bool,
    ) -> None:
        self.clear_tool_results = clear_tool_results
        self.clear_tool_results_keep_last = clear_tool_results_keep_last
        self.externalize_tool_results = externalize_tool_results
        self.strip_thinking = strip_thinking
        self.strip_usage = strip_usage

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ConversationFeatures":
        keep_last = int(args.conversation_clear_tool_results_keep_last)
        if keep_last < 0:
            raise RuntimeError("--conversation-clear-tool-results-keep-last must be >= 0")
        return cls(
            clear_tool_results=bool(args.conversation_clear_tool_results),
            clear_tool_results_keep_last=keep_last,
            externalize_tool_results=bool(args.conversation_externalize_tool_results),
            strip_thinking=bool(args.conversation_strip_thinking),
            strip_usage=bool(args.conversation_strip_usage),
        )

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "ConversationFeatures":
        data = payload or {}
        return cls(
            clear_tool_results=bool(data.get("clear_tool_results", False)),
            clear_tool_results_keep_last=int(data.get("clear_tool_results_keep_last", 3)),
            externalize_tool_results=bool(data.get("externalize_tool_results", False)),
            strip_thinking=bool(data.get("strip_thinking", False)),
            strip_usage=bool(data.get("strip_usage", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clear_tool_results": self.clear_tool_results,
            "clear_tool_results_keep_last": self.clear_tool_results_keep_last,
            "externalize_tool_results": self.externalize_tool_results,
            "strip_thinking": self.strip_thinking,
            "strip_usage": self.strip_usage,
        }

    def enabled_feature_names(self) -> List[str]:
        names: List[str] = []
        if self.clear_tool_results:
            names.append("clear_tool_results")
        if self.externalize_tool_results:
            names.append("externalize_tool_results")
        if self.strip_thinking:
            names.append("strip_thinking")
        if self.strip_usage:
            names.append("strip_usage")
        return names


class RunRecorder:
    def __init__(
        self,
        *,
        output_dir: Path,
        question: str,
        package_dir: Path,
        agent_dir: Path,
        cwd: Path,
        provider: Optional[str],
        model: Optional[str],
        tools: Optional[str],
        max_turns: Optional[int],
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
        conversation_features: ConversationFeatures,
        keep_session: bool,
        resume: bool,
    ) -> None:
        self.output_dir = output_dir
        self.resume = resume
        self.conversation_features = conversation_features
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.events_path = self.output_dir / "events.jsonl"
        self.state_path = self.output_dir / "state.json"
        self.conversation_full_path = self.output_dir / "conversation_full.json"
        self.conversation_path = self.output_dir / "conversation.json"
        self.latest_model_context_path = self.output_dir / "latest_model_context.json"
        self.final_path = self.output_dir / "final.txt"
        self.stderr_path = self.output_dir / "stderr.txt"
        self.question_path = self.output_dir / "question.txt"
        self.tool_results_dir = self.output_dir / "tool_results"

        if resume:
            self.state = self._load_existing_state()
            self.conversation_full = self._load_existing_conversation_full()
            self.latest_model_context = self._load_existing_latest_model_context()
            self._validate_resume_inputs(
                question=question,
                package_dir=package_dir,
                agent_dir=agent_dir,
                cwd=cwd,
                provider=provider,
                model=model,
                tools=tools,
                max_turns=max_turns,
                system_prompt_file=system_prompt_file,
                append_system_prompt_file=append_system_prompt_file,
                conversation_features=conversation_features,
                keep_session=keep_session,
            )
            self.question_path.write_text(question + "\n", encoding="utf-8")
            self.state["status"] = "running"
            self.state["finished_at"] = None
            self.state["error"] = None
            self.state["keep_session"] = keep_session
            self.state["conversation_features"] = self.conversation_features.to_dict()
            self.state["resume_count"] = int(self.state.get("resume_count", 0)) + 1
            self.conversation_full["status"] = "running"
            self.conversation_full["finished_at"] = None
            self.conversation_full["error"] = None
            self.conversation_full["keep_session"] = keep_session
            self.conversation_full["conversation_features"] = self.conversation_features.to_dict()
            self.conversation_full["pending_message"] = None
            self.conversation_full["final_text"] = None
            self.latest_model_context["status"] = "running"
            self.latest_model_context["finished_at"] = None
            self.latest_model_context["error"] = None
            self.latest_model_context["runtime_context_management"] = self.latest_model_context.get(
                "runtime_context_management"
            )
            self.add_note("Resumed run in existing output directory.")
            if not keep_session:
                self.add_note(
                    "Resume is reusing the artifact directory only; agent session continuity is not preserved without --keep-session."
                )
        else:
            self.question_path.write_text(question + "\n", encoding="utf-8")
            self.state = {
                "started_at": utc_now(),
                "finished_at": None,
                "status": "running",
                "question": question,
                "package_dir": str(package_dir),
                "agent_dir": str(agent_dir),
                "cwd": str(cwd),
                "provider": provider,
                "model": model,
                "tools": tools,
                "max_turns": max_turns,
                "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
                "append_system_prompt_file": str(append_system_prompt_file) if append_system_prompt_file else None,
                "conversation_features": self.conversation_features.to_dict(),
                "keep_session": keep_session,
                "resume_count": 0,
                "event_count": 0,
                "turn_count": 0,
                "assistant_text": "",
                "last_event_type": None,
                "messages": [],
                "tool_calls": [],
                "notes": [],
                "paths": {
                    "output_dir": str(self.output_dir),
                    "events_jsonl": str(self.events_path),
                    "state_json": str(self.state_path),
                    "conversation_full_json": str(self.conversation_full_path),
                    "conversation_json": str(self.conversation_path),
                    "latest_model_context_json": str(self.latest_model_context_path),
                    "final_txt": str(self.final_path),
                    "eval_result_json": str(self.output_dir / "eval_result.json"),
                    "stderr_txt": str(self.stderr_path),
                    "question_txt": str(self.question_path),
                    "tool_results_dir": str(self.tool_results_dir),
                },
            }
            self.conversation_full = {
                "started_at": self.state["started_at"],
                "finished_at": None,
                "status": "running",
                "question": question,
                "cwd": str(cwd),
                "provider": provider,
                "model": model,
                "tools": tools,
                "max_turns": max_turns,
                "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
                "append_system_prompt_file": str(append_system_prompt_file) if append_system_prompt_file else None,
                "conversation_features": self.conversation_features.to_dict(),
                "keep_session": keep_session,
                "messages": [],
                "pending_message": None,
                "final_text": None,
            }
            self._init_conversation(
                system_prompt_file=system_prompt_file,
                append_system_prompt_file=append_system_prompt_file,
            )
            self.latest_model_context = {
                "started_at": self.state["started_at"],
                "finished_at": None,
                "status": "running",
                "question": question,
                "cwd": str(cwd),
                "provider": provider,
                "model": model,
                "tools": tools,
                "max_turns": max_turns,
                "conversation_features": self.conversation_features.to_dict(),
                "runtime_context_management": None,
                "request_count": 0,
                "latest": None,
                "error": None,
            }
        self._write_artifacts()

    def _load_existing_state(self) -> Dict[str, Any]:
        state = read_json_if_exists(self.state_path)
        if state is None:
            raise RuntimeError(f"Cannot resume: missing {self.state_path}")
        return state

    def _load_existing_conversation_full(self) -> Dict[str, Any]:
        conversation = read_json_if_exists(self.conversation_full_path)
        if conversation is None:
            conversation = read_json_if_exists(self.conversation_path)
        if conversation is None:
            raise RuntimeError(f"Cannot resume: missing {self.conversation_full_path} and {self.conversation_path}")
        return conversation

    def _load_existing_latest_model_context(self) -> Dict[str, Any]:
        context = read_json_if_exists(self.latest_model_context_path)
        if context is None:
            context = {
                "started_at": self.state.get("started_at"),
                "finished_at": None,
                "status": self.state.get("status", "running"),
                "question": self.state.get("question"),
                "cwd": self.state.get("cwd"),
                "provider": self.state.get("provider"),
                "model": self.state.get("model"),
                "tools": self.state.get("tools"),
                "max_turns": self.state.get("max_turns"),
                "conversation_features": self.conversation_features.to_dict(),
                "runtime_context_management": None,
                "request_count": 0,
                "latest": None,
                "error": None,
            }
        return context

    def _normalize_path_str(self, path: Optional[Path]) -> Optional[str]:
        return str(path) if path else None

    def _infer_keep_session(self, state: Dict[str, Any]) -> Optional[bool]:
        if isinstance(state.get("keep_session"), bool):
            return bool(state["keep_session"])
        command = state.get("command")
        if isinstance(command, list):
            return "--no-session" not in command
        return None

    def _validate_resume_inputs(
        self,
        *,
        question: str,
        package_dir: Path,
        agent_dir: Path,
        cwd: Path,
        provider: Optional[str],
        model: Optional[str],
        tools: Optional[str],
        max_turns: Optional[int],
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
        conversation_features: ConversationFeatures,
        keep_session: bool,
    ) -> None:
        status = self.state.get("status")
        if status == "completed":
            raise RuntimeError(f"Cannot resume completed run in {self.output_dir}")

        comparisons = {
            "question": (self.state.get("question"), question),
            "package_dir": (self.state.get("package_dir"), str(package_dir)),
            "agent_dir": (self.state.get("agent_dir"), str(agent_dir)),
            "cwd": (self.state.get("cwd"), str(cwd)),
            "provider": (self.state.get("provider"), provider),
            "model": (self.state.get("model"), model),
            "tools": (self.state.get("tools"), tools),
            "max_turns": (self.state.get("max_turns"), max_turns),
            "system_prompt_file": (self.state.get("system_prompt_file"), self._normalize_path_str(system_prompt_file)),
            "append_system_prompt_file": (
                self.state.get("append_system_prompt_file"),
                self._normalize_path_str(append_system_prompt_file),
            ),
            "conversation_features": (
                ConversationFeatures.from_dict(self.state.get("conversation_features")).to_dict(),
                conversation_features.to_dict(),
            ),
        }
        mismatches = [
            f"{name}: existing={existing!r} new={new!r}"
            for name, (existing, new) in comparisons.items()
            if existing != new
        ]
        if mismatches:
            mismatch_text = "\n".join(mismatches)
            raise RuntimeError(f"Cannot resume with different run settings:\n{mismatch_text}")

        previous_keep_session = self._infer_keep_session(self.state)
        if previous_keep_session is not None and previous_keep_session != keep_session:
            raise RuntimeError(
                "Cannot resume with a different session mode. Match the previous run's --keep-session setting."
            )

    def _normalize_message(self, message: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not message:
            return None
        normalized = clone_json(message)

        if normalized.get("role") == "assistant":
            if self.conversation_features.strip_thinking:
                normalized["content"] = [
                    part for part in normalized.get("content", []) if part.get("type") != "thinking"
                ]
            if self.conversation_features.strip_usage:
                normalized.pop("usage", None)

        return normalized

    def _write_artifacts(self) -> None:
        write_json(self.state_path, self.state)
        write_json(self.conversation_full_path, self.conversation_full)
        conversation = self._build_processed_conversation()
        write_json(self.conversation_path, conversation)
        write_json(self.latest_model_context_path, self.latest_model_context)

    def _build_processed_conversation(self) -> Dict[str, Any]:
        conversation = clone_json(self.conversation_full)
        self._apply_conversation_features(conversation)
        return conversation

    def _apply_conversation_features(self, conversation: Dict[str, Any]) -> None:
        messages = conversation.get("messages", [])
        if not isinstance(messages, list):
            return

        if self.conversation_features.externalize_tool_results:
            for message in messages:
                if message.get("role") == "toolResult":
                    self._externalize_tool_result_message(message)

        if self.conversation_features.clear_tool_results:
            self._clear_old_tool_result_messages(messages)

    def _get_tool_result_context(self, message: Dict[str, Any]) -> Dict[str, Any]:
        context_management = message.setdefault("context_management", {})
        tool_result_context = context_management.setdefault("tool_result", {})
        return tool_result_context

    def _collect_tool_result_text(self, message: Dict[str, Any]) -> str:
        texts: List[str] = []
        for part in message.get("content", []):
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
        return "\n\n".join(texts)

    def _build_tool_result_stats(self, message: Dict[str, Any]) -> Dict[str, int]:
        stats = count_text_stats(self._collect_tool_result_text(message))
        stats["content_blocks"] = len(message.get("content", []))
        return stats

    def _build_tool_result_file_name(self, message: Dict[str, Any]) -> str:
        tool_call_id = message.get("toolCallId")
        if isinstance(tool_call_id, str) and tool_call_id:
            stem = sanitize_path_component(tool_call_id)
        else:
            stem = f"event-{self.state.get('event_count', 0)}"
        return f"{stem}.json"

    def _externalize_tool_result_message(self, message: Dict[str, Any]) -> None:
        context = self._get_tool_result_context(message)
        if context.get("externalized"):
            return

        self.tool_results_dir.mkdir(parents=True, exist_ok=True)
        rel_path = Path("tool_results") / self._build_tool_result_file_name(message)
        abs_path = self.output_dir / rel_path
        payload = {
            "saved_at": utc_now(),
            "message": clone_json(message),
        }
        write_json(abs_path, payload)

        context["externalized"] = {
            "path": str(rel_path),
            "saved_at": payload["saved_at"],
            "stats": self._build_tool_result_stats(message),
        }

    def _clear_old_tool_result_messages(self, messages: List[Dict[str, Any]]) -> None:
        keep_last = self.conversation_features.clear_tool_results_keep_last
        tool_result_indexes = [
            index for index, message in enumerate(messages) if message.get("role") == "toolResult"
        ]
        keep_indexes = set(tool_result_indexes[-keep_last:] if keep_last else [])

        for index in tool_result_indexes:
            if index in keep_indexes:
                continue
            self._clear_tool_result_message(messages[index])

    def _clear_tool_result_message(self, message: Dict[str, Any]) -> None:
        context = self._get_tool_result_context(message)
        if context.get("status") == "cleared":
            return

        stats = context.get("externalized", {}).get("stats") or self._build_tool_result_stats(message)
        context["status"] = "cleared"
        context["stats"] = stats
        context["cleared_at"] = utc_now()
        context["keep_last"] = self.conversation_features.clear_tool_results_keep_last

        summary_lines = [
            "[tool result cleared from conversation context]",
            f"tool={message.get('toolName', 'unknown')}",
            f"chars={stats.get('chars', 0)}",
            f"lines={stats.get('lines', 0)}",
        ]
        externalized_path = context.get("externalized", {}).get("path")
        if externalized_path:
            summary_lines.append(f"full_output={externalized_path}")

        message["content"] = [{"type": "text", "text": "\n".join(summary_lines)}]

    def _set_pending_message(self, message: Optional[Dict[str, Any]]) -> None:
        self.conversation_full["pending_message"] = self._normalize_message(message)

    def _append_conversation_message(self, message: Optional[Dict[str, Any]]) -> None:
        normalized = self._normalize_message(message)
        if normalized:
            self.conversation_full["messages"].append(normalized)

    def _init_conversation(
        self,
        *,
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
    ) -> None:
        base_prompt = read_text_if_exists(system_prompt_file)
        append_prompt = read_text_if_exists(append_system_prompt_file)

        if base_prompt is None and append_prompt is None:
            return

        parts = [part.strip("\n") for part in [base_prompt, append_prompt] if part]
        system_text = "\n\n".join(parts)
        self.conversation_full["messages"].append(
            {
                "role": "system",
                "content": [{"type": "text", "text": system_text}],
                "sources": {
                    "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
                    "append_system_prompt_file": str(append_system_prompt_file) if append_system_prompt_file else None,
                },
            }
        )

    def set_command(self, command: List[str]) -> None:
        self.state["command"] = command
        self._write_artifacts()

    def add_note(self, note: str) -> None:
        self.state["notes"].append({"timestamp": utc_now(), "text": note})
        self._write_artifacts()

    def append_stderr(self, text: str) -> None:
        if not text:
            return
        with self.stderr_path.open("a", encoding="utf-8") as f:
            f.write(text)

    def record_event(self, event: Dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        recorded_at = utc_now()
        self.state["event_count"] += 1
        self.state["last_event_type"] = event.get("type")

        event_type = event.get("type")
        if event_type == "turn_start":
            self.state["turn_count"] += 1
        elif event_type in {"message_start", "message_end"}:
            self.state["messages"].append(
                {
                    "event": event_type,
                    "message": event.get("message"),
                }
            )
            if event_type == "message_start":
                self._set_pending_message(event.get("message"))
            else:
                self._append_conversation_message(event.get("message"))
                self._set_pending_message(None)
        elif event_type == "message_update":
            assistant_event = event.get("assistantMessageEvent", {})
            if assistant_event.get("type") == "text_delta":
                self.state["assistant_text"] += assistant_event.get("delta", "")
            if assistant_event.get("partial"):
                self._set_pending_message(assistant_event.get("partial"))
        elif event_type in {"tool_execution_start", "tool_execution_end"}:
            self.state["tool_calls"].append(
                {
                    "recorded_at": recorded_at,
                    "event": event_type,
                    "toolCallId": event.get("toolCallId"),
                    "toolName": event.get("toolName"),
                    "args": event.get("args"),
                    "isError": event.get("isError"),
                    "result": event.get("result"),
                }
            )
        elif event_type == "provider_request_context":
            self._record_latest_model_context(event)

        self._write_artifacts()

    def _record_latest_model_context(self, event: Dict[str, Any]) -> None:
        latest_messages = event.get("messages")
        latest_payload = event.get("payload")
        request_index = event.get("requestIndex")
        runtime_context_management = event.get("runtimeContextManagement")
        self.latest_model_context["request_count"] = max(
            int(self.latest_model_context.get("request_count", 0)),
            int(request_index) if isinstance(request_index, int) else int(self.latest_model_context.get("request_count", 0)),
        )
        self.latest_model_context["runtime_context_management"] = (
            clone_json(runtime_context_management) if runtime_context_management is not None else None
        )
        self.latest_model_context["latest"] = {
            "captured_at": utc_now(),
            "request_index": request_index,
            "model": event.get("model"),
            "runtime_context_management": (
                clone_json(runtime_context_management) if runtime_context_management is not None else None
            ),
            "message_count": len(latest_messages) if isinstance(latest_messages, list) else 0,
            "messages": clone_json(latest_messages) if isinstance(latest_messages, list) else [],
            "payload": clone_json(latest_payload),
        }

    def finalize(self, *, status: str, final_text: str = "", error: Optional[str] = None, stderr_text: str = "") -> None:
        self.state["status"] = status
        self.state["finished_at"] = utc_now()
        self.state["assistant_text"] = final_text or self.state.get("assistant_text", "")
        if error:
            self.state["error"] = error

        if self.state["assistant_text"]:
            self.final_path.write_text(self.state["assistant_text"] + ("\n" if not self.state["assistant_text"].endswith("\n") else ""), encoding="utf-8")
        if stderr_text:
            if self.resume and self.stderr_path.exists():
                existing_stderr = self.stderr_path.read_text(encoding="utf-8")
                combined = existing_stderr + ("\n" if existing_stderr and not existing_stderr.endswith("\n") else "") + stderr_text
                self.stderr_path.write_text(combined, encoding="utf-8")
            else:
                self.stderr_path.write_text(stderr_text, encoding="utf-8")

        self.conversation_full["status"] = status
        self.conversation_full["finished_at"] = self.state["finished_at"]
        if error:
            self.conversation_full["error"] = error
        self.conversation_full["final_text"] = self.state["assistant_text"]
        self.conversation_full["pending_message"] = None
        self.latest_model_context["status"] = status
        self.latest_model_context["finished_at"] = self.state["finished_at"]
        if error:
            self.latest_model_context["error"] = error

        self._write_artifacts()


class PiRpcClient:
    def __init__(
        self,
        *,
        package_dir: Path,
        cwd: Path,
        agent_dir: Path,
        provider: Optional[str],
        model: Optional[str],
        tools: Optional[str],
        no_session: bool,
        show_tools: bool,
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
        extra_args: List[str],
    ) -> None:
        self.package_dir = package_dir
        self.cwd = cwd
        self.agent_dir = agent_dir
        self.provider = provider
        self.model = model
        self.tools = tools
        self.no_session = no_session
        self.show_tools = show_tools
        self.system_prompt_file = system_prompt_file
        self.append_system_prompt_file = append_system_prompt_file
        self.extra_args = extra_args
        self.proc: Optional[subprocess.Popen[bytes]] = None
        self.command: Optional[List[str]] = None
        self.stderr_chunks: List[str] = []
        self._stderr_thread: Optional[threading.Thread] = None
        self._request_id = 0

    def _ensure_built_cli(self) -> Path:
        dist_cli = self.package_dir / "dist" / "cli.js"
        if dist_cli.exists():
            return dist_cli

        pi_repo_root = self.package_dir.parents[1]
        sys.stderr.write("[setup] dist/cli.js not found, running `npm run build` at monorepo root\n")
        sys.stderr.flush()
        subprocess.run(["npm", "run", "build"], cwd=str(pi_repo_root), check=True)
        if not dist_cli.exists():
            raise RuntimeError(f"Build completed but CLI was not found at {dist_cli}")
        return dist_cli

    def _build_command(self) -> List[str]:
        dist_cli = self._ensure_built_cli()
        cmd = ["node", str(dist_cli), "--mode", "rpc"]

        if self.provider:
            cmd.extend(["--provider", self.provider])
        if self.model:
            cmd.extend(["--model", self.model])
        if self.tools:
            cmd.extend(["--tools", self.tools])
        if self.system_prompt_file:
            cmd.extend(["--system-prompt", str(self.system_prompt_file)])
        if self.append_system_prompt_file:
            cmd.extend(["--append-system-prompt", str(self.append_system_prompt_file)])
        if self.no_session:
            cmd.append("--no-session")
        cmd.extend(self.extra_args)
        return cmd

    def start(self) -> None:
        if self.proc is not None:
            raise RuntimeError("RPC client already started")

        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(self.agent_dir)
        self.command = self._build_command()
        self.proc = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        assert self.proc.stderr is not None
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _drain_stderr(self) -> None:
        assert self.proc is not None
        assert self.proc.stderr is not None
        for raw in self.proc.stderr:
            self.stderr_chunks.append(raw.decode("utf-8", errors="replace"))

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=2)
        finally:
            self.proc = None

    def _next_id(self) -> str:
        self._request_id += 1
        return f"py-{self._request_id}"

    def _send(self, payload: Dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("RPC client is not running")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()

    def _read_json_line(self) -> Dict[str, Any]:
        if self.proc is None or self.proc.stdout is None:
            raise RuntimeError("RPC client is not running")

        raw = self.proc.stdout.readline()
        if not raw:
            stderr_text = self.get_stderr().strip()
            raise RuntimeError(f"RPC process exited unexpectedly. stderr:\n{stderr_text}")

        if raw.endswith(b"\n"):
            raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        return json.loads(raw.decode("utf-8"))

    def prompt_and_wait(
        self,
        message: str,
        *,
        recorder: Optional[RunRecorder] = None,
        max_turns: Optional[int] = None,
    ) -> str:
        request_id = self._next_id()
        self._send({"id": request_id, "type": "prompt", "message": message})

        auxiliary_ids: set[str] = set()
        text_parts: List[str] = []
        prompt_ack = False
        seen_turns = 0
        sent_turn_limit_abort = False

        while True:
            event = self._read_json_line()
            if recorder:
                recorder.record_event(event)

            event_type = event.get("type")

            if event_type == "response":
                response_id = event.get("id")
                if response_id == request_id:
                    if not event.get("success", False):
                        raise RuntimeError(f"RPC prompt failed: {event.get('error', 'unknown error')}")
                    prompt_ack = True
                elif response_id in auxiliary_ids:
                    pass
                continue

            if event_type == "turn_start":
                seen_turns += 1
                if max_turns is not None and seen_turns > max_turns and not sent_turn_limit_abort:
                    abort_id = self._next_id()
                    auxiliary_ids.add(abort_id)
                    self._send({"id": abort_id, "type": "abort"})
                    sent_turn_limit_abort = True
                    note = f"Reached max_turns={max_turns}; sent RPC abort before turn {seen_turns}."
                    if recorder:
                        recorder.add_note(note)
                    sys.stderr.write(f"\n[runner] {note}\n")
                    sys.stderr.flush()
                continue

            if event_type == "message_update":
                assistant_event = event.get("assistantMessageEvent", {})
                if assistant_event.get("type") == "text_delta":
                    delta = assistant_event.get("delta", "")
                    text_parts.append(delta)
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                continue

            if event_type == "tool_execution_start" and self.show_tools:
                sys.stderr.write(f"\n[tool:start] {event.get('toolName', 'unknown')}\n")
                sys.stderr.flush()
                continue

            if event_type == "tool_execution_end" and self.show_tools:
                tool_name = event.get("toolName", "unknown")
                is_error = "yes" if event.get("isError") else "no"
                sys.stderr.write(f"\n[tool:end] {tool_name} error={is_error}\n")
                sys.stderr.flush()
                continue

            if event_type == "agent_end":
                if not prompt_ack:
                    raise RuntimeError("Received agent_end before prompt acknowledgement")
                break

        return "".join(text_parts)

    def get_stderr(self) -> str:
        return "".join(self.stderr_chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one benchmark-style question against pi-coding-agent via RPC. "
            "Suitable as a starting point for BrowseComp Plus experiments."
        )
    )
    parser.add_argument("question", nargs="*", help="Question text. If omitted, reads from --question-file or stdin.")
    parser.add_argument("--question-file", type=Path, help="Read the question from a UTF-8 text file.")
    parser.add_argument("--provider", help="Provider passed to pi, e.g. anthropic or openai.")
    parser.add_argument("--model", help="Model id or pattern passed to pi.")
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=DEFAULT_PACKAGE_DIR,
        help="Path to the built `packages/coding-agent` directory inside a pi checkout.",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=REPO_ROOT,
        help="Working directory for the agent subprocess. Defaults to the HRCI repo root.",
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=DEFAULT_AGENT_DIR,
        help="Agent config dir. Defaults to this repo's .pi/agent directory.",
    )
    parser.add_argument(
        "--tools",
        default="read,bash",
        help="Comma-separated built-in tools to enable. Default: read,bash",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        help="Client-side cap on agent turns. The runner sends an RPC abort before turn N+1 starts.",
    )
    parser.add_argument(
        "--system-prompt-file",
        type=Path,
        help="Optional text file passed to pi via --system-prompt. By default, pi uses its own dynamically generated system prompt.",
    )
    parser.add_argument(
        "--append-system-prompt-file",
        type=Path,
        help="Optional text file passed to pi via --append-system-prompt.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory to store events.jsonl, state.json, conversation_full.json, conversation.json, "
            "latest_model_context.json, final.txt, and stderr.txt. Default: outputs/runs/<timestamp>"
        ),
    )
    parser.add_argument(
        "--conversation-clear-tool-results",
        action="store_true",
        help=(
            "Compact conversation.json by replacing older toolResult payloads with placeholders "
            "while keeping recent tool results inline."
        ),
    )
    parser.add_argument(
        "--conversation-clear-tool-results-keep-last",
        type=int,
        default=3,
        help="When --conversation-clear-tool-results is enabled, keep the last N toolResult messages inline. Default: 3",
    )
    parser.add_argument(
        "--conversation-externalize-tool-results",
        action="store_true",
        help="Write each toolResult message to output_dir/tool_results/*.json and add a pointer from conversation.json.",
    )
    parser.add_argument(
        "--conversation-strip-thinking",
        action="store_true",
        help="Remove assistant thinking blocks from conversation.json.",
    )
    parser.add_argument(
        "--conversation-strip-usage",
        action="store_true",
        help="Remove assistant usage metadata from conversation.json.",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="__USE_OUTPUT_DIR__",
        help=(
            "Resume in an existing output directory. "
            "Pass a directory explicitly, or use --resume with --output-dir to resume that directory. "
            "If the directory does not exist or is empty, the runner prints a warning and starts a new run there."
        ),
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Persist session history instead of running with --no-session.",
    )
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Print tool start/end events to stderr while the agent runs.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help=(
            "Extra CLI arg or quoted arg string forwarded to pi. "
            'Examples: --extra-arg="--context-management-level level3" or '
            "--extra-arg=--model --extra-arg=claude-sonnet-4-20250514"
        ),
    )
    parser.add_argument(
        "--eval-answer",
        help="Optional gold answer. If provided, the runner grades final.txt with OpenAI and writes eval_result.json.",
    )
    parser.add_argument(
        "--eval-answer-file",
        type=Path,
        help="Optional UTF-8 text file containing the gold answer for evaluation.",
    )
    parser.add_argument(
        "--eval-judge-model",
        default=DEFAULT_EVAL_JUDGE_MODEL,
        help=f"OpenAI judge model. Default: {DEFAULT_EVAL_JUDGE_MODEL}",
    )
    parser.add_argument(
        "--eval-judge-api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the OpenAI API key for evaluation. Default: OPENAI_API_KEY",
    )
    parser.add_argument(
        "--eval-judge-timeout-seconds",
        type=int,
        default=120,
        help="HTTP timeout for the OpenAI judge call. Default: 120",
    )
    parser.add_argument(
        "--eval-judge-input-price-per-1m",
        type=float,
        default=DEFAULT_EVAL_INPUT_PRICE_PER_1M,
        help=f"Judge input token price per 1M tokens. Default: {DEFAULT_EVAL_INPUT_PRICE_PER_1M}",
    )
    parser.add_argument(
        "--eval-judge-cached-input-price-per-1m",
        type=float,
        default=DEFAULT_EVAL_CACHED_INPUT_PRICE_PER_1M,
        help=f"Judge cached-input token price per 1M tokens. Default: {DEFAULT_EVAL_CACHED_INPUT_PRICE_PER_1M}",
    )
    parser.add_argument(
        "--eval-judge-output-price-per-1m",
        type=float,
        default=DEFAULT_EVAL_OUTPUT_PRICE_PER_1M,
        help=f"Judge output token price per 1M tokens. Default: {DEFAULT_EVAL_OUTPUT_PRICE_PER_1M}",
    )
    return parser.parse_args()


def load_question(args: argparse.Namespace, *, resume_dir: Optional[Path]) -> str:
    if args.question_file:
        return args.question_file.read_text(encoding="utf-8").strip()
    if args.question:
        return " ".join(args.question).strip()
    if resume_dir:
        resume_question = read_text_if_exists(resume_dir / "question.txt")
        if resume_question is not None:
            return resume_question.strip()
        state = read_json_if_exists(resume_dir / "state.json")
        if state and isinstance(state.get("question"), str):
            return state["question"].strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def resolve_output_dir(args: argparse.Namespace) -> tuple[Path, bool]:
    output_dir = args.output_dir.resolve() if args.output_dir else None
    resume_dir: Optional[Path] = None

    if args.resume is not None:
        if args.resume == "__USE_OUTPUT_DIR__":
            if output_dir is None:
                raise RuntimeError("--resume without a directory requires --output-dir")
            resume_dir = output_dir
        else:
            resume_dir = Path(args.resume).resolve()
            if output_dir is not None and output_dir != resume_dir:
                raise RuntimeError("--resume DIR and --output-dir must point to the same directory")

    resolved_dir = resume_dir or output_dir or build_default_output_dir().resolve()
    return resolved_dir, resume_dir is not None


def normalize_resume_mode(output_dir: Path, resume_requested: bool) -> tuple[bool, Optional[str]]:
    if not resume_requested:
        return False, None
    if not output_dir.exists():
        return (
            False,
            f"[runner] --resume requested but directory does not exist; creating a new run instead: {output_dir}",
        )
    if is_directory_empty(output_dir):
        return (
            False,
            f"[runner] --resume requested but directory is empty; creating a new run instead: {output_dir}",
        )
    return True, None


def main() -> int:
    args = parse_args()
    if args.eval_answer and args.eval_answer_file:
        print("Use at most one of --eval-answer and --eval-answer-file.", file=sys.stderr)
        return 2
    eval_answer = load_eval_answer(
        eval_answer=args.eval_answer,
        eval_answer_file=args.eval_answer_file.resolve() if args.eval_answer_file else None,
    )
    try:
        conversation_features = ConversationFeatures.from_args(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        output_dir, resume = resolve_output_dir(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    resume, resume_warning = normalize_resume_mode(output_dir, resume)
    if resume_warning:
        print(resume_warning, file=sys.stderr)

    question = load_question(args, resume_dir=output_dir if resume else None)
    if not question:
        print("No question provided. Use positional text, --question-file, or stdin.", file=sys.stderr)
        return 2

    system_prompt_file = args.system_prompt_file
    if not resume:
        if output_dir.exists() and not is_directory_empty(output_dir):
            print(
                f"Refusing to reuse non-empty output directory without --resume: {output_dir}",
                file=sys.stderr,
            )
            return 2

    existing_state = read_json_if_exists(output_dir / "state.json") if resume else None
    if resume and eval_answer is not None and existing_state and existing_state.get("status") == "completed":
        predicted_answer = (
            read_text_if_exists(output_dir / "final.txt")
            or existing_state.get("assistant_text")
            or ""
        ).strip()
        try:
            eval_result = evaluate_run_output(
                output_dir=output_dir,
                question=question,
                gold_answer=eval_answer,
                predicted_answer=predicted_answer,
                judge_model=args.eval_judge_model,
                judge_api_key_env=args.eval_judge_api_key_env,
                judge_timeout_seconds=args.eval_judge_timeout_seconds,
                judge_input_price_per_1m=args.eval_judge_input_price_per_1m,
                judge_cached_input_price_per_1m=args.eval_judge_cached_input_price_per_1m,
                judge_output_price_per_1m=args.eval_judge_output_price_per_1m,
            )
        except Exception as exc:
            print(f"Evaluation failed: {exc}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "output_dir": str(output_dir),
                    "is_correct": eval_result.get("is_correct"),
                    "normalized_prediction": eval_result.get("normalized_prediction"),
                    "reason": eval_result.get("reason"),
                    "eval_result_json": str(output_dir / "eval_result.json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        recorder = RunRecorder(
            output_dir=output_dir,
            question=question,
            package_dir=args.package_dir.resolve(),
            agent_dir=args.agent_dir.resolve(),
            cwd=args.cwd.resolve(),
            provider=args.provider,
            model=args.model,
            tools=args.tools,
            max_turns=args.max_turns,
            system_prompt_file=system_prompt_file.resolve() if system_prompt_file else None,
            append_system_prompt_file=args.append_system_prompt_file.resolve() if args.append_system_prompt_file else None,
            conversation_features=conversation_features,
            keep_session=args.keep_session,
            resume=resume,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    client = PiRpcClient(
        package_dir=args.package_dir.resolve(),
        cwd=args.cwd.resolve(),
        agent_dir=args.agent_dir.resolve(),
        provider=args.provider,
        model=args.model,
        tools=args.tools,
        no_session=not args.keep_session,
        show_tools=args.show_tools,
        system_prompt_file=system_prompt_file.resolve() if system_prompt_file else None,
        append_system_prompt_file=args.append_system_prompt_file.resolve() if args.append_system_prompt_file else None,
        extra_args=expand_extra_args(args.extra_arg),
    )

    try:
        client.start()
        if client.command:
            recorder.set_command(client.command)
        sys.stderr.write(f"[runner] saving run artifacts under {output_dir}\n")
        sys.stderr.flush()

        final_text = client.prompt_and_wait(question, recorder=recorder, max_turns=args.max_turns)
        if not final_text.endswith("\n"):
            sys.stdout.write("\n")
        recorder.finalize(status="completed", final_text=final_text, stderr_text=client.get_stderr())
        if eval_answer is not None:
            eval_result = evaluate_run_output(
                output_dir=output_dir,
                question=question,
                gold_answer=eval_answer,
                predicted_answer=final_text.strip(),
                judge_model=args.eval_judge_model,
                judge_api_key_env=args.eval_judge_api_key_env,
                judge_timeout_seconds=args.eval_judge_timeout_seconds,
                judge_input_price_per_1m=args.eval_judge_input_price_per_1m,
                judge_cached_input_price_per_1m=args.eval_judge_cached_input_price_per_1m,
                judge_output_price_per_1m=args.eval_judge_output_price_per_1m,
            )
            print(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "is_correct": eval_result.get("is_correct"),
                        "normalized_prediction": eval_result.get("normalized_prediction"),
                        "reason": eval_result.get("reason"),
                        "eval_result_json": str(output_dir / "eval_result.json"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    except Exception as exc:
        stderr_text = client.get_stderr().strip()
        recorder.finalize(status="failed", error=str(exc), stderr_text=stderr_text)
        print(f"RPC run failed: {exc}", file=sys.stderr)
        if stderr_text:
            print("\n[agent stderr]", file=sys.stderr)
            print(stderr_text, file=sys.stderr)
        return 1
    finally:
        client.stop()


if __name__ == "__main__":
    raise SystemExit(main())
