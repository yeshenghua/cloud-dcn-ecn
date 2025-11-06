#!/usr/bin/env python3
import argparse, os, sys, pandas as pd, numpy as np

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
    # Return the column names for the best available signal type
    cols = [c for c in df.columns if c.endswith(':vectime') or c.endswith(':vecvalue')]
    # group by base name
    bases = set(c.rsplit(':',1)[0] for c in cols)
    # prefer rcvdBytes over rcvdPk(packetBytes)
    for prefix, sig in build_sig_candidates(rx_host):
        for b in bases:
            if prefix in b and b.endswith(sig):
                tcol = b+':vectime'; vcol = b+':vecvalue'
                if tcol in df.columns and vcol in df.columns:
                    yield b, tcol, vcol

def fct_from_vectors(csv_path, rx_host):
    df = pd.read_csv(csv_path)
    send_map = parse_flows_inc(os.path.abspath(INC_PATH), rx_host)
    fcts = []
    for b, tcol, vcol in pick_vector_columns(df, rx_host):
        # extract app index from base string
        # example base: SmallLeafSpine.host[0].app[12].rcvdBytes:vector
        try:
            app_idx = int(b.split('app[')[1].split(']')[0])
        except Exception:
            continue
        if app_idx not in send_map: 
            continue
        need = send_map[app_idx]
        t = df[tcol].dropna().astype(str).str.split().explode().astype(float).to_numpy()
        v = df[vcol].dropna().astype(str).str.split().explode().astype(float).to_numpy()
        if len(t)==0 or len(v)==0: 
            continue
        # cumulative since vectors may be increments for rcvdPk(packetBytes)
        if ('rcvdPk' in b) or ('packetReceived' in b):
            v = np.cumsum(v)
        # first non-zero time as start
        try:
            start_idx = np.where(v>0)[0][0]
        except IndexError:
            continue
        start_t = t[start_idx]
        # time reach target bytes
        done_idx = np.where(v>=need)[0]
        if len(done_idx)==0:
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
