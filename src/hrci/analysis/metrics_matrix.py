"""
Claude Code Metrics Matrix — all datasets.

Layout (3 rows):
  Row 1 : Accuracy vs Latency  |  Accuracy vs Cost  |  Latency vs Cost (bubble)
  Row 2 : Accuracy ranking     |  Latency dist       |  Cost dist
  Row 3 : Token Breakdown (wide, spans all columns)
"""

import glob
import json
import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from ._common import ANALYSIS_BASE, ensure_figure_dir

# ── dataset registry ──────────────────────────────────────────────────────────

BASE = str(ANALYSIS_BASE)

QA_DATASETS = {
    "musique_dev_sample50":         "musique",
    "hotpotqa_dev_sample50":        "hotpotqa",
    "2wikimultihopqa_dev_sample50": "2wiki",
    "bamboogle_test_sample50":      "bamboogle",
    "nq_test_sample50":             "nq",
    "triviaqa_test_sample50":       "triviaqa",
}

IR_DATASETS = {
    "bright_biology":        "biology",
    "bright_robotics":       "robotics",
}

BROWSECOMP_DIR = "eval_logs/claude_code/browsecomp-plus_full"
BROWSECOMP_LABEL = "browsecomp+"

# Colour per dataset (deterministic, visually distinct)
PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#393b79",
]


# ── data loading ──────────────────────────────────────────────────────────────

def _last_msg(jsonl_path: str) -> dict:
    """Return the last message from a single-line JSONL conversation file."""
    with open(jsonl_path) as f:
        line = f.read().strip()
    if not line:
        return {}
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return {}
    msgs = d.get("messages", [])
    return msgs[-1] if msgs else {}


def _tokens(last_msg: dict) -> dict:
    """Extract token counts from a result message's usage field."""
    usage = last_msg.get("usage", {})
    return {
        "input":         usage.get("input_tokens", 0),
        "output":        usage.get("output_tokens", 0),
        "cache_write":   usage.get("cache_creation_input_tokens", 0),
        "cache_read":    usage.get("cache_read_input_tokens", 0),
    }


