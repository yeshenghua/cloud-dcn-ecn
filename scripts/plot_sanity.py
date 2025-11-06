#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sanity plot from OMNeT++/INET vectors.
- Prefer queue length vectors with largest variation; fallback to drop/loss with largest increase.
- Handles both wide (vectime/vecvalue) and row-wise (time/value) csv from opp_scavetool -T v.
"""

import os, re, sys, math, json, shlex, subprocess as sp
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/cloud-dcn-ecn")
RESULTS = os.path.join(BASE, "results")
FIG_DIR = os.path.join(BASE, "figs")
os.makedirs(FIG_DIR, exist_ok=True)

def find_vectors_csv():
    preferred = os.path.join(RESULTS, "incast8_vectors.csv")
    if os.path.exists(preferred):
        return preferred
    for fn in os.listdir(RESULTS):
        if fn.endswith("_vectors.csv"):
            return os.path.join(RESULTS, fn)
    vec_raw = os.path.join(RESULTS, "incast8", "omnetpp.vec")
    scavetool = os.path.expanduser("~/Downloads/omnetpp-6.2.0/bin/opp_scavetool")
    if os.path.exists(vec_raw) and os.path.exists(scavetool):
        outcsv = preferred
        cmd = f'{shlex.quote(scavetool)} export -T v -o {shlex.quote(outcsv)} {shlex.quote(vec_raw)}'
        print(f"[info] exporting vectors CSV via: {cmd}")
        if sp.run(cmd, shell=True).returncode == 0 and os.path.exists(outcsv):
            return outcsv
    return None

parser = argparse.ArgumentParser(description="Sanity plot for OMNeT++ vectors")
parser.add_argument("--module", dest="module_substr", default=os.environ.get("PLOT_MODULE"),
                    help="Substring of module path to prioritize (e.g., 'leaf[0].ppp[2].queue')")
parser.add_argument("--name", dest="name_substr", default=os.environ.get("PLOT_NAME"),
                    help="Optional name substring to prefer (e.g., 'queueBitLength')")
args = parser.parse_args(args=[] if hasattr(sys, 'ps1') else None)

VEC_CSV = find_vectors_csv()
if not VEC_CSV:
    sys.exit("ERROR: vectors CSV not found. Export with: opp_scavetool export -T v -o results/incast8_vectors.csv results/incast8/omnetpp.vec")
print(f"[info] using vectors CSV: {VEC_CSV}")

df = pd.read_csv(VEC_CSV)
df.columns = [c.strip().lower() for c in df.columns]

for need in ("module","name"):
    if need not in df.columns:
        sys.exit("ERROR: CSV missing 'module'/'name' (use opp_scavetool -T v).")

HAS_WIDE = ("vectime" in df.columns) and ("vecvalue" in df.columns)
TIME_COL_WIDE, VAL_COL_WIDE = "vectime", "vecvalue"
TIME_COL_ROW,  VAL_COL_ROW  = ("time" if "time" in df.columns else None,
                               "value" if "value" in df.columns else None)

# Helpers -------------------------------------------------------------

def parse_list_field(cell):
    s = str(cell).strip()
    if not s:
        return []
    # 去掉可能的花括号
    if s[0] in "{[" and s[-1] in "}]":
        s = s[1:-1]
    parts = re.split(r"[,\s;]+", s)
    out = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(float(p))
        except ValueError:
            pass
    return out

def get_xy(group):
    """Return numeric (x,y) from a group of the same (module,name)."""
    if HAS_WIDE:
        row0 = group.iloc[0]
        x = parse_list_field(row0[TIME_COL_WIDE])
        y = parse_list_field(row0[VAL_COL_WIDE])
    else:
        if TIME_COL_ROW is None or VAL_COL_ROW is None:
            return [], []
        tx = pd.to_numeric(group[TIME_COL_ROW], errors="coerce")
        ty = pd.to_numeric(group[VAL_COL_ROW], errors="coerce")
        m = ~(tx.isna() | ty.isna())
        x = tx[m].to_list()
        y = ty[m].to_list()
    return x, y

def variation_score(y):
    if not y:
        return -1
    arr = np.asarray(y, dtype=float)
    return float(np.nanmax(arr) - np.nanmin(arr))

def growth_score(y):
    if not y:
        return -1
    arr = np.asarray(y, dtype=float)
    return float(arr[-1] - arr[0])

# Pick candidate ------------------------------------------------------

queue_name_pats = [re.compile(p, re.I) for p in (r"queue.*length", r"queueLength", r"\bqueue(len)?\b")]
drop_name_pats  = [re.compile(p, re.I) for p in (r"\bdrop\b", r"packet.*(drop|lost)", r"overflow")]

def filter_by_name(frame, pats):
    m = pd.Series(False, index=frame.index)
    for p in pats:
        m = m | frame["name"].astype(str).str.contains(p)
    return frame[m]

def best_signal(frame, score_fn):
    best = None
    best_rec = None
    # group by (module,name) and score each vector’s y-range / growth
    for (mod, name), grp in frame.groupby(["module","name"]):
        x, y = get_xy(grp)
        score = score_fn(y)
        if score <= 0:
            continue
        rec = {"module": str(mod), "name": str(name), "x": x, "y": y, "score": score}
        if best is None or score > best["score"]:
            best = rec
        if best_rec is None:
            best_rec = rec
    # fall back to any parsed (even if zero-variance) to avoid None
    return best or best_rec

# 先挑“队列长度里波动最大的”
target_frame = df
if args.module_substr:
    target_frame = target_frame[target_frame["module"].astype(str).str.contains(re.escape(args.module_substr), case=False, regex=True)]
if args.name_substr:
    target_frame = target_frame[target_frame["name"].astype(str).str.contains(re.escape(args.name_substr), case=False, regex=True)]

cand = None
if len(target_frame) > 0:
    # pick within target module/name first
    cand = best_signal(filter_by_name(target_frame, queue_name_pats), variation_score) or \
           best_signal(target_frame, variation_score)
if cand is None:
    cand = best_signal(filter_by_name(df, queue_name_pats), variation_score)
picked_kind = "queue"
if cand is None or not cand["x"] or not cand["y"]:
    # 再挑“丢包/丢失里增长最大的”
    cand = best_signal(filter_by_name(df, drop_name_pats), growth_score)
    picked_kind = "drop"

if cand is None or not cand["x"] or not cand["y"]:
    sys.exit("ERROR: Could not reconstruct any useful vector (queue or drop). Ensure vector recording is on and CSV contains vectime/vecvalue.")

x, y = cand["x"], cand["y"]
print(f"[info] picked {picked_kind} vector:")
print(f"  module = {cand['module']}")
print(f"  name   = {cand['name']}")
print(f"  points = {len(x)}, score={cand['score']:.3f}")

# Downsample to keep file small
MAX_POINTS = 20000
if len(x) > MAX_POINTS:
    step = math.ceil(len(x) / MAX_POINTS)
    x, y = x[::step], y[::step]
    print(f"[info] downsampled to {len(x)} points (step={step})")

# ---- Plot ----
out_png = os.path.join(FIG_DIR, f"incast8_sanity_{picked_kind}.png")
plt.figure(figsize=(8, 4.2))

# 阶梯线更适合离散向量
plt.step(x, y, where="post")

# 智能设置 y 轴标签
ylabel = "Counter / Value"
if picked_kind == "queue":
    ylabel = "Queue length (bits)" if "bit" in cand["name"].lower() else "Queue length (pkts)"
plt.xlabel("Time (s)")
plt.ylabel(ylabel)
plt.title(f"Incast=8 sanity — {picked_kind} vector\n{cand['module']} :: {cand['name']}")
plt.tight_layout()
plt.savefig(out_png, dpi=240)  # 更清晰
plt.close()
print(f"[ok] saved: {out_png}")
