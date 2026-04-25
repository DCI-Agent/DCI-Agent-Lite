"""Grep tool usage analysis — all dataset groups."""
import os, re, json, glob
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from collections import Counter, defaultdict
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


# ── data loading ──────────────────────────────────────────────────────────────

def load_grep_calls(directory):
    """Return (per_q_calls, all_calls) for one dataset directory."""
    full_path = os.path.join(BASE, directory)
    per_q = []
    for fpath in sorted(glob.glob(os.path.join(full_path, '*.jsonl'))):
        calls = []
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
                                and block.get('name') == 'Grep'):
                            calls.append(block.get('input', {}))
        per_q.append(calls)
    return per_q, [c for q in per_q for c in q]


# ── classifiers ───────────────────────────────────────────────────────────────

def classify_pattern(p):
    has_pipe    = '|' in p
    has_dotstar = bool(re.search(r'\.\*', p))
    if has_dotstar and has_pipe:
        return 'X.*Y|Y.*X (co-occurrence)'
    if has_pipe:
        return 'A|B|C (OR variants)'
    if has_dotstar:
        return 'X.*Y (sequence)'
    # proper noun: starts with uppercase, may contain hyphens, digits, quotes, parens
    if re.match(r'^[A-Z\(][A-Za-z0-9\u00C0-\u024F\'\-\(\) ]+$', p):
        return 'proper noun (entity)'
    # descriptive phrase: multi-word lowercase (natural language query)
    if re.match(r'^[a-z][a-z0-9 \-,\']+$', p) and ' ' in p:
        return 'descriptive phrase'
    return 'other'


# ── plotting helpers ──────────────────────────────────────────────────────────

def stacked_bars(ax, ds_names, counts_by_ds, categories, colors, title,
                 n_q_by_ds=None, ylabel='% of Grep calls', min_pct_label=8):
    x = np.arange(len(ds_names))
    width = 0.55
    bottoms = np.zeros(len(ds_names))
    for cat, color in zip(categories, colors):
        vals  = np.array([counts_by_ds[ds].get(cat, 0) for ds in ds_names], dtype=float)
        tots  = np.array([sum(counts_by_ds[ds].values()) for ds in ds_names], dtype=float)
        n_qs  = np.array([n_q_by_ds[ds] for ds in ds_names], dtype=float) if n_q_by_ds else None
        pcts  = np.where(tots > 0, vals / tots * 100, 0)
        ax.bar(x, pcts, width, bottom=bottoms, color=color, label=cat)
        for xi, (bot, pct, val) in enumerate(zip(bottoms, pcts, vals)):
            if pct >= min_pct_label:
                avg = val / n_qs[xi] if n_qs is not None else val
                ax.text(xi, bot + pct / 2, f'{pct:.0f}%\n({avg:.1f}/q)',
                        ha='center', va='center',
                        fontsize=7.5, fontweight='bold', color='white')
        bottoms += pcts
    ax.set_xticks(x)
    ax.set_xticklabels(ds_names, fontsize=9, rotation=15, ha='right')
    ax.set_ylim(0, 118)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for xi, ds in enumerate(ds_names):
        tot = sum(counts_by_ds[ds].values())
        nq  = n_q_by_ds[ds] if n_q_by_ds else None
        label = f'n={tot}\n({tot/nq:.1f}/q)' if nq else f'n={tot}'
        ax.text(xi, 102, label, ha='center', va='bottom', fontsize=7, color='#444')


# ── main ──────────────────────────────────────────────────────────────────────