def load_qa(dataset_dir: str, label: str) -> dict:
    """Load QA dataset metrics."""
    root = os.path.join(BASE, "eval_logs", "claude_code", "qa", dataset_dir)
    eval_path = os.path.join(root, "evaluated.jsonl")

    # Build qid → evaluated record
    eval_map: dict[str, dict] = {}
    with open(eval_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                eval_map[r["qid"]] = r
            except (json.JSONDecodeError, KeyError):
                pass

    costs, latencies, accuracies = [], [], []
    tok_input, tok_output, tok_cw, tok_cr = [], [], [], []

    for qid, ev in eval_map.items():
        raw_path = os.path.join(root, f"{qid}.jsonl")
        if not os.path.exists(raw_path):
            continue
        lm = _last_msg(raw_path)
        dur_s = lm.get("duration_ms", 0) / 1000.0

        costs.append(ev.get("total_cost_usd", lm.get("total_cost_usd", 0)))
        latencies.append(dur_s)
        accuracies.append(1.0 if ev.get("correct") else 0.0)
        tok = _tokens(lm)
        tok_input.append(tok["input"])
        tok_output.append(tok["output"])
        tok_cw.append(tok["cache_write"])
        tok_cr.append(tok["cache_read"])

    return dict(
        label=label,
        costs=costs,
        latencies=latencies,
        accuracies=accuracies,          # 0/1 per question
        acc_mean=float(np.mean(accuracies)) * 100 if accuracies else None,
        acc_type="Accuracy (%)",
        tok_input=tok_input,
        tok_output=tok_output,
        tok_cw=tok_cw,
        tok_cr=tok_cr,
    )


def load_ir(dataset_dir: str, label: str) -> dict:
    """Load IR dataset metrics (uses ndcg@10 as accuracy proxy)."""
    root = os.path.join(BASE, "eval_logs", "claude_code", "ir", dataset_dir)
    eval_path = os.path.join(root, "evaluated_ir.jsonl")

    eval_map: dict[str, dict] = {}
    with open(eval_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                eval_map[r["qid"]] = r
            except (json.JSONDecodeError, KeyError):
                pass

    costs, latencies, accuracies = [], [], []
    tok_input, tok_output, tok_cw, tok_cr = [], [], [], []

    for qid, ev in eval_map.items():
        raw_path = os.path.join(root, f"{qid}.jsonl")
        if not os.path.exists(raw_path):
            continue
        lm = _last_msg(raw_path)
        dur_s = lm.get("duration_ms", 0) / 1000.0

        costs.append(ev.get("total_cost_usd", lm.get("total_cost_usd", 0)))
        latencies.append(dur_s)
        accuracies.append(ev.get("ndcg@10", 0.0))  # already in [0,1]
        tok = _tokens(lm)
        tok_input.append(tok["input"])
        tok_output.append(tok["output"])
        tok_cw.append(tok["cache_write"])
        tok_cr.append(tok["cache_read"])

    return dict(
        label=label,
        costs=costs,
        latencies=latencies,
        accuracies=accuracies,
        acc_mean=float(np.mean(accuracies)) * 100 if accuracies else None,
        acc_type="nDCG@10 (%)",
        tok_input=tok_input,
        tok_output=tok_output,
        tok_cw=tok_cw,
        tok_cr=tok_cr,
    )


def load_browsecomp(label: str, acc_mean: float = 79.95) -> dict:
    """Load browsecomp-plus metrics. acc_mean is provided externally."""
    root = os.path.join(BASE, BROWSECOMP_DIR)
    raw_files = [
        p for p in glob.glob(os.path.join(root, "*.jsonl"))
    ]

    costs, latencies = [], []
    tok_input, tok_output, tok_cw, tok_cr = [], [], [], []

    for fp in raw_files:
        lm = _last_msg(fp)
        if not lm:
            continue
        dur_s = lm.get("duration_ms", 0) / 1000.0
        cost = lm.get("total_cost_usd", 0)
        costs.append(cost)
        latencies.append(dur_s)
        tok = _tokens(lm)
        tok_input.append(tok["input"])
        tok_output.append(tok["output"])
        tok_cw.append(tok["cache_write"])
        tok_cr.append(tok["cache_read"])

    return dict(
        label=label,
        costs=costs,
        latencies=latencies,
        accuracies=[],
        acc_mean=acc_mean,
        acc_type="Accuracy (%)",
        tok_input=tok_input,
        tok_output=tok_output,
        tok_cw=tok_cw,
        tok_cr=tok_cr,
    )


def load_all() -> list[dict]:
    datasets = []
    for d, lbl in QA_DATASETS.items():
        datasets.append(load_qa(d, lbl))
    for d, lbl in IR_DATASETS.items():
        datasets.append(load_ir(d, lbl))
    datasets.append(load_browsecomp(BROWSECOMP_LABEL))
    return datasets


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_mean(lst):
    return float(np.mean(lst)) if lst else 0.0


# ── plotting ──────────────────────────────────────────────────────────────────

def make_figure(datasets: list[dict]):
    n_ds = len(datasets)
    colors = {ds["label"]: PALETTE[i % len(PALETTE)] for i, ds in enumerate(datasets)}

    # Summary stats per dataset
    stats = []
    for ds in datasets:
        stats.append(dict(
            label=ds["label"],
            cost_mean=_safe_mean(ds["costs"]),
            cost_all=ds["costs"],
            lat_mean=_safe_mean(ds["latencies"]),
            lat_all=ds["latencies"],
            acc_mean=ds["acc_mean"],
            acc_all=ds["accuracies"],
            tok_input=_safe_mean(ds["tok_input"]),
            tok_output=_safe_mean(ds["tok_output"]),
            tok_cw=_safe_mean(ds["tok_cw"]),
            tok_cr=_safe_mean(ds["tok_cr"]),
            n=len(ds["costs"]),
        ))

    # ── figure setup ──────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 18))
    # 3 rows: row heights roughly equal; row 3 is token breakdown (shorter)
    gs = fig.add_gridspec(
        3, 3,
        height_ratios=[3, 3, 2.5],
        hspace=0.45,
        wspace=0.35,
    )

    ax_acc_lat = fig.add_subplot(gs[0, 0])   # Accuracy vs Latency
    ax_acc_cost = fig.add_subplot(gs[0, 1])  # Accuracy vs Cost
    ax_bubble = fig.add_subplot(gs[0, 2])    # Latency vs Cost (bubble = acc)

    ax_acc_rank = fig.add_subplot(gs[1, 0])  # Accuracy ranking
    ax_lat_dist = fig.add_subplot(gs[1, 1])  # Latency distribution
    ax_cost_dist = fig.add_subplot(gs[1, 2]) # Cost distribution

    ax_tok = fig.add_subplot(gs[2, :])       # Token Breakdown (wide)

    # datasets that have accuracy
    acc_stats = [s for s in stats if s["acc_mean"] is not None]

    # ── Row 1 : Scatter plots ─────────────────────────────────────────────────

    def _scatter(ax, xs, ys, xlabel, ylabel, title, annotate=True):
        for s in stats:
            x, y = xs(s), ys(s)
            if x is None or y is None:
                continue
            c = colors[s["label"]]
            ax.scatter(x, y, color=c, s=80, zorder=3)
            if annotate:
                ax.annotate(
                    s["label"], (x, y),
                    textcoords="offset points", xytext=(4, 4),
                    fontsize=7, color=c,
                )
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.3, linestyle="--")

    # Accuracy vs Latency
    _scatter(
        ax_acc_lat,
        xs=lambda s: s["lat_mean"],
        ys=lambda s: s["acc_mean"],
        xlabel="Latency per question (s)",
        ylabel="Accuracy (%)",
        title="Accuracy vs Latency",
    )

    # Accuracy vs Cost
    _scatter(
        ax_acc_cost,
        xs=lambda s: s["cost_mean"],
        ys=lambda s: s["acc_mean"],
        xlabel="Cost per question (USD)",
        ylabel="Accuracy (%)",
        title="Accuracy vs Cost",
    )

    # Latency vs Cost bubble (bubble size ∝ accuracy)
    for s in stats:
        c = colors[s["label"]]
        x, y = s["cost_mean"], s["lat_mean"]
        size = max(30, s["acc_mean"] * 5) if s["acc_mean"] is not None else 80
        ax_bubble.scatter(x, y, s=size, color=c, alpha=0.7, zorder=3)
        ax_bubble.annotate(
            s["label"], (x, y),
            textcoords="offset points", xytext=(4, 4),
            fontsize=7, color=c,
        )
    ax_bubble.set_xlabel("Cost per question (USD)", fontsize=9)
    ax_bubble.set_ylabel("Latency per question (s)", fontsize=9)
    ax_bubble.set_title(
        "Latency vs Cost\n(bubble ∝ accuracy)",
        fontsize=10, fontweight="bold",
    )
    ax_bubble.spines["top"].set_visible(False)
    ax_bubble.spines["right"].set_visible(False)
    ax_bubble.grid(True, alpha=0.3, linestyle="--")

    # ── Row 2 : Distribution plots ────────────────────────────────────────────

    # Accuracy ranking (horizontal bar)
    sorted_acc = sorted(acc_stats, key=lambda s: s["acc_mean"])
    labels_a = [s["label"] for s in sorted_acc]
    vals_a = [s["acc_mean"] for s in sorted_acc]
    bar_colors_a = [colors[lbl] for lbl in labels_a]
    bars = ax_acc_rank.barh(labels_a, vals_a, color=bar_colors_a)
    for bar, v in zip(bars, vals_a):
        ax_acc_rank.text(
            v + 0.5, bar.get_y() + bar.get_height() / 2,
            f"{v:.1f}%", va="center", fontsize=8,
        )
    ax_acc_rank.set_xlabel("Accuracy (%)", fontsize=9)
    ax_acc_rank.set_title("Accuracy ranking", fontsize=10, fontweight="bold")
    ax_acc_rank.spines["top"].set_visible(False)
    ax_acc_rank.spines["right"].set_visible(False)
    ax_acc_rank.set_xlim(0, max(vals_a) * 1.15 if vals_a else 100)

    # Latency distribution (box plot)
    lat_data = [s["lat_all"] for s in stats]
    lat_labels = [s["label"] for s in stats]
    bp1 = ax_lat_dist.boxplot(lat_data, vert=True, patch_artist=True, widths=0.6)
    for patch, lbl in zip(bp1["boxes"], lat_labels):
        patch.set_facecolor(colors[lbl])
        patch.set_alpha(0.7)
    ax_lat_dist.set_xticks(range(1, n_ds + 1))
    ax_lat_dist.set_xticklabels(lat_labels, rotation=35, ha="right", fontsize=7)
    ax_lat_dist.set_ylabel("Latency per question (s)", fontsize=9)
    ax_lat_dist.set_title("Latency distribution", fontsize=10, fontweight="bold")
    ax_lat_dist.spines["top"].set_visible(False)
    ax_lat_dist.spines["right"].set_visible(False)

    # Cost distribution (box plot)
    cost_data = [s["cost_all"] for s in stats]
    cost_labels = [s["label"] for s in stats]
    bp2 = ax_cost_dist.boxplot(cost_data, vert=True, patch_artist=True, widths=0.6)
    for patch, lbl in zip(bp2["boxes"], cost_labels):
        patch.set_facecolor(colors[lbl])
        patch.set_alpha(0.7)
    ax_cost_dist.set_xticks(range(1, n_ds + 1))
    ax_cost_dist.set_xticklabels(cost_labels, rotation=35, ha="right", fontsize=7)
    ax_cost_dist.set_ylabel("Cost per question (USD)", fontsize=9)
    ax_cost_dist.set_title("Cost distribution", fontsize=10, fontweight="bold")
    ax_cost_dist.spines["top"].set_visible(False)
    ax_cost_dist.spines["right"].set_visible(False)

    # ── Row 3 : Token Breakdown ───────────────────────────────────────────────
    tok_categories = ["Input tokens", "Output tokens", "Cache write tokens", "Cache read tokens"]
    tok_colors_map = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    tok_keys = ["tok_input", "tok_output", "tok_cw", "tok_cr"]

    x = np.arange(n_ds)
    width = 0.6
    bottoms = np.zeros(n_ds)
    seg_vals: list[np.ndarray] = []

    for cat, col, key in zip(tok_categories, tok_colors_map, tok_keys):
        vals = np.array([s[key] for s in stats])
        seg_vals.append(vals)
        ax_tok.bar(x, vals, bottom=bottoms, color=col, label=cat, width=width, zorder=2)
        bottoms = bottoms + vals

    totals = sum(seg_vals)  # per-dataset total

    # Total label above each bar (human-readable: K / M)
    def _fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"{v/1_000_000:.2f}M"
        if v >= 1_000:
            return f"{v/1_000:.1f}K"
        return str(int(v))

    for xi, tot in enumerate(totals):
        ax_tok.text(
            xi, tot * 1.03, _fmt(tot),
            ha="center", va="bottom", fontsize=8, fontweight="bold", color="#333333",
        )

    # Per-segment labels: show pct + token count when segment is large enough.
    # In log space, "large enough" means the segment spans ≥12% of the log range.
    log_top = np.log10(np.maximum(totals, 1))
    log_bot_global = 0  # log10(1)

    bottoms2 = np.zeros(n_ds)
    for vals in seg_vals:
        for xi, (bot, v, tot) in enumerate(zip(bottoms2, vals, totals)):
            if v <= 0:
                bottoms2[xi] += v
                continue
            pct = v / tot * 100 if tot > 0 else 0
            # log-space fraction of the visible range this segment occupies
            seg_log_span = np.log10(bot + v + 1) - np.log10(max(bot, 1))
            total_log_span = log_top[xi] - log_bot_global
            log_frac = seg_log_span / total_log_span if total_log_span > 0 else 0

            if log_frac >= 0.12:
                mid = np.sqrt((bot + 1) * (bot + v + 1))  # geometric midpoint
                label = f"{pct:.0f}%\n{_fmt(v)}"
                ax_tok.text(
                    xi, mid, label,
                    ha="center", va="center", fontsize=6.5,
                    color="white", fontweight="bold",
                    linespacing=1.3,
                )
        bottoms2 = bottoms2 + vals

    ax_tok.set_yscale("log")
    ax_tok.set_ylim(bottom=1)
    # nudge top so total labels aren't clipped
    ax_tok.set_ylim(top=float(totals.max()) * 6)
    ax_tok.set_xticks(x)
    ax_tok.set_xticklabels([s["label"] for s in stats], fontsize=9, rotation=15, ha="right")
    ax_tok.set_ylabel("Avg tokens per question (log scale)", fontsize=9)
    ax_tok.set_title("Token Breakdown (avg per question)", fontsize=11, fontweight="bold")
    ax_tok.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v):,}")
    )
    ax_tok.tick_params(axis="y", labelsize=7)
    ax_tok.spines["top"].set_visible(False)
    ax_tok.spines["right"].set_visible(False)
    ax_tok.grid(axis="y", alpha=0.3, linestyle="--", zorder=0)
    ax_tok.legend(fontsize=8, loc="upper left", ncol=2, framealpha=0.9)

    # ── Title ─────────────────────────────────────────────────────────────────
    all_labels = ", ".join(s["label"] for s in stats)
    fig.suptitle(
        f"Claude Code Metrics Matrix\n{all_labels}",
        fontsize=13, fontweight="bold", y=0.98,
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = str(ensure_figure_dir())
    out = os.path.join(out_dir, "metrics_matrix.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out}")
    return out


if __name__ == "__main__":
    datasets = load_all()
    make_figure(datasets)
