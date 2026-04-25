"""Tool call breakdown per dataset — produces figure only."""
import os, json, glob
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from ._common import ANALYSIS_BASE, ensure_figure_dir

BASE = str(ANALYSIS_BASE)

ALL_DIRS = [
    'eval_logs/claude_code/qa/musique_dev_sample50',
    'eval_logs/claude_code/qa/hotpotqa_dev_sample50',
    'eval_logs/claude_code/qa/2wikimultihopqa_dev_sample50',
    'eval_logs/claude_code/qa/bamboogle_test_sample50',
    'eval_logs/claude_code/qa/nq_test_sample50',
    'eval_logs/claude_code/qa/triviaqa_test_sample50',
    'eval_logs/claude_code/ir/bright_biology',
    'eval_logs/claude_code/ir/bright_robotics',
    'eval_logs/claude_code/browsecomp-plus_full',
]

LABELS = {
    'musique_dev_sample50':         'musique',
    'hotpotqa_dev_sample50':        'hotpotqa',
    '2wikimultihopqa_dev_sample50': '2wiki',
    'bamboogle_test_sample50':      'bamboogle',
    'nq_test_sample50':             'nq',
    'triviaqa_test_sample50':       'triviaqa',
    'bright_biology':               'biology',
    'bright_robotics':              'robotics',
    'browsecomp-plus_full':         'browsecomp-plus',
}

# Tool categories (stack order bottom→top); 'other' catches unknown tools
TOOLS = ['Bash', 'Grep', 'Read', 'Glob', 'ToolSearch', 'TaskOutput', 'other']

CAT_COLORS = [
    '#d62728',  # red     — Bash
    '#1f77b4',  # blue    — Grep
    '#ff7f0e',  # orange  — Read
    '#2ca02c',  # green   — Glob
    '#9467bd',  # purple  — ToolSearch
    '#bcbd22',  # yellow  — TaskOutput
    '#7f7f7f',  # grey    — other
]


# ── data loading ──────────────────────────────────────────────────────────────

def load_tool_calls(directory):
    """Return (per_q_counts, total_counts) where each is a dict {tool: count}."""
    full_path = os.path.join(BASE, directory)
    per_q = []
    for fpath in sorted(glob.glob(os.path.join(full_path, '*.jsonl'))):
        counts = {t: 0 for t in TOOLS}
        with open(fpath) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for msg in obj.get('messages', []):
                    if msg.get('type') != 'assistant':
                        continue
                    for block in msg.get('message', {}).get('content', []):
                        if (isinstance(block, dict)
                                and block.get('type') == 'tool_use'):
                            name = block.get('name', 'other')
                            key = name if name in TOOLS else 'other'
                            counts[key] += 1
        per_q.append(counts)

    total = {t: sum(q[t] for q in per_q) for t in TOOLS}
    return per_q, total


# ── plotting ──────────────────────────────────────────────────────────────────

def make_figure():
    out_dir = str(ensure_figure_dir())

    ds_names, ds_total, ds_n_q = [], [], []

    for d in ALL_DIRS:
        per_q, total = load_tool_calls(d)
        ds_names.append(LABELS[os.path.basename(d)])
        ds_total.append(total)
        ds_n_q.append(len(per_q))

    n_ds = len(ds_names)
    x = np.arange(n_ds)
    width = 0.55

    fig, ax = plt.subplots(figsize=(n_ds * 2, 6))
    bottoms = np.zeros(n_ds)

    for tool, color in zip(TOOLS, CAT_COLORS):
        counts = np.array([ds_total[i][tool] for i in range(n_ds)], dtype=float)
        grand   = np.array([sum(ds_total[i].values()) for i in range(n_ds)], dtype=float)
        n_qs    = np.array(ds_n_q, dtype=float)

        pcts = np.where(grand > 0, counts / grand * 100, 0)
        avgs = counts / n_qs

        ax.bar(x, pcts, width, bottom=bottoms, color=color, label=tool)

        for xi, (bot, pct, avg) in enumerate(zip(bottoms, pcts, avgs)):
            if pct >= 5:
                ax.text(xi, bot + pct / 2,
                        f'{pct:.0f}%\n({avg:.1f}/q)',
                        ha='center', va='center',
                        fontsize=7.5, fontweight='bold', color='white')

        bottoms = bottoms + pcts

    # Totals above each bar
    for xi in range(n_ds):
        tot = sum(ds_total[xi].values())
        nq  = ds_n_q[xi]
        ax.text(xi, 102, f'n={tot}\n({tot/nq:.1f}/q avg)',
                ha='center', va='bottom', fontsize=8, color='#333333')

    ax.set_xticks(x)
    ax.set_xticklabels(ds_names, fontsize=10, rotation=15, ha='right')
    ax.set_ylabel('% of all tool calls', fontsize=11)
    ax.set_title('Tool call breakdown per dataset', fontsize=13, fontweight='bold')
    ax.set_ylim(0, 115)
    ax.set_xlim(-0.5, n_ds - 0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    patches = [mpatches.Patch(color=c, label=l) for l, c in zip(TOOLS, CAT_COLORS)]
    ax.legend(handles=patches, loc='upper right', fontsize=9,
              ncol=2, framealpha=0.9)

    fig.tight_layout()
    out = os.path.join(out_dir, 'tool_per_dataset.png')
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved → {out}')


if __name__ == '__main__':
    make_figure()
