#!/usr/bin/env python3
"""Download DCI-Agent/dci-bench benchmark datasets from HuggingFace."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser(description="Download DCI-Agent/dci-bench datasets")
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=Path("data/dci-bench"),
        help="Local directory to save datasets (default: data/dci-bench/)",
    )
    args = parser.parse_args()

    repo_id = "DCI-Agent/dci-bench"
    args.local_dir.mkdir(parents=True, exist_ok=True)

    print(f"==> Downloading {repo_id}...")
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=str(args.local_dir),
            local_dir_use_symlinks=False,
        )
        print(f"\n==> Downloaded successfully to {args.local_dir}")
    except Exception as e:
        print(f"\nWARN: Download failed: {e}", file=sys.stderr)
        print("      Make sure you are logged in: huggingface-cli login", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
