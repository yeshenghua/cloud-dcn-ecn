#!/usr/bin/env python3
import argparse, sys, os
import pandas as pd
import numpy as np

USECOLS = ["run","type","module","name","vectime","vecvalue"]

def load_vectors(path):
    df = pd.read_csv(path, usecols=USECOLS, low_memory=False)
    df = df[df["type"]=="vector"].copy()
    df["vectime"] = pd.to_numeric(df["vectime"], errors="coerce")
    df["vecvalue"] = pd.to_numeric(df["vecvalue"], errors="coerce")
    df = df.dropna(subset=["vectime","vecvalue"])
    return df

def pick_vectors(df, rx_host):
    mask_host = df["module"].astype(str).str.contains(rf"\.host\[{rx_host}\]\.", regex=True)
    return df[mask_host].copy()

def fct_from_bytes_series(times, values, is_pkt_bytes=False):
    idx = np.argsort(times)
    t = np.asarray(times)[idx]
    v = np.asarray(values)[idx]
    if is_pkt_bytes:
        v = np.cumsum(v)
    started = np.where(v > 0)[0]
    if started.size == 0:
        return None
    t0 = t[started[0]]
    v_end = v[-1]
    t1 = t[np.where(v >= v_end)[0][0]]
    return dict(t_start=float(t0), t_end=float(t1), bytes_total=float(v_end), fct_s=float(max(0.0, t1-t0)))

def fct_from_e2e_times(times):
    # times 是每包到达的时间戳；FCT≈最后一包到达 - 第一包到达
    if len(times)==0:
        return None
    t0 = float(np.min(times))
    t1 = float(np.max(times))
    return dict(t_start=t0, t_end=t1, bytes_total=float('nan'), fct_s=float(max(0.0, t1-t0)))

def main():
    ap = argparse.ArgumentParser(description="Extract per-flow FCT from vectors CSV (bytes or fallback to endToEndDelay)")
    ap.add_argument("--vectors", required=True)
    ap.add_argument("--rx-host", type=int, default=0)
    ap.add_argument("--out_flows", required=True)
    ap.add_argument("--out_summary", required=True)
    args = ap.parse_args()

    if not os.path.isfile(args.vectors):
        sys.exit(f"[ERR] vectors CSV not found: {args.vectors}")

    df = load_vectors(args.vectors)
    rx = pick_vectors(df, args.rx_host)
    if rx.empty:
        sys.exit(f"[ERR] No vectors under host[{args.rx_host}] in {args.vectors}")

    # 三类候选统计
    key_bytes   = "rcvdBytes:vector"
    key_pkbytes = "rcvdPk:vector(packetBytes)"
    key_e2e     = "endToEndDelay:vector"

    have_bytes   = rx["name"].eq(key_bytes).any()
    have_pkbytes = rx["name"].eq(key_pkbytes).any()
    have_e2e     = rx["name"].eq(key_e2e).any()

    if not (have_bytes or have_pkbytes or have_e2e):
        inv = (rx.groupby(["module","name"]).size().reset_index(name="rows")
                 .sort_values("rows", ascending=False))
        inv_path = os.path.splitext(args.out_summary)[0] + "_inventory.csv"
        inv.to_csv(inv_path, index=False)
        sys.exit(
            f"[ERR] Not found any of [{key_bytes} | {key_pkbytes} | {key_e2e}] under host[{args.rx_host}]. "
            f"Wrote inventory to {inv_path}. Open it to see what *is* available, or enable recording in omnetpp.ini."
        )

    rows = []

    # 1) rcvdBytes:vector
    if have_bytes:
        for (mod, name), g in rx[rx["name"].eq(key_bytes)].groupby(["module","name"], sort=False):
            res = fct_from_bytes_series(g["vectime"], g["vecvalue"], is_pkt_bytes=False)
            if res: rows.append({"module":mod, "name":name, **res})

    # 2) rcvdPk:vector(packetBytes)
    if have_pkbytes:
        for (mod, name), g in rx[rx["name"].eq(key_pkbytes)].groupby(["module","name"], sort=False):
            res = fct_from_bytes_series(g["vectime"], g["vecvalue"], is_pkt_bytes=True)
            if res: rows.append({"module":mod, "name":name, **res})

    # 3) fallback: endToEndDelay:vector（只用时间窗口，bytes_total 为 NaN）
    if not rows and have_e2e:
        for (mod, name), g in rx[rx["name"].eq(key_e2e)].groupby(["module","name"], sort=False):
            res = fct_from_e2e_times(g["vectime"])
            if res: rows.append({"module":mod, "name":name, **res})

    if not rows:
        sys.exit("[ERR] Could not derive any FCT from available vectors.")

    flows = pd.DataFrame(rows).sort_values("fct_s")
    os.makedirs(os.path.dirname(args.out_flows), exist_ok=True)
    flows.to_csv(args.out_flows, index=False)

    qs = [0.5, 0.95, 0.99]
    pct = {f"P{int(q*100)}": flows["fct_s"].quantile(q) for q in qs}
    summary = pd.DataFrame([{
        "rx_host": args.rx_host,
        "flows": len(flows),
        **pct
    }])
    os.makedirs(os.path.dirname(args.out_summary), exist_ok=True)
    summary.to_csv(args.out_summary, index=False)

    print(f"[ok] wrote {args.out_flows} ({len(flows)} flows)")
    print(f"[ok] wrote {args.out_summary}: {summary.to_dict(orient='records')[0]}")

if __name__ == "__main__":
    main()
