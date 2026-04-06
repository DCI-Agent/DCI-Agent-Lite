import argparse
import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set


DEFAULT_SAMPLE_FILE = Path("data/bcplus_sampled_100_qa.jsonl")
DEFAULT_SOURCE_FILE = Path("data/bclpus/decrypted.jsonl")
DEFAULT_OUTPUT_FILE = Path("data/bcplus_sampled_100_qa_with_gold_doc.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the fixed 100-question BrowseComp-Plus QA set by query_id, "
            "including the original gold_docs from the decrypted source dataset."
        )
    )
    parser.add_argument(
        "--sample-file",
        type=Path,
        default=DEFAULT_SAMPLE_FILE,
        help=f"JSONL file containing the sampled query ids. Default: {DEFAULT_SAMPLE_FILE}",
    )
    parser.add_argument(
        "--source-file",
        type=Path,
        default=DEFAULT_SOURCE_FILE,
        help=(
            "Decrypted BrowseComp-Plus source JSONL. "
            f"Default: {DEFAULT_SOURCE_FILE}"
        ),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output JSONL file for the extracted fixed set. Default: {DEFAULT_OUTPUT_FILE}",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=None,
        help=(
            "Optional list of fields to keep from the source rows. "
            "By default the full matched source row is written."
        ),
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc


def load_sample_query_ids(sample_file: Path) -> List[str]:
    query_ids: List[str] = []
    seen: Set[str] = set()
    for row in load_jsonl(sample_file):
        query_id = str(row["query_id"])
        if query_id in seen:
            raise ValueError(f"Duplicate query_id {query_id} found in {sample_file}")
        query_ids.append(query_id)
        seen.add(query_id)
    return query_ids


def index_source_rows(source_file: Path, target_ids: Set[str]) -> Dict[str, dict]:
    matched_rows: Dict[str, dict] = {}
    for row in load_jsonl(source_file):
        query_id = str(row["query_id"])
        if query_id not in target_ids:
            continue
        if query_id in matched_rows:
            raise ValueError(
                f"Duplicate query_id {query_id} found in source file {source_file}"
            )
        matched_rows[query_id] = row
    return matched_rows


def project_fields(row: dict, fields: Optional[List[str]]) -> dict:
    if not fields:
        return row
    return {field: row[field] for field in fields if field in row}


def main() -> None:
    args = parse_args()

    if not args.sample_file.exists():
        raise FileNotFoundError(f"Sample file does not exist: {args.sample_file}")
    if not args.source_file.exists():
        raise FileNotFoundError(f"Source file does not exist: {args.source_file}")

    query_ids = load_sample_query_ids(args.sample_file)
    matched_rows = index_source_rows(args.source_file, set(query_ids))

    missing_ids = [query_id for query_id in query_ids if query_id not in matched_rows]
    if missing_ids:
        missing_preview = ", ".join(missing_ids[:10])
        raise ValueError(
            f"Missing {len(missing_ids)} query ids from source file: {missing_preview}"
        )

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    with args.output_file.open("w", encoding="utf-8") as handle:
        for query_id in query_ids:
            row = matched_rows[query_id]
            output_row = project_fields(row, args.fields)
            json.dump(output_row, handle, ensure_ascii=False)
            handle.write("\n")

    print(
        "Wrote "
        f"{len(query_ids)} records to {args.output_file} "
        f"from {args.source_file} using ids from {args.sample_file}"
    )


if __name__ == "__main__":
    main()
