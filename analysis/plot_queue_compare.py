#!/usr/bin/env python3
import argparse, pandas as pd, matplotlib.pyplot as plt, os, sys

# Side-by-side queue comparison (sym vs asym) for a single (K,L,N,seed)
# Usage: python analysis/plot_queue_compare.py --sym results/fixk_K10_L0.6_N8_sym_s1_vectors.csv --asym results/fixk_K10_L0.6_N8_asym_s1_vectors.csv --output figs/compare_K10_L0.6_N8_s1.png --module leaf[0].ppp[2].queue --name queueBitLength --k 10 --unit KB

def extract_queue(df, module_sub, name_sub):
    # Find first matching vector row
    candidates = df[(df['module'].str.contains(module_sub, na=False)) & (df['name'].str.contains(name_sub, na=False)) & (df['type']=='vector')]
    if candidates.empty:
        return None, None
    row = candidates.iloc[0]
    # Collect numeric columns (vectime/vecvalue) pattern
    times_cols = [c for c in df.columns if c.startswith(row['module']) and c.endswith(':vectime')]  # fallback heuristic may fail; wide export simpler
    # Simpler generic: iterate columns ending with :vectime/:vecvalue matching name substring
    tcol = row['module'] + '.' + row['name'] + ':vectime'
    vcol = row['module'] + '.' + row['name'] + ':vecvalue'
    if tcol in df.columns and vcol in df.columns:
        t = df[tcol].dropna().astype(str).str.split().explode().astype(float).to_numpy()
        v = df[vcol].dropna().astype(str).str.split().explode().astype(float).to_numpy()
        return t, v
    # Fallback: try scanning all columns for vectime/vecvalue with same name
    t, v = None, None
    return t, v

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', required=True)
    ap.add_argument('--asym', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--module', default='leaf[0].ppp[2].queue')
    ap.add_argument('--name', default='queueBitLength')
    ap.add_argument('--k', type=float, default=None)
    ap.add_argument('--unit', choices=['B','KB','MB','packets'], default='KB')
    args = ap.parse_args()

    sym_df = pd.read_csv(args.sym)
    asym_df = pd.read_csv(args.asym)

    t_sym, q_sym = extract_queue(sym_df, args.module, args.name)
    t_asym, q_asym = extract_queue(asym_df, args.module, args.name)

    if t_sym is None or t_asym is None:
        print('Queue vectors not found')
        sys.exit(1)

    # Unit conversion (assume bit length -> bytes -> target unit if not packets)
    def convert(values):
        if args.unit == 'packets':
            return values  # if already packet length counts
        # assume bits -> bytes
        vals = values / 8.0
        if args.unit == 'KB':
            return vals / 1024.0
        if args.unit == 'MB':
            return vals / (1024.0*1024.0)
        return vals

    q_sym_c = convert(q_sym)
    q_asym_c = convert(q_asym)

    fig, axes = plt.subplots(1,2, figsize=(12,4), sharey=True)
    axes[0].plot(t_sym, q_sym_c, color='steelblue')
    axes[0].set_title(f'Symmetric')
    axes[1].plot(t_asym, q_asym_c, color='darkorange')
    axes[1].set_title('Asymmetric (5Gbps link)')
    for ax in axes:
        ax.set_xlabel('Time (s)')
    axes[0].set_ylabel(f'Queue ({args.unit})')
    if args.k is not None and args.unit != 'packets':
        for ax in axes:
            ax.axhline(args.k, color='red', linestyle='--', linewidth=1.0)
    fig.suptitle(f'Queue Comparison K={args.k} N/Ax')
    fig.tight_layout(rect=[0,0,1,0.95])
    out=os.path.abspath(args.output)
    fig.savefig(out, dpi=100)
    print('wrote', out)
