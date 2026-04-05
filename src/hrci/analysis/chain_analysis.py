"""Tool call chain analysis for Claude Code logs.

Produces 2 figures saved to figure/claude_code/:
  chain_heatmap.png   — transition probability matrix (P(next|current))
  chain_ngrams.png    — top-20 2-grams and top-15 3-grams
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
    'eval_logs/claude_code/ir/beir_arguana_sample50',
    'eval_logs/claude_code/ir/beir_scifact_sample50',
    'eval_logs/claude_code/ir/bright_biology',
    'eval_logs/claude_code/ir/bright_robotics',
    'eval_logs/claude_code/browsecomp-plus_full',
]

# ── Bash subtype categorization ───────────────────────────────────────────────

def strip_comments(cmd):
    lines = cmd.split('\n')
    return '\n'.join(l for l in lines if not l.strip().startswith('#')).strip()


def split_pipes(cmd):
    parts, current = [], []
    in_sq = in_dq = False
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_dq:
            in_sq = not in_sq
        elif c == '"' and not in_sq:
            in_dq = not in_dq
        elif c == '\\':
            current.append(c); i += 1
            if i < len(cmd): current.append(cmd[i])
            i += 1; continue
        elif c == '|' and not in_sq and not in_dq:
            if i + 1 < len(cmd) and cmd[i + 1] == '|':
                current.append(c); i += 1
            else:
                parts.append(''.join(current).strip()); current = []; i += 1; continue
        current.append(c); i += 1
    if current:
        parts.append(''.join(current).strip())
    return parts


def bash_subtype(cmd):
    cmd = strip_comments(cmd)
    if not cmd:
        return 'B:other'
    parts = split_pipes(cmd)
    grep_parts = [p for p in parts if re.match(r'(\w+=\S+\s+)*grep', p.strip())]

    for p in grep_parts:
        if r'\|' in p:
            return 'B:grep+alt'
    if len(grep_parts) >= 2:
        return 'B:grep|grep'
    if re.search(r'python3?\s*-?\s*<<', cmd):
        return 'B:py-heredoc'
    if re.search(r'python3?\s+-c', cmd):
        return 'B:py-c'
    if grep_parts:
        return 'B:grep'
    if re.search(r'\bawk\b', cmd):
        return 'B:sed'
    if re.search(r"sed\s+[^;]*-n\s+['\"]?[\d,]+p", cmd) or re.search(r"sed\s+['\"]?[\d,]+p", cmd):
        return 'B:sed'
    if re.match(r'\s*for\b', cmd):
        return 'B:for'
    if re.search(r'\b(cat|head|tail)\b', cmd):
        return 'B:cat'
    if re.search(r'\bwc\b', cmd):
        return 'B:wc'
    if re.search(r'\b(ls|find)\b', cmd):
        return 'B:ls/find'
    return 'B:other'


KNOWN_TOOLS = {'Grep', 'Read', 'Glob', 'ToolSearch', 'TaskOutput', 'Agent'}

def tool_label(block):
    name = block.get('name', 'other')
    if name == 'Bash':
        return bash_subtype(block.get('input', {}).get('command', ''))
    return name if name in KNOWN_TOOLS else 'other'


# ── Data loading ──────────────────────────────────────────────────────────────

def load_sequences():
    """Return list of tool-call sequences, one list per question file."""
    sequences = []
    for d in ALL_DIRS:
        full = os.path.join(BASE, d)
        for fpath in sorted(glob.glob(os.path.join(full, '*.jsonl'))):
            seq = []
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
                            if isinstance(block, dict) and block.get('type') == 'tool_use':
                                seq.append(tool_label(block))
            if seq:
                sequences.append(seq)
    return sequences


# ── Node colour palette ───────────────────────────────────────────────────────

NODE_COLORS = {
    'B:grep+alt':   '#d62728',
    'B:grep':       '#e377c2',
    'B:grep|grep':  '#ff7f0e',
    'B:py-c':       '#1f77b4',
    'B:py-heredoc': '#aec7e8',
    'B:sed':        '#2ca02c',
    'B:cat':        '#8c6d31',
    'B:for':        '#bcbd22',
    'B:wc':         '#e8c100',
    'B:ls/find':    '#17becf',
    'B:other':      '#7f7f7f',
    'Grep':         '#1f77b4',
    'Read':         '#2ca02c',
    'Glob':         '#9467bd',
    'ToolSearch':   '#8c564b',
    'TaskOutput':   '#e7ba52',
    'Agent':        '#f7b6d2',
    'other':        '#c7c7c7',
}


# ── Figure 1: Transition heatmap ─────────────────────────────────────────────

def plot_heatmap(sequences, out_path):
    # Count all transitions and determine active labels
    bigrams = Counter()
    tool_freq = Counter()
    for seq in sequences:
        for t in seq:
            tool_freq[t] += 1
        for a, b in zip(seq, seq[1:]):
            bigrams[(a, b)] += 1

    # Keep labels that appear at least once as source or target in a transition
    active = sorted(
        {t for (a, b) in bigrams for t in (a, b)},
        key=lambda t: -tool_freq[t]
    )
    idx = {t: i for i, t in enumerate(active)}
    n = len(active)

    mat = np.zeros((n, n), dtype=int)
    for (a, b), cnt in bigrams.items():
        if a in idx and b in idx:
            mat[idx[a], idx[b]] += cnt

    # Row-normalise to get transition probabilities
    row_sums = mat.sum(axis=1, keepdims=True)
    prob = np.where(row_sums > 0, mat / row_sums, 0)

    fig, ax = plt.subplots(figsize=(max(12, n * 0.8), max(10, n * 0.75)))
    im = ax.imshow(prob, cmap='YlOrRd', aspect='auto', vmin=0, vmax=1)

    # Annotate cells
    for i in range(n):
        for j in range(n):
            if mat[i, j] > 0:
                ax.text(j, i, f'{prob[i,j]:.0%}\n({mat[i,j]})',
                        ha='center', va='center',
                        fontsize=6.5,
                        color='white' if prob[i, j] > 0.5 else 'black')

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(active, rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels(active, fontsize=8)
    ax.set_xlabel('Next tool call', fontsize=10)
    ax.set_ylabel('Current tool call', fontsize=10)
    ax.set_title('Tool call transition matrix\n(cell = P(next|current), count in brackets)',
                 fontsize=12, fontweight='bold')

    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label='Transition probability')
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved → {out_path}')


# ── Figure 2: Top n-grams ─────────────────────────────────────────────────────

def plot_ngrams(sequences, out_path):
    bigrams  = Counter()
    trigrams = Counter()
    for seq in sequences:
        for a, b in zip(seq, seq[1:]):
            bigrams[(a, b)] += 1
        for a, b, c in zip(seq, seq[1:], seq[2:]):
            trigrams[(a, b, c)] += 1

    top_bi  = bigrams.most_common(20)
    top_tri = trigrams.most_common(15)

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # ── 2-grams ──
    ax = axes[0]
    labels = [f'{a}  →  {b}' for (a, b), _ in top_bi]
    vals   = [v for _, v in top_bi]
    colors = [NODE_COLORS.get(a, '#999') for (a, _), _ in top_bi]
    ypos   = np.arange(len(labels))
    bars   = ax.barh(ypos, vals, color=colors, alpha=0.85)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('Count', fontsize=10)
    ax.set_title('Top-20 2-gram tool chains', fontsize=11, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + max(vals) * 0.01, bar.get_y() + bar.get_height() / 2,
                str(val), va='center', fontsize=8)
    ax.set_xlim(0, max(vals) * 1.12)

    # ── 3-grams ──
    ax = axes[1]
    labels = [f'{a}  →  {b}  →  {c}' for (a, b, c), _ in top_tri]
    vals   = [v for _, v in top_tri]
    colors = [NODE_COLORS.get(a, '#999') for (a, _, __), _ in top_tri]
    ypos   = np.arange(len(labels))
    bars   = ax.barh(ypos, vals, color=colors, alpha=0.85)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('Count', fontsize=10)
    ax.set_title('Top-15 3-gram tool chains', fontsize=11, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + max(vals) * 0.01, bar.get_y() + bar.get_height() / 2,
                str(val), va='center', fontsize=8)
    ax.set_xlim(0, max(vals) * 1.12)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved → {out_path}')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    out_dir = str(ensure_figure_dir())

    print('Loading sequences …')
    sequences = load_sequences()
    print(f'  {len(sequences)} question files, '
          f'{sum(len(s) for s in sequences)} total tool calls')

    plot_heatmap(sequences, os.path.join(out_dir, 'chain_heatmap.png'))
    plot_ngrams( sequences, os.path.join(out_dir, 'chain_ngrams.png'))


if __name__ == '__main__':
    main()
