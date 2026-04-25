"""Analyze python3 -c Bash calls across datasets.

What are the inline Python scripts doing?
  - keyword search in doc contents
  - id-based lookup
  - combined / other

Produces two subplots:
  (left)  Stacked bar: Python call type % per dataset
  (right) Horizontal bar: which fields are accessed / printed
"""
import os, json, glob, re
from collections import Counter

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

# Sub-categories of Python calls (stack order bottom→top)
CATS = [
    'keyword in contents',   # if 'X' in d['contents']
    'id-based lookup',       # if d['id'] in [...]  or  d['id'] == '...'
    'keyword + id combined', # uses both
    'title search',          # if 'X' in d['title']
    'other',
]

CAT_COLORS = [
    '#1f77b4',  # blue   — keyword in contents
    '#d62728',  # red    — id-based lookup
    '#ff7f0e',  # orange — combined
    '#2ca02c',  # green  — title search
    '#7f7f7f',  # grey   — other
]

# Fields accessed when printing results
FIELD_CATS = [
    "d['contents'] / d['text']",
    "d['title']",
    "d['id']",
    "multiple fields",
    "print whole doc",
]


# ── helpers ────────────────────────────────────────────────────────────────────

def is_python_cmd(cmd: str) -> bool:
    first = cmd.strip().split('\n')[0]
    return bool(re.match(r'\s*python3?(\.\d+)?\s+(-c\b|<<)', first))


def classify_python(cmd: str) -> str:
    has_contents = bool(re.search(
        r"['\"]contents['\"]|d\[.contents.\]|doc\[.contents.\]|\.get\(.contents.\)", cmd))
    has_title    = bool(re.search(
        r"['\"]title['\"]|d\[.title.\]|doc\[.title.\]", cmd))
    has_id       = bool(re.search(
        r"d\[.id.\]\s*(==|in\s*\[)|['\"]id['\"]\s*:\s*['\"]", cmd))

    if has_id and (has_contents or has_title):
        return 'keyword + id combined'
    if has_id:
        return 'id-based lookup'
    if has_contents:
        return 'keyword in contents'
    if has_title:
        return 'title search'
    return 'other'


def classify_print_field(cmd: str) -> str:
    prints_contents = bool(re.search(
        r"print.*contents|contents.*print|d\[.contents.\].*\bprint\b|\bprint\b.*d\[.contents.\]",
        cmd, re.DOTALL))
    prints_title = bool(re.search(
        r"print.*title|title.*print|d\[.title.\].*\bprint\b|\bprint\b.*d\[.title.\]",
        cmd, re.DOTALL))
    prints_id = bool(re.search(
        r"print.*\bid\b|\bid\b.*print|d\[.id.\].*\bprint\b|\bprint\b.*d\[.id.\]",
        cmd, re.DOTALL))
    prints_doc = bool(re.search(r"print\(d\)|print\(doc\)|print\(json", cmd))

    count = sum([prints_contents, prints_title, prints_id, prints_doc])
    if prints_doc:
        return "print whole doc"
    if count >= 2:
        return "multiple fields"
    if prints_contents:
        return "d['contents'] / d['text']"
    if prints_title:
        return "d['title']"
    if prints_id:
        return "d['id']"
    return "d['contents'] / d['text']"   # most likely default


def load_python_cmds(directory: str):
    full = os.path.join(BASE, directory)
    cmds, n_q = [], 0
    for fpath in sorted(glob.glob(os.path.join(full, '*.jsonl'))):
        if os.path.basename(fpath) == 'evaluated.jsonl':
            continue
        n_q += 1
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
                                and block.get('type') == 'tool_use'
                                and block.get('name') == 'Bash'):
                            c = block.get('input', {}).get('command', '')
                            if c and is_python_cmd(c):
                                cmds.append(c)
    return cmds, n_q


# ── plotting ───────────────────────────────────────────────────────────────────

