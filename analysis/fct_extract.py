#!/usr/bin/env python3
import argparse, os, sys, pandas as pd, numpy as np, re

# Minimal skeleton to compute per-flow FCT percentiles from vectors CSV.
# Strategy:
# - Try rcvdBytes:vector or rcvdPk:vector(packetBytes) on RX host[0] apps
# - Infer per-app sendBytes from flows.inc by parsing sendBytes lines
# - For each (host[0].app[i]), find first timestamp (first packet) and time when cumulative bytes >= sendBytes
# - Output summary CSV with P50/P95/P99 for each input file

INC_PATH = os.path.join(os.path.dirname(__file__), '..', 'sim', 'flows.inc')

def build_sig_candidates(rx_host):
    prefix = f'SmallLeafSpine.host[{rx_host}].app['
    return [
        (prefix, 'rcvdBytes:vector'),
        (prefix, 'rcvdPk:vector(packetBytes)'),
        (prefix, 'packetReceived:vector(packetBytes)'),
    ]

def parse_flows_inc(path, rx_host):
    send = {}
    try:
        with open(path, 'r') as f:
            for line in f:
                line=line.strip()
                if not line or 'sendBytes' not in line: continue
                # **.host[H].app[I].sendBytes = XXXB
                try:
                    lhs, rhs = line.split('=',1)
                    rhs = rhs.strip()
                    if rhs.endswith('B'): rhs = rhs[:-1]
                    bytes_ = int(rhs)
                    # extract host and app index
                    # lhs like: **.host[0].app[12].sendBytes
                    parts = lhs.split('.')
                    h = int(parts[2].split('[')[1].split(']')[0])
                    a = int(parts[3].split('[')[1].split(']')[0])
                    if h==rx_host:
                        send[a] = bytes_
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return send

def pick_vector_columns(df, rx_host):
    """Yield (base, tcol, vcol) for vectors belonging to host[rx_host].app[*].
    Supports two formats:
      A) Wide multi-column: each vector has <base>:vectime / <base>:vecvalue columns.
      B) Row-wise opp_scavetool export: row with columns 'module','name','vectime','vecvalue'.
    """
    cols = [c for c in df.columns if c.endswith(':vectime') or c.endswith(':vecvalue')]
    if cols:  # Format A
        bases = set(c.rsplit(':',1)[0] for c in cols)
        for prefix, sig in build_sig_candidates(rx_host):
            for b in bases:
                if prefix in b and b.endswith(sig):
                    tcol = b+':vectime'; vcol = b+':vecvalue'
                    if tcol in df.columns and vcol in df.columns:
                        yield b, tcol, vcol
    else:  # Format B
        host_pat = re.compile(rf"\.host\[{rx_host}\]\.app\[(\d+)\]\.")
        for _, row in df.iterrows():
            mod = str(row.get('module',''))
            if not host_pat.search(mod):
                continue
            base = f"{mod}.{row.get('name','')}"
            yield base, 'vectime', 'vecvalue'

def parse_list_field(cell):
    s = str(cell).strip()
    if not s:
        return []
    if s[0] in '{[' and s[-1] in '}]':
        s = s[1:-1]
    parts = re.split(r"[\s,;]+", s)
    out = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(float(p))
        except ValueError:
            pass
    return out

def fct_from_vectors(csv_path, rx_host):
    df = pd.read_csv(csv_path)
    send_map = parse_flows_inc(os.path.abspath(INC_PATH), rx_host)
    fcts = []
    for b, tcol, vcol in pick_vector_columns(df, rx_host):
        try:
            app_idx = int(b.split('app[')[1].split(']')[0])
        except Exception:
            continue
        if app_idx not in send_map:
            continue
        need = send_map[app_idx]
        # Format A: columns hold space-separated lists in first row; Format B: vectime/vecvalue columns per row
        col_t = df[tcol] if tcol in df.columns else None
        col_v = df[vcol] if vcol in df.columns else None
        if col_t is None or col_v is None:
            continue
        # For Format B each row is separate vector; select the row matching current base
        if not any(c.endswith(':vectime') for c in df.columns):
            # filter to matching module+name
            mdf = df[(df['module'].astype(str).str.contains(f"host\[{rx_host}\]\.app\[{app_idx}\]")) & (df['name'].astype(str).str.contains('rcvdBytes|rcvdPk|packetReceived|endToEndDelay'))]
            if mdf.empty:
                continue
            # take first match
            row = mdf.iloc[0]
            t_list = parse_list_field(row['vectime'])
            v_list = parse_list_field(row['vecvalue'])
        else:
            # wide format: explode all rows of tcol/vcol
            t_list = df[tcol].dropna().astype(str).str.split().explode().astype(float).to_list()
            v_list = df[vcol].dropna().astype(str).str.split().explode().astype(float).to_list()
        if not t_list or not v_list:
            continue
        t = np.asarray(t_list)
        v = np.asarray(v_list)
        if ('rcvdPk' in b) or ('packetReceived' in b):
            v = np.cumsum(v)
        nz = np.where(v>0)[0]
        if nz.size == 0:
            continue
        start_t = t[nz[0]]
        done_idx = np.where(v>=need)[0]
        if done_idx.size == 0:
            continue
        done_t = t[done_idx[0]]
        fcts.append(done_t - start_t)
    return fcts

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--vectors', nargs='+', required=True, help='vectors CSV paths')
    ap.add_argument('--rx-host', type=int, default=0, help='Receiver host index (default 0)')
    ap.add_argument('--out_flows', default='results/fct_flows.csv')
    ap.add_argument('--out_summary', default='results/fct_summary.csv')
    args = ap.parse_args()

    flow_rows = []
    summary_rows = []
    for vpath in args.vectors:
        fcts = fct_from_vectors(vpath, args.rx_host)
        if fcts:
            arr = np.array(fcts)
            summary_rows.append({
                'file': os.path.basename(vpath),
                'count': len(arr),
                'p50_ms': float(np.percentile(arr,50)*1000.0),
                'p95_ms': float(np.percentile(arr,95)*1000.0),
                'p99_ms': float(np.percentile(arr,99)*1000.0),
            })
            for val in arr:
                flow_rows.append({'file': os.path.basename(vpath), 'fct_ms': float(val*1000.0)})
        else:
            summary_rows.append({ 'file': os.path.basename(vpath), 'count': 0 })

    os.makedirs(os.path.dirname(args.out_summary), exist_ok=True)
    pd.DataFrame(flow_rows).to_csv(args.out_flows, index=False)
    pd.DataFrame(summary_rows).to_csv(args.out_summary, index=False)
    print('wrote', args.out_flows)
    print('wrote', args.out_summary)
