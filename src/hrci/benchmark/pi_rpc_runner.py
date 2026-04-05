#!/usr/bin/env python3
"""
Minimal Python RPC example for pi-coding-agent.

This is aimed at benchmark-style experiments such as BrowseComp Plus:
- start the agent in RPC mode
- send one question
- stream text deltas
- optionally log tool events
- return the final assistant text

Important:
- The stock coding-agent package does NOT ship a dedicated browser tool.
- Built-in tools are: read, bash, edit, write, grep, find, ls.
- For BrowseComp-style tasks, the agent can still browse indirectly through
  `bash` with command-line tools such as `curl`, `wget`, `lynx`, or a custom
  extension that exposes a browser/search tool.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_PI_REPO = REPO_ROOT / "long-horizon-pi"
DEFAULT_PACKAGE_DIR = DEFAULT_PI_REPO / "packages" / "coding-agent"
DEFAULT_AGENT_DIR = DEFAULT_PI_REPO / ".pi" / "agent"


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
        self.extra_args = extra_args
        self.proc: Optional[subprocess.Popen[bytes]] = None
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
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(pi_repo_root),
            check=True,
        )
        if not dist_cli.exists():
            raise RuntimeError(f"Build completed but CLI was not found at {dist_cli}")
        return dist_cli

    def _build_command(self) -> List[str]:
        dist_cli = self._ensure_built_cli()
        cmd = ["node", str(dist_cli)]

        cmd.extend(["--mode", "rpc"])
        if self.provider:
            cmd.extend(["--provider", self.provider])
        if self.model:
            cmd.extend(["--model", self.model])
        if self.tools:
            cmd.extend(["--tools", self.tools])
        if self.no_session:
            cmd.append("--no-session")
        cmd.extend(self.extra_args)
        return cmd

    def start(self) -> None:
        if self.proc is not None:
            raise RuntimeError("RPC client already started")

        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(self.agent_dir)

        self.proc = subprocess.Popen(
            self._build_command(),
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

    def prompt_and_wait(self, message: str) -> str:
        request_id = self._next_id()
        self._send({"id": request_id, "type": "prompt", "message": message})

        text_parts: List[str] = []
        prompt_ack = False

        while True:
            event = self._read_json_line()
            event_type = event.get("type")

            if event_type == "response" and event.get("id") == request_id:
                if not event.get("success", False):
                    raise RuntimeError(f"RPC prompt failed: {event.get('error', 'unknown error')}")
                prompt_ack = True
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
                tool_name = event.get("toolName", "unknown")
                sys.stderr.write(f"\n[tool:start] {tool_name}\n")
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
        help="Extra CLI arg forwarded to pi. Can be used multiple times.",
    )
    return parser.parse_args()


def load_question(args: argparse.Namespace) -> str:
    if args.question_file:
        return args.question_file.read_text(encoding="utf-8").strip()
    if args.question:
        return " ".join(args.question).strip()
    return sys.stdin.read().strip()


def main() -> int:
    args = parse_args()
    question = load_question(args)
    if not question:
        print("No question provided. Use positional text, --question-file, or stdin.", file=sys.stderr)
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
        extra_args=args.extra_arg,
    )

    try:
        client.start()
        final_text = client.prompt_and_wait(question)
        if not final_text.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print(f"RPC run failed: {exc}", file=sys.stderr)
        stderr_text = client.get_stderr().strip()
        if stderr_text:
            print("\n[agent stderr]", file=sys.stderr)
            print(stderr_text, file=sys.stderr)
        return 1
    finally:
        client.stop()


if __name__ == "__main__":
    raise SystemExit(main())