def make_figure():
    out_dir = str(ensure_figure_dir())

    ds_names, ds_counts, ds_n_q, ds_total = [], [], [], []
    all_cmds = []

    for d in ALL_DIRS:
        cmds, n_q = load_python_cmds(d)
        counts = {cat: sum(1 for c in cmds if classify_python(c) == cat) for cat in CATS}
        ds_names.append(LABELS[os.path.basename(d)])
        ds_counts.append(counts)
        ds_n_q.append(n_q)
        ds_total.append(len(cmds))
        all_cmds.extend(cmds)

    n_ds = len(ds_names)
    x = np.arange(n_ds)
    width = 0.55

    fig, axes = plt.subplots(1, 2, figsize=(max(12, n_ds * 2.5), 6),
                             gridspec_kw={'width_ratios': [3, 1.6]})

    # ── left: stacked bar ──────────────────────────────────────────────────────
    ax = axes[0]
    bottoms = np.zeros(n_ds)

    for cat, color in zip(CATS, CAT_COLORS):
        counts = np.array([ds_counts[i][cat] for i in range(n_ds)], dtype=float)
        grand  = np.array(ds_total, dtype=float)
        n_qs   = np.array(ds_n_q, dtype=float)
        pcts   = np.where(grand > 0, counts / grand * 100, 0)
        avgs   = counts / n_qs

        ax.bar(x, pcts, width, bottom=bottoms, color=color, label=cat)

        for xi, (bot, pct, avg) in enumerate(zip(bottoms, pcts, avgs)):
            if pct >= 7:
                ax.text(xi, bot + pct / 2,
                        f'{pct:.0f}%\n({avg:.1f}/q)',
                        ha='center', va='center',
                        fontsize=8, fontweight='bold', color='white')

        bottoms += pcts

    for xi in range(n_ds):
        tot = ds_total[xi]
        nq  = ds_n_q[xi]
        ax.text(xi, 102, f'n={tot}\n({tot/nq:.1f}/q avg)',
                ha='center', va='bottom', fontsize=8, color='#333333')

    ax.set_xticks(x)
    ax.set_xticklabels(ds_names, fontsize=10, rotation=15, ha='right')
    ax.set_ylabel('% of Python Bash calls', fontsize=11)
    ax.set_title('python3 -c call type per dataset', fontsize=13, fontweight='bold')
    ax.set_ylim(0, 115)
    ax.set_xlim(-0.5, n_ds - 0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    patches = [mpatches.Patch(color=c, label=l) for l, c in zip(CATS, CAT_COLORS)]
    ax.legend(handles=patches, loc='upper right', fontsize=9, ncol=1, framealpha=0.9)

    # ── right: what fields are printed / returned ──────────────────────────────
    ax2 = axes[1]

    field_counter = Counter(classify_print_field(c) for c in all_cmds)
    total = len(all_cmds)

    field_labels = [k for k, _ in field_counter.most_common()]
    field_vals   = [v for _, v in field_counter.most_common()]

    ypos = np.arange(len(field_labels))
    bars = ax2.barh(ypos, field_vals, color='#1f77b4', alpha=0.85)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(field_labels, fontsize=9.5)
    ax2.invert_yaxis()
    ax2.set_xlabel('# python3 -c calls (all datasets)', fontsize=10)
    ax2.set_title('What field does the script print?\n(global)', fontsize=11, fontweight='bold')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    for bar, val in zip(bars, field_vals):
        pct = val / total * 100
        ax2.text(bar.get_width() + 3, bar.get_y() + bar.get_height() / 2,
                 f'{val}  ({pct:.0f}%)', va='center', fontsize=9)

    ax2.set_xlim(0, (max(field_vals) * 1.45) if field_vals else 1)

    fig.tight_layout()

    out = os.path.join(out_dir, 'python_analysis.png')
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved → {out}')


if __name__ == '__main__':
    make_figure()
