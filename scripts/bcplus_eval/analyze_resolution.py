#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "bcplus_eval_100" / "openai_level5_limit10_concurrency10"

RG_HIT_RE = re.compile(r"^(?P<path>(?:\.{0,2}/|/)[^:\n]+):(?P<line>\d+):(?P<text>.*)$")
FILE_LINE_RE = re.compile(r"^(?:\.{0,2}/|/).+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class CorpusStats:
    total_docs: int
    total_lines: Optional[int]
    line_counts_by_path: Dict[str, int]
    size_bytes_by_path: Dict[str, int]


@dataclass
class GoldDoc:
    docid: str
    url: Optional[str]
    text: str
    normalized_text: str
    local_path: Optional[str] = None
    local_line_count: Optional[int] = None
    local_size_bytes: Optional[int] = None


@dataclass
class Observation:
    qid: str
    index: int
    role_index: int
    tool_name: str
    command: Optional[str]
    read_path: Optional[str]
    result_text: str
    candidate_doc_paths: Set[str]
    candidate_doc_count: Optional[int]
    candidate_line_count: Optional[int]
    matched_docs: Dict[str, Dict[str, Any]]
    duration_ms: Optional[int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze BrowseComp-Plus HRCI trajectories and estimate realized retrieval resolution "
            "from saved conversation artifacts."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Run directory containing per-query outputs. Default: {DEFAULT_OUTPUT_ROOT}",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        help="Optional corpus directory override. If omitted, infer from config.json.",
    )
    parser.add_argument(
        "--write-json",
        type=Path,
        help="Optional explicit path for JSON output. Default: <output-root>/resolution_analysis.json",
    )
    parser.add_argument(
        "--write-md",
        type=Path,
        help="Optional explicit path for Markdown summary. Default: <output-root>/resolution_analysis.md",
    )
    parser.add_argument(
        "--min-snippet-chars",
        type=int,
        default=24,
        help="Minimum normalized snippet length used when matching tool output against gold evidence docs. Default: 24",
    )
    parser.add_argument(
        "--segment-chars",
        type=int,
        default=300,
        help="Pseudo-segment size, in characters, for within-document resolution when raw files are flattened to very few lines. Default: 300",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_text(text: str) -> str:
    lowered = text.lower()
    normalized = NON_ALNUM_RE.sub(" ", lowered)
    return " ".join(normalized.split())


def score_from_candidate_count(candidate_count: Optional[int], universe_count: Optional[int]) -> Optional[float]:
    if candidate_count is None or universe_count is None:
        return None
    candidate_count = max(int(candidate_count), 1)
    universe_count = max(int(universe_count), 1)
    if universe_count <= 1:
        return 1.0
    if candidate_count >= universe_count:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (math.log(candidate_count) / math.log(universe_count))))