def make_figure():
    out_dir = str(ensure_figure_dir())

    # Collect per-dataset data
    ds_names   = []
    all_calls_by_ds  = {}
    n_q_by_ds  = {}
    for d in ALL_DIRS:
        per_q, calls = load_grep_calls(d)
        name = LABELS[os.path.basename(d)]
        ds_names.append(name)
        all_calls_by_ds[name] = calls
        n_q_by_ds[name] = len(per_q)

    # ── compute counts per dataset ────────────────────────────────────────────

    # 1. Pattern type
    PAT_CATS   = ['proper noun (entity)', 'X.*Y|Y.*X (co-occurrence)',
                  'A|B|C (OR variants)', 'X.*Y (sequence)', 'descriptive phrase', 'other']
    PAT_COLORS = ['#1f77b4', '#d62728', '#ff7f0e', '#2ca02c', '#9467bd', '#7f7f7f']
    pat_counts = {ds: Counter(classify_pattern(c.get('pattern', ''))
                              for c in all_calls_by_ds[ds])
                  for ds in ds_names}

    # 2. output_mode
    OM_CATS   = ['content', 'files_with_matches', 'count']
    OM_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c']
    om_counts = {ds: Counter(c.get('output_mode', 'content')
                             for c in all_calls_by_ds[ds])
                 for ds in ds_names}

    # 3. -i flag
    I_CATS   = ['-i on', 'case-sensitive']
    I_COLORS = ['#d62728', '#aaaaaa']
    i_counts = {ds: {'-i on':        sum(1 for c in all_calls_by_ds[ds] if c.get('-i')),
                     'case-sensitive': sum(1 for c in all_calls_by_ds[ds] if not c.get('-i'))}
                for ds in ds_names}

    # 4. head_limit — bar of common values per dataset
    HL_VALS = [5, 10, 15, 20, 30, 50, 'other']

    def hl_bucket(v):
        return v if v in [5, 10, 15, 20, 30, 50] else 'other'

    hl_counts = {ds: Counter(hl_bucket(c['head_limit'])
                             for c in all_calls_by_ds[ds] if 'head_limit' in c)
                 for ds in ds_names}
    HL_COLORS = ['#aec7e8', '#1f77b4', '#c5b0d5', '#ff7f0e', '#2ca02c', '#d62728', '#7f7f7f']

    # 5. context (-C) — bar of common values
    CTX_VALS = [1, 2, 3, 5, 10, 'other']

    def ctx_bucket(v):
        return v if v in [1, 2, 3, 5, 10] else 'other'

    ctx_counts = {ds: Counter(ctx_bucket(c.get('-C', c.get('context')))
                              for c in all_calls_by_ds[ds]
                              if '-C' in c or 'context' in c)
                  for ds in ds_names}
    CTX_COLORS = ['#aec7e8', '#1f77b4', '#d62728', '#ff7f0e', '#2ca02c', '#7f7f7f']

    # ── layout ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(max(12, len(ds_names) * 2.5), 14))
    fig.suptitle('Grep tool — all datasets analysis', fontsize=14,
                 fontweight='bold', y=0.99)
    gs = fig.add_gridspec(3, 2, hspace=0.5, wspace=0.35)

    ax_pat = fig.add_subplot(gs[0, :])   # full width — pattern
    ax_om  = fig.add_subplot(gs[1, 0])
    ax_i   = fig.add_subplot(gs[1, 1])
    ax_hl  = fig.add_subplot(gs[2, 0])
    ax_ctx = fig.add_subplot(gs[2, 1])

    # Pattern type
    stacked_bars(ax_pat, ds_names, pat_counts, PAT_CATS, PAT_COLORS, 'Pattern type',
                 n_q_by_ds=n_q_by_ds)
    ax_pat.legend(
        [mpatches.Patch(color=c, label=l) for l, c in zip(PAT_CATS, PAT_COLORS)],
        PAT_CATS, fontsize=8.5, loc='lower center',
        bbox_to_anchor=(0.5, 1.02), ncol=3, framealpha=0.9)

    # output_mode
    stacked_bars(ax_om, ds_names, om_counts, OM_CATS, OM_COLORS, 'output_mode',
                 n_q_by_ds=n_q_by_ds)
    ax_om.legend(
        [mpatches.Patch(color=c, label=l) for l, c in zip(OM_CATS, OM_COLORS)],
        OM_CATS, fontsize=8, loc='upper right')

    # -i flag
    stacked_bars(ax_i, ds_names, i_counts, I_CATS, I_COLORS, '-i flag (case sensitivity)',
                 n_q_by_ds=n_q_by_ds)
    ax_i.legend(
        [mpatches.Patch(color=c, label=l) for c, l in zip(I_COLORS, I_CATS)],
        I_CATS, fontsize=8, loc='lower right')

    # head_limit
    stacked_bars(ax_hl, ds_names, hl_counts,
                 [str(v) for v in HL_VALS], HL_COLORS,
                 'head_limit (when set)', n_q_by_ds=n_q_by_ds,
                 ylabel='% of calls with head_limit')
    ax_hl.legend(
        [mpatches.Patch(color=c, label=str(l)) for c, l in zip(HL_COLORS, HL_VALS)],
        [str(v) for v in HL_VALS], fontsize=8, loc='upper right', title='value')

    # context (-C)
    stacked_bars(ax_ctx, ds_names, ctx_counts,
                 [str(v) for v in CTX_VALS], CTX_COLORS,
                 'context -C (when set)', n_q_by_ds=n_q_by_ds,
                 ylabel='% of calls with context')
    ax_ctx.legend(
        [mpatches.Patch(color=c, label=str(l)) for c, l in zip(CTX_COLORS, CTX_VALS)],
        [str(v) for v in CTX_VALS], fontsize=8, loc='upper right', title='lines')

    out = os.path.join(out_dir, 'grep_tool_patterns.png')
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved → {out}')


if __name__ == '__main__':
    make_figure()
