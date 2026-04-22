#!/usr/bin/env python3
"""Download DCI-Agent/corpus subsets from HuggingFace."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


SUBSETS = [
    "browsecomp_plus",
    "bright_biology",
    "bright_earth_science",
    "bright_economics",
    "bright_robotics",
    "wiki",
]


def download_subset(repo_id: str, subset: str, local_dir: Path) -> bool:
    print(f"  -> {subset}")
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=str(local_dir),
            allow_patterns=[f"{subset}/*"],
            local_dir_use_symlinks=False,
        )
        print(f"     Done: {local_dir / subset}")
        return True
    except Exception as e:
        print(f"     Error: {e}", file=sys.stderr)
        return False


def export_browsecomp_plus(local_dir: Path) -> None:
    bc_plus_dir = local_dir / "browsecomp_plus"
    bc_plus_docs = local_dir / "bc_plus_docs"
    if not bc_plus_dir.exists():
        print(f"     Skip export: {bc_plus_dir} not found")
        return
    print(f"\n  -> Exporting BrowseComp-Plus to {bc_plus_docs}")
    subprocess.run(
        [
            sys.executable, "-m", "hrci.benchmark.export_bc_plus_docs",
            "--source-dir", str(bc_plus_dir),
            "--output-dir", str(bc_plus_docs),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download DCI-Agent/corpus datasets")
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=Path("corpus"),
        help="Local directory to save datasets (default: corpus/)",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip exporting browsecomp_plus to bc_plus_docs",
    )
    args = parser.parse_args()

    repo_id = "DCI-Agent/corpus"
    args.local_dir.mkdir(parents=True, exist_ok=True)

    failed = []
    for subset in SUBSETS:
        if not download_subset(repo_id, subset, args.local_dir):
            failed.append(subset)

    if failed:
        print(f"\nWARN: Failed to download {len(failed)} subset(s): {', '.join(failed)}")
        print("      Make sure you are logged in: huggingface-cli login")
        sys.exit(1)

    if not args.skip_export:
        export_browsecomp_plus(args.local_dir)

    print("\n==> All datasets downloaded successfully!")


if __name__ == "__main__":
    main()
