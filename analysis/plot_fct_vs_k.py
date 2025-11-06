#!/usr/bin/env python3
import argparse, pandas as pd, matplotlib.pyplot as plt, os, re

# Plot FCT percentiles vs K for a fixed (L,N,scenario) across seeds.
# Expects fct_summary.csv style rows: file,count,p50_ms,p95_ms,p99_ms
# Filenames encode K,L,N,scenario,seed like: fixk_K30_L0.6_N8_sym_s1_vectors.csv
# We'll group by K and aggregate p95/p99 across seeds (mean or median selectable).

PATTERN = re.compile(r'fixk_K(?P<K>\d+)_L(?P<L>\d+\.\d+)_N(?P<N>\d+)_?(?P<scen>sym|asym)?_s(?P<seed>\d+)')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--summary', required=True, help='FCT summary CSV produced by fct_extract.py')
    ap.add_argument('--L', required=True, help='Load e.g. 0.6')
    ap.add_argument('--N', required=True, help='Incast fan-in e.g. 8')
    ap.add_argument('--scenario', choices=['sym','asym'], required=True)
    ap.add_argument('--metric', choices=['mean','median'], default='median', help='Aggregate across seeds')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.summary)
    # Extract params from filename
    rows = []
    for _, r in df.iterrows():
        fname = r['file']
        m = PATTERN.search(fname)
        if not m: continue
        K = int(m.group('K'))
        L = m.group('L'); N = m.group('N'); scen = m.group('scen'); seed = int(m.group('seed'))
        if L != args.L or N != args.N or scen != args.scenario: continue
        rows.append({'K':K,'seed':seed,'p95':r.get('p95_ms'), 'p99':r.get('p99_ms')})
    if not rows:
        print('No matching rows for filter')
        raise SystemExit(1)
    dff = pd.DataFrame(rows)
    agg_func = {'mean':dff.groupby('K').mean, 'median':dff.groupby('K').median}[args.metric]
    agg = agg_func()

    fig, ax = plt.subplots(figsize=(6,4))
    ax.plot(agg.index, agg['p95'], marker='o', label='P95 FCT')
    ax.plot(agg.index, agg['p99'], marker='s', label='P99 FCT')
    ax.set_xlabel('K (packets)')
    ax.set_ylabel('FCT (ms)')
    ax.set_title(f'FCT vs K (L={args.L}, N={args.N}, {args.scenario}, {args.metric})')
    ax.grid(alpha=0.3)
    ax.legend()
    out = os.path.abspath(args.output)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print('wrote', out)
