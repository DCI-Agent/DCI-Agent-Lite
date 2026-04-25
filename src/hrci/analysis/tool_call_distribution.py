"""
Tool-call count distribution: correct vs incorrect, per dataset.
Mirrors the layout of turn_distribution.png:
  Row 1 — overlapping histograms (green=correct, red=incorrect) + mean dashed lines
  Row 2 — box plots (correct vs incorrect)
"""

import glob
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from scipy import stats as sp_stats
from ._common import ANALYSIS_BASE, ensure_figure_dir

BASE = ANALYSIS_BASE

# ── dataset registry ──────────────────────────────────────────────────────────

QA_DATASETS = [
    ("eval_logs/claude_code/qa/musique_dev_sample50",         "musique",   "qa"),
    ("eval_logs/claude_code/qa/hotpotqa_dev_sample50",        "hotpotqa",  "qa"),
    ("eval_logs/claude_code/qa/2wikimultihopqa_dev_sample50", "2wiki",     "qa"),
    ("eval_logs/claude_code/qa/bamboogle_test_sample50",      "bamboogle", "qa"),
    ("eval_logs/claude_code/qa/nq_test_sample50",             "nq",        "qa"),
    ("eval_logs/claude_code/qa/triviaqa_test_sample50",       "triviaqa",  "qa"),
]

IR_DATASETS = [
    ("eval_logs/claude_code/ir/bright_biology",        "biology",  "ir"),
    ("eval_logs/claude_code/ir/bright_robotics",       "robotics", "ir"),
]

ALL_DATASETS = QA_DATASETS + IR_DATASETS

COLOR_CORRECT   = "#2ca02c"
COLOR_INCORRECT = "#d62728"


# ── data loading ──────────────────────────────────────────────────────────────

def count_tool_calls(jsonl_path: Path) -> int:
    with open(jsonl_path) as f:
        d = json.loads(f.read())
    return sum(
        1
        for m in d.get("messages", [])
        if m.get("type") == "assistant"
        for b in m.get("message", {}).get("content", [])
        if isinstance(b, dict) and b.get("type") == "tool_use"
    )


def load_dataset(rel_dir: str, ds_type: str) -> tuple[list[int], list[int]]:
    """Return (correct_counts, incorrect_counts)."""
    root = BASE / rel_dir

    # Build qid → correct mapping
    if ds_type == "qa":
        eval_file = root / "evaluated.jsonl"
        correct_map: dict[str, bool] = {}
        with open(eval_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                correct_map[r["qid"]] = bool(r.get("correct", False))
    else:  # ir
        eval_file = root / "evaluated_ir.jsonl"
        correct_map = {}
        with open(eval_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                # treat ndcg@10 > 0.5 as "correct"
                correct_map[r["qid"]] = r.get("ndcg@10", 0.0) > 0.5

    correct_counts, incorrect_counts = [], []
    for qid, is_correct in correct_map.items():
        raw_path = root / f"{qid}.jsonl"
        if not raw_path.exists():
            continue
        n = count_tool_calls(raw_path)
        if is_correct:
            correct_counts.append(n)
        else:
            incorrect_counts.append(n)

    return correct_counts, incorrect_counts


# ── plotting ──────────────────────────────────────────────────────────────────

def make_figure():
    n_ds = len(ALL_DATASETS)

    fig, axes = plt.subplots(
        2, n_ds,
        figsize=(n_ds * 3.2, 8),
        gridspec_kw={"hspace": 0.55, "wspace": 0.35},
    )

    fig.suptitle(
        "Tool-Call Count Distribution: Correct vs Incorrect",
        fontsize=14, fontweight="bold", y=1.01,
    )

    for col, (rel_dir, label, ds_type) in enumerate(ALL_DATASETS):
        correct, incorrect = load_dataset(rel_dir, ds_type)

        ax_hist = axes[0, col]
        ax_box  = axes[1, col]

        all_vals = correct + incorrect
        if not all_vals:
            ax_hist.set_visible(False)
            ax_box.set_visible(False)
            continue

        # ── histogram ────────────────────────────────────────────────────────
        x_max = max(all_vals)
        bins = np.linspace(0, x_max + 1, min(30, x_max + 2))

        ax_hist.hist(correct,   bins=bins, color=COLOR_CORRECT,   alpha=0.55,
                     label=f"Correct (n={len(correct)})",   edgecolor="none")
        ax_hist.hist(incorrect, bins=bins, color=COLOR_INCORRECT, alpha=0.55,
                     label=f"Incorrect (n={len(incorrect)})", edgecolor="none")

        # mean dashed lines
        if correct:
            m_c = np.mean(correct)
            ax_hist.axvline(m_c, color=COLOR_CORRECT,   linestyle="--", linewidth=1.2)
        if incorrect:
            m_i = np.mean(incorrect)
            ax_hist.axvline(m_i, color=COLOR_INCORRECT, linestyle="--", linewidth=1.2)

        ax_hist.set_title(label, fontsize=9, fontweight="bold")
        ax_hist.set_xlabel("# tool calls", fontsize=7.5)
        ax_hist.set_ylabel("# questions",  fontsize=7.5)
        ax_hist.tick_params(labelsize=7)
        ax_hist.spines["top"].set_visible(False)
        ax_hist.spines["right"].set_visible(False)
        ax_hist.legend(fontsize=6, loc="upper right", framealpha=0.8)

        # ── box plot ─────────────────────────────────────────────────────────
        data_to_plot = [correct, incorrect] if incorrect else [correct]
        tick_labels  = (
            [f"Correct\n(n={len(correct)})", f"Incorrect\n(n={len(incorrect)})"]
            if incorrect else [f"Correct\n(n={len(correct)})"]
        )
        box_colors = [COLOR_CORRECT, COLOR_INCORRECT][: len(data_to_plot)]

        bp = ax_box.boxplot(
            data_to_plot,
            patch_artist=True,
            widths=0.5,
            medianprops=dict(color="white", linewidth=2),
        )
        for patch, c in zip(bp["boxes"], box_colors):
            patch.set_facecolor(c)
            patch.set_alpha(0.75)
        for element in ("whiskers", "caps", "fliers"):
            for line in bp[element]:
                line.set_color("#555555")
                line.set_linewidth(0.8)

        # Mann-Whitney U annotation
        if correct and incorrect:
            u_stat, p_val = sp_stats.mannwhitneyu(
                correct, incorrect, alternative="two-sided"
            )
            mean_txt = (
                f"Correct μ={np.mean(correct):.1f}±{np.std(correct):.1f}\n"
                f"Incorrect μ={np.mean(incorrect):.1f}±{np.std(incorrect):.1f}"
            )
            ax_box.text(
                0.03, 0.97, mean_txt,
                transform=ax_box.transAxes,
                fontsize=6, va="top", color="#333333",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none"),
            )

        ax_box.set_title(f"Tool calls: Correct vs Incorrect", fontsize=7.5)
        ax_box.set_xticks(range(1, len(data_to_plot) + 1))
        ax_box.set_xticklabels(tick_labels, fontsize=7)
        ax_box.set_ylabel("# tool calls", fontsize=7.5)
        ax_box.tick_params(labelsize=7)
        ax_box.spines["top"].set_visible(False)
        ax_box.spines["right"].set_visible(False)

    out_dir = ensure_figure_dir()
    out = out_dir / "tool_call_distribution.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    make_figure()
