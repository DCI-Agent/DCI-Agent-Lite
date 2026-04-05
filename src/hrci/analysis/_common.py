from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_BASE = Path(os.environ.get("HRCI_ANALYSIS_BASE", REPO_ROOT / "cc-analysis"))
FIGURE_ROOT = Path(os.environ.get("HRCI_FIGURE_ROOT", REPO_ROOT / "outputs" / "figures"))


def ensure_figure_dir() -> Path:
    out_dir = FIGURE_ROOT / "claude_code"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
