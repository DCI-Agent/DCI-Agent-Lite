#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath

import pyarrow.parquet as pq
from tqdm import tqdm


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "corpus" / "bright_corpus_raw"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "corpus" / "bright_corpus"
BRIGHT_SUBSETS = ("biology", "earth_science", "economics", "robotics")
COMPLETE_MARKER = ".dci_export_complete"


def safe_relative_path(value: str) -> Path:
    rel = PurePosixPath(value)
    if rel.is_absolute() or not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError(f"Unsafe BRIGHT document id: {value!r}")
    return Path(*rel.parts)


def export_subset(source_dir: Path, output_dir: Path) -> int:
    parquet_files = sorted(source_dir.glob("*.parquet"))
    if not parquet_files:
        raise SystemExit(f"No parquet files found under {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    marker_path = output_dir / COMPLETE_MARKER
    marker_path.unlink(missing_ok=True)
    total_docs = sum(pq.ParquetFile(parquet_file).metadata.num_rows for parquet_file in parquet_files)
    exported = 0

    progress = tqdm(
        total=total_docs,
        desc=f"Exporting BRIGHT docs from {source_dir.name}",
        unit="doc",
    )
    try:
        for parquet_file in parquet_files:
            pf = pq.ParquetFile(parquet_file)
            for row_group_idx in range(pf.num_row_groups):
                table = pf.read_row_group(row_group_idx, columns=["id", "content"])
                for row in table.to_pylist():
                    relative_path = safe_relative_path(str(row["id"]))
                    content = row["content"] or ""
                    target_path = output_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    if not target_path.exists() or target_path.read_text(encoding="utf-8") != content:
                        target_path.write_text(content, encoding="utf-8")
                    exported += 1
                    progress.update(1)

            progress.write(f"exported {parquet_file.name}")
    finally:
        progress.close()

    print(f"done: exported {exported} documents to {output_dir}")
    marker_path.write_text(f"{exported}\n", encoding="utf-8")
    return exported


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export BRIGHT parquet corpora into document folders. "
            "Document ids are preserved as relative paths for benchmark matching."
        )
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Directory containing BRIGHT subset directories.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Target directory for exported BRIGHT subset directories.",
    )
    parser.add_argument(
        "--subset",
        action="append",
        choices=BRIGHT_SUBSETS,
        help="BRIGHT subset to export. May be supplied multiple times. Defaults to all subsets.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    subsets = tuple(args.subset or BRIGHT_SUBSETS)

    total = 0
    for subset in subsets:
        total += export_subset(source_root / subset, output_root / subset)
    print(f"\n==> BRIGHT export complete: {total} documents")


if __name__ == "__main__":
    main()
