#!/usr/bin/env python3
"""
Print pi's default dynamically generated system prompt for a given tool set.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_PI_REPO = REPO_ROOT / "pi-mono"
DEFAULT_PACKAGE_DIR = DEFAULT_PI_REPO / "packages" / "coding-agent"


def ensure_built_package(package_dir: Path) -> None:
    dist_system_prompt = package_dir / "dist" / "core" / "system-prompt.js"
    dist_tools_index = package_dir / "dist" / "core" / "tools" / "index.js"
    if dist_system_prompt.exists() and dist_tools_index.exists():
        return

    pi_repo_root = package_dir.parents[1]
    print("[setup] built pi package not found, running `npm run build` at monorepo root", file=sys.stderr)
    subprocess.run(["npm", "run", "build"], cwd=str(pi_repo_root), check=True)

    if not dist_system_prompt.exists() or not dist_tools_index.exists():
        raise RuntimeError(f"Build completed but required dist files were not found under {package_dir / 'dist'}")


def parse_tools(raw: str | None) -> List[str]:
    if not raw:
        return ["read", "bash", "edit", "write"]
    tools = [tool.strip() for tool in raw.split(",") if tool.strip()]
    return tools or ["read", "bash", "edit", "write"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print pi's default dynamically generated system prompt for a given tool set."
    )
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
        help="Working directory to embed in the generated prompt. Default: HRCI repo root.",
    )
    parser.add_argument(
        "--tools",
        help="Comma-separated built-in tools. Default: read,bash,edit,write",
    )
    parser.add_argument(
        "--append-system-prompt-file",
        type=Path,
        help="Optional text file appended the same way pi would append a system prompt.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_dir = args.package_dir.resolve()
    cwd = args.cwd.resolve()
    tools = parse_tools(args.tools)
    append_text = ""

    if args.append_system_prompt_file:
        append_text = args.append_system_prompt_file.read_text(encoding="utf-8")

    ensure_built_package(package_dir)

    system_prompt_module = (package_dir / "dist" / "core" / "system-prompt.js").resolve().as_uri()
    tools_module = (package_dir / "dist" / "core" / "tools" / "index.js").resolve().as_uri()

    node_script = """
const { buildSystemPrompt } = await import(process.argv[1]);
const { createAllToolDefinitions } = await import(process.argv[2]);

const cwd = process.argv[3];
const tools = JSON.parse(process.argv[4]);
const appendText = process.argv[5] || "";

const definitions = createAllToolDefinitions(cwd);
const toolSnippets = {};
const promptGuidelines = [];
const missingTools = [];

for (const toolName of tools) {
  const definition = definitions[toolName];
  if (!definition) {
    missingTools.push(toolName);
    continue;
  }
  if (definition.promptSnippet) {
    toolSnippets[toolName] = definition.promptSnippet;
  }
  if (Array.isArray(definition.promptGuidelines)) {
    promptGuidelines.push(...definition.promptGuidelines);
  }
}

if (missingTools.length > 0) {
  console.error(`Unknown built-in tools: ${missingTools.join(", ")}`);
  process.exit(2);
}

const prompt = buildSystemPrompt({
  cwd,
  selectedTools: tools,
  toolSnippets,
  promptGuidelines,
  appendSystemPrompt: appendText || undefined,
});

process.stdout.write(prompt);
"""

    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            node_script,
            system_prompt_module,
            tools_module,
            str(cwd),
            json.dumps(tools),
            append_text,
        ],
        text=True,
        capture_output=True,
    )

    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return completed.returncode

    print(completed.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
