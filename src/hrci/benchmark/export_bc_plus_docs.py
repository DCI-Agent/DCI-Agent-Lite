#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_DIR = REPO_ROOT / "corpus" / "bc-plus-corpus" / "data"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "corpus" / "bc plus docs"

TITLE_RE = re.compile(r"(?mi)^title:\s*(.+?)\s*$")
INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE_RE = re.compile(r"\s+")
MAX_STEM_LEN = 140


def extract_title(text: str) -> str | None:
    match = TITLE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def sanitize_name(value: str, fallback: str) -> str:
    value = INVALID_CHARS_RE.sub(" ", value)
    value = WHITESPACE_RE.sub(" ", value).strip().strip(".")
    return value or fallback


def get_domain(url: str) -> str:
    hostname = urlparse(url).hostname or "unknown-domain"
    return sanitize_name(hostname.lower(), "unknown-domain")


def build_filename(title: str | None, url: str, docid: str) -> str:
    parsed = urlparse(url)
    path_name = Path(parsed.path).name
    fallback = path_name or f"doc-{docid}"
    stem = title or fallback
    stem = sanitize_name(stem, f"doc-{docid}")
    if len(stem) > MAX_STEM_LEN:
        stem = stem[:MAX_STEM_LEN].rstrip(" .")
    if not stem:
        stem = f"doc-{docid}"
    return f"{stem}.txt"


def unique_path(path: Path, docid: str, text: str) -> Path:
    if not path.exists():
        return path
    try:
        if path.read_text(encoding="utf-8") == text:
            return path
    except OSError:
        pass
    stem = path.stem
    suffix = path.suffix
    candidate = path.with_name(f"{stem}__docid_{docid}{suffix}")
    if not candidate.exists():
        return candidate
    try:
        if candidate.read_text(encoding="utf-8") == text:
            return candidate
    except OSError:
        pass
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}__docid_{docid}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        try:
            if candidate.read_text(encoding="utf-8") == text:
                return candidate
        except OSError:
            pass
        counter += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export the BrowseComp Plus parquet corpus into a domain-first folder layout. "
            "Each output file is named after the document title when available."
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing BrowseComp Plus parquet shards.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Target directory for the exported text files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_files = sorted(source_dir.glob("*.parquet"))
    if not parquet_files:
        raise SystemExit(f"No parquet files found under {source_dir}")
    total = 0

    for parquet_file in parquet_files:
        pf = pq.ParquetFile(parquet_file)
        for row_group_idx in range(pf.num_row_groups):
            table = pf.read_row_group(row_group_idx, columns=["docid", "text", "url"])
            for row in table.to_pylist():
                docid = str(row["docid"])
                text = row["text"]
                url = row["url"]

                domain = get_domain(url)
                title = extract_title(text)
                filename = build_filename(title, url, docid)

                target_dir = output_dir / domain
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = unique_path(target_dir / filename, docid, text)
                target_path.write_text(text, encoding="utf-8")
                total += 1

        print(f"exported {parquet_file.name}")

    print(f"done: exported {total} documents to {output_dir}")


if __name__ == "__main__":
    main()
