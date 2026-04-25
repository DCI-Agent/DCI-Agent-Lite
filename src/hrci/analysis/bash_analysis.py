"""Deep bash command analysis for Claude Code logs — produces figure only."""
import os, re, json, glob
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

# Category definitions (order = stack order bottom→top)
CATEGORIES = [
    ('grep + regex alternation (\\|)',   '#d62728'),
    ('grep (simple string lookup)',      '#e377c2'),
    ('grep | grep (chain/refine)',       '#ff7f0e'),
    ('python3 -c (inline)',             '#1f77b4'),
    ('python3 heredoc (<<EOF)',         '#aec7e8'),
    ('sed -n NNNp (line lookup)',        '#2ca02c'),
    ('cat / head / tail',               '#8c6d31'),
    ('for loop',                        '#bcbd22'),
    ('wc (count)',                      '#e8c100'),
    ('ls / find',                       '#17becf'),
    ('other',                           '#7f7f7f'),
]
CAT_NAMES   = [c[0] for c in CATEGORIES]
CAT_COLORS  = [c[1] for c in CATEGORIES]


# ── helpers ──────────────────────────────────────────────────────────────────

def load_bash_cmds(directory):
    """Return (per_q_cmds, all_cmds) for a dataset directory."""
    full_path = os.path.join(BASE, directory)
    per_q = []
    for fpath in sorted(glob.glob(os.path.join(full_path, '*.jsonl'))):
        cmds = []
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
                            cmd = block.get('input', {}).get('command', '')
                            if cmd:
                                cmds.append(cmd)
        per_q.append(cmds)
    all_cmds = [c for q in per_q for c in q]
    return per_q, all_cmds


def split_pipes(cmd):
    """Split on unquoted | (not ||)."""
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
            current.append(c)
            i += 1
            if i < len(cmd):
                current.append(cmd[i])
            i += 1
            continue
        elif c == '|' and not in_sq and not in_dq:
            if i + 1 < len(cmd) and cmd[i + 1] == '|':
                current.append(c)
                i += 1
            else:
                parts.append(''.join(current).strip())
                current = []
                i += 1
                continue
        current.append(c)
        i += 1
    if current:
        parts.append(''.join(current).strip())
    return parts


def strip_comments(cmd):
    """Remove leading shell comment lines (# ...) from a command."""
    lines = cmd.split('\n')
    non_comment = [l for l in lines if not l.strip().startswith('#')]
    return '\n'.join(non_comment).strip()


def categorise(cmd):
    """Return the category name for a bash command."""
    cmd = strip_comments(cmd)
    if not cmd:
        return 'other'

    parts = split_pipes(cmd)
    # match grep even with env-var prefix like LC_ALL=C grep ...
    grep_parts = [p for p in parts if re.match(r'(\w+=\S+\s+)*grep', p.strip())]

    # grep with regex alternation \|
    for p in grep_parts:
        if r'\|' in p:
            return 'grep + regex alternation (\\|)'

    # grep | grep chain (2+ greps piped)
    if len(grep_parts) >= 2:
        return 'grep | grep (chain/refine)'

    # python3 heredoc  (python3 - <<'EOF'  or  python3 <<'EOF')
    if re.search(r'python3?\s*-?\s*<<', cmd):
        return 'python3 heredoc (<<EOF)'

    # python3 -c inline
    if re.search(r'python3?\s+-c', cmd):
        return 'python3 -c (inline)'

    # simple grep (no alternation, no chain) — catches grep piped to head/python3 etc.
    if grep_parts:
        return 'grep (simple string lookup)'

    # awk line-range lookup: awk 'NR>=N && NR<=M'
    if re.search(r'\bawk\b', cmd):
        return 'sed -n NNNp (line lookup)'

    # sed -n NNNp or sed -n N,Mp (single line or range, with or without quotes)
    if re.search(r"sed\s+[^;]*-n\s+['\"]?[\d,]+p", cmd) or re.search(r"sed\s+['\"]?[\d,]+p", cmd):
        return 'sed -n NNNp (line lookup)'

    # for loop (e.g. for i in ...; do ... done)
    if re.match(r'\s*for\b', cmd):
        return 'for loop'

    # cat / head / tail
    if re.search(r'\b(cat|head|tail)\b', cmd):
        return 'cat / head / tail'

    # wc
    if re.search(r'\bwc\b', cmd):
        return 'wc (count)'

    # ls / find
    if re.search(r'\b(ls|find)\b', cmd):
        return 'ls / find'

    return 'other'


# ── plotting ──────────────────────────────────────────────────────────────────

def make_figure():
    out_dir = str(ensure_figure_dir())

    ds_names, ds_counts, ds_n_q = [], [], []

    for d in ALL_DIRS:
        per_q, all_cmds = load_bash_cmds(d)
        cat_counts = {c: 0 for c in CAT_NAMES}
        for cmd in all_cmds:
            cat_counts[categorise(cmd)] += 1
        ds_names.append(LABELS[os.path.basename(d)])
        ds_counts.append(cat_counts)
        ds_n_q.append(len(per_q))

    n_ds = len(ds_names)
    x = np.arange(n_ds)
    width = 0.55

    fig, ax = plt.subplots(figsize=(n_ds * 2, 6))
    bottoms = np.zeros(n_ds)

    for cat, color in zip(CAT_NAMES, CAT_COLORS):
        counts = np.array([ds_counts[i][cat] for i in range(n_ds)], dtype=float)
        totals = np.array([sum(ds_counts[i].values()) for i in range(n_ds)], dtype=float)
        n_qs   = np.array(ds_n_q, dtype=float)

        pcts = np.where(totals > 0, counts / totals * 100, 0)
        avgs = counts / n_qs

        ax.bar(x, pcts, width, bottom=bottoms, color=color, label=cat)

        for xi, (bot, pct, avg) in enumerate(zip(bottoms, pcts, avgs)):
            if pct >= 5:
                ax.text(xi, bot + pct / 2,
                        f'{pct:.0f}%\n({avg:.1f}/q)',
                        ha='center', va='center',
                        fontsize=7.5, fontweight='bold', color='white')

        bottoms = bottoms + pcts

    # Totals above each bar
    for xi in range(n_ds):
        tot = sum(ds_counts[xi].values())
        nq  = ds_n_q[xi]
        ax.text(xi, 102, f'n={tot}\n({tot/nq:.1f}/q avg)',
                ha='center', va='bottom', fontsize=8, color='#333333')

    ax.set_xticks(x)
    ax.set_xticklabels(ds_names, fontsize=10, rotation=15, ha='right')
    ax.set_ylabel('% of all bash commands', fontsize=11)
    ax.set_title('Bash command category breakdown per dataset', fontsize=13, fontweight='bold')
    ax.set_ylim(0, 115)
    ax.set_xlim(-0.5, n_ds - 0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    patches = [mpatches.Patch(color=c, label=l) for l, c in zip(CAT_NAMES, CAT_COLORS)]
    ax.legend(handles=patches, loc='upper right', fontsize=8,
              ncol=2, framealpha=0.9)

    fig.tight_layout()
    out = os.path.join(out_dir, 'bash_per_dataset.png')
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved → {out}')


if __name__ == '__main__':
    make_figure()
