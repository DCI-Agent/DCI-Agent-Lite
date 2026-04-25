#!/usr/bin/env python3
"""Download DCI-Agent/corpus subsets from HuggingFace with idempotency and path aliasing."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


# (repo_subset_name, local_target_path_under_corpus/)
SUBSET_ALIASES: list[tuple[str, str]] = [
    ("browsecomp_plus", "browsecomp_plus"),
    ("bright_biology", "bright_corpus/biology"),
    ("bright_earth_science", "bright_corpus/earth_science"),
    ("bright_economics", "bright_corpus/economics"),
    ("bright_robotics", "bright_corpus/robotics"),
    ("wiki", "wiki_corpus"),
]


def is_download_complete(target_dir: Path) -> bool:
    """Check if target directory exists and contains at least one file."""
    if not target_dir.exists():
        return False
    for child in target_dir.rglob("*"):
        if child.is_file():
            return True
    return False


def download_subset(repo_id: str, subset: str, target_dir: Path) -> bool:
    if is_download_complete(target_dir):
        print(f"  -> {subset}  (already present at {target_dir})")
        return True

    print(f"  -> {subset}")
    temp_dir = target_dir.parent / f".tmp_{subset.replace('/', '_')}"
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=str(temp_dir),
            allow_patterns=[f"{subset}/*"],
        )
    except Exception as e:
        print(f"     Error downloading {subset}: {e}", file=sys.stderr)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    src_dir = temp_dir / subset
    if not src_dir.exists():
        # allow_patterns may have skipped everything; clean up and mark as failed
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"     Error: subset '{subset}' not found in repo (no files matched)", file=sys.stderr)
        return False

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_dir), str(target_dir))
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"     Done: {target_dir}")
    return True


def export_browsecomp_plus(local_dir: Path) -> None:
    bc_plus_dir = local_dir / "browsecomp_plus"
    bc_plus_docs = local_dir / "bc_plus_docs"
    if not bc_plus_dir.exists():
        print(f"     Skip export: {bc_plus_dir} not found")
        return
    if bc_plus_docs.exists() and any(bc_plus_docs.iterdir()):
        print(f"     Skip export: {bc_plus_docs} already present")
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
    for subset, alias in SUBSET_ALIASES:
        target_dir = args.local_dir / alias
        if not download_subset(repo_id, subset, target_dir):
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