def infer_corpus_dir(output_root: Path, explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit.resolve()
    config_path = output_root / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Could not infer corpus dir because config is missing: {config_path}")
    config = read_json(config_path)
    corpus_dir = config.get("corpus_dir")
    if not corpus_dir:
        raise ValueError(f"config.json does not contain corpus_dir: {config_path}")
    configured = Path(corpus_dir)
    if configured.exists():
        return configured.resolve()
    local_default = REPO_ROOT / "corpus" / "bc_plus_docs"
    if local_default.exists():
        return local_default.resolve()
    return configured.resolve()


def build_corpus_stats(corpus_dir: Path) -> CorpusStats:
    cache_path = corpus_dir / ".resolution_corpus_stats.json"
    if cache_path.exists():
        cached = read_json(cache_path)
        if cached.get("corpus_dir") == str(corpus_dir):
            return CorpusStats(
                total_docs=int(cached.get("total_docs", 0) or 0),
                total_lines=(
                    max(int(cached.get("total_lines", 1) or 1), 1)
                    if cached.get("total_lines") is not None
                    else None
                ),
                line_counts_by_path={},
                size_bytes_by_path={},
            )

    quoted = shlex.quote(str(corpus_dir))
    doc_cmd = f"find -L {quoted} -type f | wc -l"
    doc_result = subprocess.run(["/bin/zsh", "-lc", doc_cmd], check=True, capture_output=True, text=True)
    total_docs = int(doc_result.stdout.strip() or "0")
    write_json(
        cache_path,
        {
            "corpus_dir": str(corpus_dir),
            "total_docs": total_docs,
            "total_lines": None,
        },
    )
    return CorpusStats(total_docs=total_docs, total_lines=None, line_counts_by_path={}, size_bytes_by_path={})


def get_file_line_count(corpus_stats: CorpusStats, path: Optional[str]) -> Optional[int]:
    if not path:
        return None
    cached = corpus_stats.line_counts_by_path.get(path)
    if cached is not None:
        return cached
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            count = sum(1 for _ in handle)
    except OSError:
        return None
    count = max(count, 1)
    corpus_stats.line_counts_by_path[path] = count
    return count


def get_file_size_bytes(corpus_stats: CorpusStats, path: Optional[str]) -> Optional[int]:
    if not path:
        return None
    cached = corpus_stats.size_bytes_by_path.get(path)
    if cached is not None:
        return cached
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        size = file_path.stat().st_size
    except OSError:
        return None
    size = max(int(size), 1)
    corpus_stats.size_bytes_by_path[path] = size
    return size


def count_segments(char_count: Optional[int], segment_chars: int) -> Optional[int]:
    if char_count is None:
        return None
    return max(1, math.ceil(max(int(char_count), 1) / max(segment_chars, 1)))


def iter_query_dirs(output_root: Path) -> Iterable[Path]:
    for child in sorted(output_root.iterdir(), key=lambda p: p.name):
        if child.is_dir() and (child / "item.json").exists() and (child / "conversation_full.json").exists():
            yield child


def reanchor_to_local_corpus(path: Path, corpus_dir: Path) -> Path:
    parts = list(path.parts)
    if "bc_plus_docs" in parts:
        anchor = parts.index("bc_plus_docs")
        suffix = parts[anchor + 1 :]
        return (corpus_dir / Path(*suffix)).resolve()
    return path


def resolve_path(raw_path: str, *, cwd: Optional[Path], corpus_dir: Path) -> str:
    raw_path = raw_path.strip()
    if not raw_path:
        return raw_path
    path = Path(raw_path)
    if path.is_absolute():
        if path.exists():
            return str(path.resolve())
        return str(reanchor_to_local_corpus(path, corpus_dir))
    if cwd is not None:
        resolved = (cwd / path).resolve()
        if resolved.exists():
            return str(resolved)
        return str(reanchor_to_local_corpus(resolved, corpus_dir))
    return str((corpus_dir / path).resolve())


def guess_local_path_from_url(url: Optional[str], corpus_dir: Path) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.strip()
    if not host:
        return None
    host_dir = corpus_dir / host
    if not host_dir.exists():
        return None
    suffix = Path(parsed.path).name
    suffix_norm = normalize_text(Path(suffix).stem)
    candidates = list(host_dir.rglob("*"))
    if not candidates:
        return None
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if suffix and suffix in candidate.name:
            return str(candidate.resolve())
        if suffix_norm and suffix_norm in normalize_text(candidate.stem):
            return str(candidate.resolve())
    txt_candidate = host_dir / (suffix + ".txt")
    if txt_candidate.exists():
        return str(txt_candidate.resolve())
    return None


def build_gold_docs(item: Dict[str, Any], corpus_dir: Path, corpus_stats: CorpusStats) -> List[GoldDoc]:
    gold_docs: List[GoldDoc] = []
    for row in item.get("evidence_docs") or item.get("gold_docs") or []:
        url = row.get("url")
        local_path = guess_local_path_from_url(url, corpus_dir)
        local_line_count = get_file_line_count(corpus_stats, local_path)
        local_size_bytes = get_file_size_bytes(corpus_stats, local_path)
        gold_docs.append(
            GoldDoc(
                docid=str(row["docid"]),
                url=url,
                text=row.get("text") or "",
                normalized_text=normalize_text(row.get("text") or ""),
                local_path=local_path,
                local_line_count=local_line_count,
                local_size_bytes=local_size_bytes,
            )
        )
    return gold_docs


def match_snippet_to_gold_docs(
    snippet: str,
    gold_docs: Sequence[GoldDoc],
    *,
    min_snippet_chars: int,
) -> Dict[str, str]:
    normalized = normalize_text(snippet)
    if len(normalized) < min_snippet_chars:
        return {}
    matches: Dict[str, str] = {}
    for gold_doc in gold_docs:
        if normalized and normalized in gold_doc.normalized_text:
            matches[gold_doc.docid] = normalized
    return matches


def extract_candidate_doc_paths(text: str, *, cwd: Optional[Path], corpus_dir: Path) -> Set[str]:
    paths: Set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if RG_HIT_RE.match(line):
            match = RG_HIT_RE.match(line)
            assert match is not None
            paths.add(resolve_path(match.group("path"), cwd=cwd, corpus_dir=corpus_dir))
            continue
        if FILE_LINE_RE.match(line) and "." in Path(line).name:
            paths.add(resolve_path(line, cwd=cwd, corpus_dir=corpus_dir))
    return paths


def count_candidate_lines_for_read(text: str) -> int:
    lines = text.splitlines()
    return max(len(lines), 1)


def pair_observations(
    *,
    qid: str,
    conversation_full: Dict[str, Any],
    corpus_dir: Path,
    gold_docs: Sequence[GoldDoc],
    min_snippet_chars: int,
) -> List[Observation]:
    cwd_text = conversation_full.get("cwd")
    cwd = Path(cwd_text) if cwd_text else corpus_dir
    messages = conversation_full.get("messages") or []
    observations: List[Observation] = []
    observation_index = 0
    for idx, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        tool_calls = [block for block in message.get("content", []) if block.get("type") == "toolCall"]
        if not tool_calls:
            continue
        tool_call = tool_calls[-1]
        tool_call_id = tool_call.get("id")
        tool_name = str(tool_call.get("name") or "")
        arguments = tool_call.get("arguments") or {}

        result_message = None
        for look_ahead in range(idx + 1, len(messages)):
            candidate = messages[look_ahead]
            if candidate.get("role") == "toolResult" and candidate.get("toolCallId") == tool_call_id:
                result_message = candidate
                break
            if candidate.get("role") == "assistant":
                break
        if result_message is None:
            continue

        result_text = "".join(block.get("text", "") for block in result_message.get("content", []) if block.get("type") == "text")
        candidate_doc_paths: Set[str] = set()
        candidate_line_count: Optional[int] = None
        matched_docs: Dict[str, Dict[str, Any]] = {}

        rg_hits: List[Tuple[str, int, str]] = []
        for raw_line in result_text.splitlines():
            match = RG_HIT_RE.match(raw_line)
            if match is None:
                continue
            resolved_path = resolve_path(match.group("path"), cwd=cwd, corpus_dir=corpus_dir)
            line_no = int(match.group("line"))
            snippet = match.group("text").strip()
            rg_hits.append((resolved_path, line_no, snippet))
            candidate_doc_paths.add(resolved_path)

        if rg_hits:
            candidate_line_count = len(rg_hits)
            per_doc_hit_lines: Dict[str, int] = defaultdict(int)
            for resolved_path, line_no, snippet in rg_hits:
                matches = match_snippet_to_gold_docs(snippet, gold_docs, min_snippet_chars=min_snippet_chars)
                for docid, normalized_snippet in matches.items():
                    per_doc_hit_lines[docid] += 1
                    current = matched_docs.get(docid)
                    if current is None or len(normalized_snippet) > len(current["normalized_snippet"]):
                        matched_docs[docid] = {
                            "matched_via": "rg_hit",
                            "path": resolved_path,
                            "line_no": line_no,
                            "snippet": snippet,
                            "normalized_snippet": normalized_snippet,
                            "within_doc_candidate_lines": None,
                            "within_doc_candidate_chars": len(snippet),
                        }
            for docid, hit_count in per_doc_hit_lines.items():
                if docid in matched_docs:
                    matched_docs[docid]["within_doc_candidate_lines"] = hit_count
        elif tool_name == "read":
            raw_read_path = str(arguments.get("path") or "")
            resolved_read_path = resolve_path(raw_read_path, cwd=cwd, corpus_dir=corpus_dir) if raw_read_path else None
            if resolved_read_path:
                candidate_doc_paths.add(resolved_read_path)
            candidate_line_count = count_candidate_lines_for_read(result_text)
            lines = [line for line in result_text.splitlines() if line.strip()]
            best_matches: Dict[str, Tuple[str, str]] = {}
            for line in lines:
                matches = match_snippet_to_gold_docs(line, gold_docs, min_snippet_chars=min_snippet_chars)
                for docid, normalized_snippet in matches.items():
                    current = best_matches.get(docid)
                    if current is None or len(normalized_snippet) > len(current[1]):
                        best_matches[docid] = (line, normalized_snippet)
            for docid, (snippet, normalized_snippet) in best_matches.items():
                matched_docs[docid] = {
                    "matched_via": "read",
                    "path": resolved_read_path,
                    "line_no": None,
                    "snippet": snippet,
                    "normalized_snippet": normalized_snippet,
                    "within_doc_candidate_lines": candidate_line_count,
                    "within_doc_candidate_chars": len(result_text),
                }
        else:
            candidate_doc_paths = extract_candidate_doc_paths(result_text, cwd=cwd, corpus_dir=corpus_dir)

        candidate_doc_count = len(candidate_doc_paths) if candidate_doc_paths else None
        duration_ms = None
        tool_execution = result_message.get("tool_execution") or {}
        if isinstance(tool_execution.get("duration_ms"), (int, float)):
            duration_ms = int(tool_execution["duration_ms"])

        observation_index += 1
        observations.append(
            Observation(
                qid=qid,
                index=observation_index,
                role_index=idx,
                tool_name=tool_name,
                command=arguments.get("command"),
                read_path=arguments.get("path"),
                result_text=result_text,
                candidate_doc_paths=candidate_doc_paths,
                candidate_doc_count=candidate_doc_count,
                candidate_line_count=candidate_line_count,
                matched_docs=matched_docs,
                duration_ms=duration_ms,
            )
        )
    return observations


def latest_payload_text(latest_model_context: Dict[str, Any]) -> str:
    latest = latest_model_context.get("latest") or {}
    payload = latest.get("payload") or {}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def summarize_query(
    *,
    query_dir: Path,
    corpus_dir: Path,
    corpus_stats: CorpusStats,
    min_snippet_chars: int,
    segment_chars: int,
) -> Dict[str, Any]:
    item = read_json(query_dir / "item.json")
    conversation_full = read_json(query_dir / "conversation_full.json")
    result = read_json(query_dir / "result.json") if (query_dir / "result.json").exists() else {}
    latest_model_context = read_json(query_dir / "latest_model_context.json") if (query_dir / "latest_model_context.json").exists() else {}
    qid = str(item["query_id"])

    gold_docs = build_gold_docs(item, corpus_dir, corpus_stats)
    observations = pair_observations(
        qid=qid,
        conversation_full=conversation_full,
        corpus_dir=corpus_dir,
        gold_docs=gold_docs,
        min_snippet_chars=min_snippet_chars,
    )

    payload_norm = normalize_text(latest_payload_text(latest_model_context))
    per_doc: List[Dict[str, Any]] = []

    for gold_doc in gold_docs:
        doc_observations: List[Observation] = [obs for obs in observations if gold_doc.docid in obs.matched_docs]
        best_doc_score = None
        best_line_score = None
        best_within_doc_score = None
        best_within_doc_segment_score = None
        best_doc_observation = None
        best_line_observation = None
        best_within_doc_observation = None
        best_within_doc_segment_observation = None

        for obs in doc_observations:
            matched = obs.matched_docs[gold_doc.docid]
            if matched.get("path") and not gold_doc.local_path:
                gold_doc.local_path = matched.get("path")
                gold_doc.local_line_count = get_file_line_count(corpus_stats, gold_doc.local_path)
                gold_doc.local_size_bytes = get_file_size_bytes(corpus_stats, gold_doc.local_path)

            doc_score = score_from_candidate_count(obs.candidate_doc_count, corpus_stats.total_docs)
            line_score = score_from_candidate_count(obs.candidate_line_count, corpus_stats.total_lines)
            within_doc_universe = gold_doc.local_line_count
            within_doc_count = matched.get("within_doc_candidate_lines")
            within_doc_score = score_from_candidate_count(within_doc_count, within_doc_universe)
            within_doc_segment_universe = count_segments(gold_doc.local_size_bytes, segment_chars)
            within_doc_segment_count = count_segments(matched.get("within_doc_candidate_chars"), segment_chars)
            within_doc_segment_score = score_from_candidate_count(
                within_doc_segment_count,
                within_doc_segment_universe,
            )

            if best_doc_score is None or (doc_score is not None and doc_score > best_doc_score):
                best_doc_score = doc_score
                best_doc_observation = obs
            if best_line_score is None or (line_score is not None and line_score > best_line_score):
                best_line_score = line_score
                best_line_observation = obs
            if best_within_doc_score is None or (within_doc_score is not None and within_doc_score > best_within_doc_score):
                best_within_doc_score = within_doc_score
                best_within_doc_observation = obs
            if best_within_doc_segment_score is None or (
                within_doc_segment_score is not None and within_doc_segment_score > best_within_doc_segment_score
            ):
                best_within_doc_segment_score = within_doc_segment_score
                best_within_doc_segment_observation = obs

        retained_in_latest_context = False
        retained_snippet = None
        if best_line_observation is not None:
            retained_snippet = best_line_observation.matched_docs[gold_doc.docid]["normalized_snippet"]
            retained_in_latest_context = bool(retained_snippet and retained_snippet in payload_norm)

        best_combined_score = None
        if best_doc_score is not None and best_within_doc_score is not None:
            best_combined_score = min(best_doc_score, best_within_doc_score)
        best_segment_combined_score = None
        if best_doc_score is not None and best_within_doc_segment_score is not None:
            best_segment_combined_score = min(best_doc_score, best_within_doc_segment_score)

        per_doc.append(
            {
                "docid": gold_doc.docid,
                "url": gold_doc.url,
                "local_path": gold_doc.local_path,
                "local_line_count": gold_doc.local_line_count,
                "local_size_bytes": gold_doc.local_size_bytes,
                "matched": bool(doc_observations),
                "match_count": len(doc_observations),
                "best_doc_resolution": best_doc_score,
                "best_corpus_line_resolution": best_line_score,
                "best_within_doc_resolution": best_within_doc_score,
                "best_within_doc_segment_resolution": best_within_doc_segment_score,
                "best_combined_resolution": best_combined_score,
                "best_segment_combined_resolution": best_segment_combined_score,
                "first_hit_observation_index": None if not doc_observations else doc_observations[0].index,
                "best_doc_observation_index": None if best_doc_observation is None else best_doc_observation.index,
                "best_line_observation_index": None if best_line_observation is None else best_line_observation.index,
                "best_within_doc_observation_index": (
                    None if best_within_doc_observation is None else best_within_doc_observation.index
                ),
                "best_within_doc_segment_observation_index": (
                    None if best_within_doc_segment_observation is None else best_within_doc_segment_observation.index
                ),
                "retained_in_latest_context": retained_in_latest_context,
                "best_snippet": (
                    None
                    if best_line_observation is None
                    else best_line_observation.matched_docs[gold_doc.docid]["snippet"][:500]
                ),
                "best_snippet_path": (
                    None
                    if best_line_observation is None
                    else best_line_observation.matched_docs[gold_doc.docid]["path"]
                ),
                "best_snippet_line_no": (
                    None
                    if best_line_observation is None
                    else best_line_observation.matched_docs[gold_doc.docid]["line_no"]
                ),
            }
        )

    matched_doc_scores = [row["best_doc_resolution"] for row in per_doc if row["best_doc_resolution"] is not None]
    matched_line_scores = [row["best_corpus_line_resolution"] for row in per_doc if row["best_corpus_line_resolution"] is not None]
    matched_within_doc_scores = [row["best_within_doc_resolution"] for row in per_doc if row["best_within_doc_resolution"] is not None]
    matched_within_doc_segment_scores = [
        row["best_within_doc_segment_resolution"] for row in per_doc if row["best_within_doc_segment_resolution"] is not None
    ]
    matched_combined_scores = [row["best_combined_resolution"] for row in per_doc if row["best_combined_resolution"] is not None]
    matched_segment_combined_scores = [
        row["best_segment_combined_resolution"] for row in per_doc if row["best_segment_combined_resolution"] is not None
    ]
    coverage = (sum(1 for row in per_doc if row["matched"]) / len(per_doc)) if per_doc else 0.0
    strict_doc_resolution = min(matched_doc_scores) if len(matched_doc_scores) == len(per_doc) and per_doc else 0.0
    strict_line_resolution = min(matched_line_scores) if len(matched_line_scores) == len(per_doc) and per_doc else 0.0
    strict_within_doc_resolution = (
        min(matched_within_doc_scores) if len(matched_within_doc_scores) == len(per_doc) and per_doc else 0.0
    )
    strict_within_doc_segment_resolution = (
        min(matched_within_doc_segment_scores)
        if len(matched_within_doc_segment_scores) == len(per_doc) and per_doc
        else 0.0
    )
    strict_combined_resolution = (
        min(matched_combined_scores) if len(matched_combined_scores) == len(per_doc) and per_doc else 0.0
    )
    strict_segment_combined_resolution = (
        min(matched_segment_combined_scores)
        if len(matched_segment_combined_scores) == len(per_doc) and per_doc
        else 0.0
    )
    latest_context_retention = (
        sum(1 for row in per_doc if row["retained_in_latest_context"]) / len(per_doc)
        if per_doc
        else 0.0
    )

    return {
        "query_id": qid,
        "is_correct": result.get("is_correct"),
        "gold_answer": item.get("answer"),
        "predicted_answer": result.get("final_text"),
        "observation_count": len(observations),
        "gold_doc_count": len(per_doc),
        "evidence_doc_coverage": coverage,
        "strict_doc_resolution": strict_doc_resolution,
        "strict_corpus_line_resolution": strict_line_resolution,
        "strict_within_doc_resolution": strict_within_doc_resolution,
        "strict_within_doc_segment_resolution": strict_within_doc_segment_resolution,
        "strict_combined_resolution": strict_combined_resolution,
        "strict_segment_combined_resolution": strict_segment_combined_resolution,
        "avg_doc_resolution": (sum(matched_doc_scores) / len(matched_doc_scores)) if matched_doc_scores else 0.0,
        "avg_corpus_line_resolution": (sum(matched_line_scores) / len(matched_line_scores)) if matched_line_scores else 0.0,
        "avg_within_doc_resolution": (
            (sum(matched_within_doc_scores) / len(matched_within_doc_scores)) if matched_within_doc_scores else 0.0
        ),
        "avg_within_doc_segment_resolution": (
            (sum(matched_within_doc_segment_scores) / len(matched_within_doc_segment_scores))
            if matched_within_doc_segment_scores
            else 0.0
        ),
        "avg_combined_resolution": (
            (sum(matched_combined_scores) / len(matched_combined_scores)) if matched_combined_scores else 0.0
        ),
        "avg_segment_combined_resolution": (
            (sum(matched_segment_combined_scores) / len(matched_segment_combined_scores))
            if matched_segment_combined_scores
            else 0.0
        ),
        "latest_context_evidence_retention": latest_context_retention,
        "runtime_context_level": (
            read_json(query_dir.parent / "config.json").get("runtime_context_level")
            if (query_dir.parent / "config.json").exists()
            else None
        ),
        "per_doc": per_doc,
        "sample_observations": [
            {
                "index": obs.index,
                "tool_name": obs.tool_name,
                "command": obs.command,
                "read_path": obs.read_path,
                "candidate_doc_count": obs.candidate_doc_count,
                "candidate_line_count": obs.candidate_line_count,
                "matched_docids": sorted(obs.matched_docs.keys()),
                "duration_ms": obs.duration_ms,
            }
            for obs in observations
            if obs.matched_docs
        ][:10],
    }


def aggregate_query_summaries(query_summaries: Sequence[Dict[str, Any]], corpus_stats: CorpusStats, output_root: Path) -> Dict[str, Any]:
    total = len(query_summaries)
    correct = [row for row in query_summaries if row.get("is_correct") is True]
    incorrect = [row for row in query_summaries if row.get("is_correct") is False]

    def avg(rows: Sequence[Dict[str, Any]], key: str) -> float:
        if not rows:
            return 0.0
        return sum(float(row.get(key, 0.0) or 0.0) for row in rows) / len(rows)

    hardest = sorted(
        query_summaries,
        key=lambda row: (
            float(row.get("strict_segment_combined_resolution", 0.0) or 0.0),
            float(row.get("evidence_doc_coverage", 0.0)),
        ),
    )[:5]

    return {
        "run_dir": str(output_root.resolve()),
        "corpus_stats": {
            "total_docs": corpus_stats.total_docs,
            "total_lines": corpus_stats.total_lines,
        },
        "counts": {
            "queries": total,
            "correct": len(correct),
            "incorrect": len(incorrect),
        },
        "averages": {
            "evidence_doc_coverage": avg(query_summaries, "evidence_doc_coverage"),
            "strict_doc_resolution": avg(query_summaries, "strict_doc_resolution"),
            "strict_corpus_line_resolution": avg(query_summaries, "strict_corpus_line_resolution"),
            "strict_within_doc_resolution": avg(query_summaries, "strict_within_doc_resolution"),
            "strict_within_doc_segment_resolution": avg(query_summaries, "strict_within_doc_segment_resolution"),
            "strict_combined_resolution": avg(query_summaries, "strict_combined_resolution"),
            "strict_segment_combined_resolution": avg(query_summaries, "strict_segment_combined_resolution"),
            "avg_doc_resolution": avg(query_summaries, "avg_doc_resolution"),
            "avg_within_doc_segment_resolution": avg(query_summaries, "avg_within_doc_segment_resolution"),
            "avg_segment_combined_resolution": avg(query_summaries, "avg_segment_combined_resolution"),
            "latest_context_evidence_retention": avg(query_summaries, "latest_context_evidence_retention"),
            "correct_strict_within_doc_resolution": avg(correct, "strict_within_doc_resolution"),
            "incorrect_strict_within_doc_resolution": avg(incorrect, "strict_within_doc_resolution"),
            "correct_avg_segment_combined_resolution": avg(correct, "avg_segment_combined_resolution"),
            "incorrect_avg_segment_combined_resolution": avg(incorrect, "avg_segment_combined_resolution"),
        },
        "lowest_strict_within_doc_resolution": [
            {
                "query_id": row["query_id"],
                "is_correct": row.get("is_correct"),
                "strict_within_doc_resolution": row.get("strict_within_doc_resolution"),
                "strict_segment_combined_resolution": row.get("strict_segment_combined_resolution"),
                "evidence_doc_coverage": row.get("evidence_doc_coverage"),
            }
            for row in hardest
        ],
    }


def render_markdown(report: Dict[str, Any]) -> str:
    agg = report["aggregate"]
    corpus = agg["corpus_stats"]
    averages = agg["averages"]
    lines = [
        "# Resolution Analysis",
        "",
        f"- Run dir: `{agg['run_dir']}`",
        f"- Queries analyzed: {agg['counts']['queries']}",
        f"- Correct / incorrect: {agg['counts']['correct']} / {agg['counts']['incorrect']}",
        f"- Corpus docs: {corpus['total_docs']}",
        f"- Corpus lines: {corpus['total_lines'] if corpus['total_lines'] is not None else 'not computed in fast mode'}",
        "",
        "## Aggregate Metrics",
        "",
        f"- Avg evidence-doc coverage: {averages['evidence_doc_coverage']:.3f}",
        f"- Avg strict doc resolution: {averages['strict_doc_resolution']:.3f}",
        f"- Avg strict corpus-line resolution: {averages['strict_corpus_line_resolution']:.3f}",
        f"- Avg strict within-doc resolution: {averages['strict_within_doc_resolution']:.3f}",
        f"- Avg strict within-doc segment resolution: {averages['strict_within_doc_segment_resolution']:.3f}",
        f"- Avg strict combined resolution: {averages['strict_combined_resolution']:.3f}",
        f"- Avg strict segment-combined resolution: {averages['strict_segment_combined_resolution']:.3f}",
        f"- Avg doc resolution (matched-doc average): {averages['avg_doc_resolution']:.3f}",
        f"- Avg within-doc segment resolution (matched-doc average): {averages['avg_within_doc_segment_resolution']:.3f}",
        f"- Avg segment-combined resolution (matched-doc average): {averages['avg_segment_combined_resolution']:.3f}",
        f"- Avg latest-context evidence retention: {averages['latest_context_evidence_retention']:.3f}",
        f"- Correct avg strict within-doc resolution: {averages['correct_strict_within_doc_resolution']:.3f}",
        f"- Incorrect avg strict within-doc resolution: {averages['incorrect_strict_within_doc_resolution']:.3f}",
        f"- Correct avg segment-combined resolution: {averages['correct_avg_segment_combined_resolution']:.3f}",
        f"- Incorrect avg segment-combined resolution: {averages['incorrect_avg_segment_combined_resolution']:.3f}",
        "",
        "## Lowest Strict Within-Doc Resolution",
        "",
        "| Query ID | Correct | Strict Within-Doc | Strict Segment-Combined | Coverage |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in agg["lowest_strict_within_doc_resolution"]:
        lines.append(
            f"| {row['query_id']} | {row['is_correct']} | {float(row['strict_within_doc_resolution'] or 0.0):.3f} | "
            f"{float(row['strict_segment_combined_resolution'] or 0.0):.3f} | {float(row['evidence_doc_coverage'] or 0.0):.3f} |"
        )
    lines.append("")
    lines.append("## Per-Query Snapshot")
    lines.append("")
    lines.append("| Query ID | Correct | Coverage | Strict Doc | Strict Within-Doc | Strict Segment | Strict Segment-Combined | Retention |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in report["queries"]:
        lines.append(
            f"| {row['query_id']} | {row.get('is_correct')} | {float(row['evidence_doc_coverage']):.3f} | "
            f"{float(row['strict_doc_resolution']):.3f} | {float(row['strict_within_doc_resolution']):.3f} | "
            f"{float(row['strict_within_doc_segment_resolution']):.3f} | {float(row['strict_segment_combined_resolution']):.3f} | "
            f"{float(row['latest_context_evidence_retention']):.3f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_root = args.output_root.resolve()
    if not output_root.exists():
        raise FileNotFoundError(f"Output root does not exist: {output_root}")

    corpus_dir = infer_corpus_dir(output_root, args.corpus_dir)
    corpus_stats = build_corpus_stats(corpus_dir)

    query_summaries = [
        summarize_query(
            query_dir=query_dir,
            corpus_dir=corpus_dir,
            corpus_stats=corpus_stats,
            min_snippet_chars=args.min_snippet_chars,
            segment_chars=args.segment_chars,
        )
        for query_dir in iter_query_dirs(output_root)
    ]
    query_summaries.sort(key=lambda row: row["query_id"])

    report = {
        "aggregate": aggregate_query_summaries(query_summaries, corpus_stats, output_root),
        "queries": query_summaries,
    }

    json_path = args.write_json or (output_root / "resolution_analysis.json")
    md_path = args.write_md or (output_root / "resolution_analysis.md")
    write_json(json_path, report)
    write_text(md_path, render_markdown(report))

    print(f"Wrote JSON analysis to {json_path}")
    print(f"Wrote Markdown summary to {md_path}")
    print(json.dumps(report["aggregate"]["averages"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
