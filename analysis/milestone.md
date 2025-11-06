# Milestone

Shenghua Ye, Yuheng Hou

codebase: https://github.com/yeshenghua/cloud-dcn-ecn

## 1. Executive Summary
This milestone establishes a reproducible OMNeT++/INET simulation environment to study Fixed-K ECN (RED with minth=maxth=K) under incast traffic in a small leaf–spine topology. We validated instrumentation (queue vectors + per-flow receive traces enabling Flow Completion Time / FCT extraction) and produced initial queue evolution and FCT vs K results for a reduced experimental slice: K ∈ {10,30,60}, load L=0.6, fan-in N=8, symmetric vs one asymmetric (5 Gbps uplink) scenario, seed=1.

## 2. Scope Covered in This Phase
| Dimension | Values Implemented | Notes |
|-----------|--------------------|-------|
| K (packets) | 10, 30, 60 | Implemented via RED minth=maxth=K. |
| Load (L) | 0.6 | Scaling incast burst gap for offered load approximation. |
| Incast fan-in (N) | 8 | N=16 configs prepared (not yet run in this slice). |
| Scenario | symmetric, asymmetric (5 Gbps bottleneck link) | Bottleneck enforced via runtime override. |
| Seeds | 1 (validation) | Scripts parameterized for ≥5 seeds next phase. |
| Metrics | Queue trace, FCT (p50/p95/p99) | FCT derived from receiver app vectors. |

## 3. Environment & Reproducibility
- OMNeT++: 6.2.0 (Academic Public License)
- INET: compiled (clang-release) — dynamic library loaded via absolute path.
- Topology: `sim/dcn/SmallLeafSpine.ned` (parametric channel `EthChan`).
- Configurations: `omnetpp.ini` (baseline, ECN, K variants, incast8 / incast16).
- Traffic: `scripts/traffic_incast.py` (args: N, Load, Seed) generating `sim/flows.inc`.
- Batch drivers: `scripts/run_grid.sh` (grid), `scripts/run_fixed_k.sh` (quick K sweep).
- Post-processing: `analysis/fct_extract.py`, `analysis/plot_fct_vs_k.py`, `scripts/plot_sanity.py`.

### Required Runtime Exports (macOS example)
```
export OMNETPP_BIN="/Users/ye/Downloads/omnetpp-6.2.0/bin/opp_run"
export SCAVE_BIN="/Users/ye/Downloads/omnetpp-6.2.0/bin/opp_scavetool"
export INET_NED="/Users/ye/Projects/inet/src"
export INET_LIB="/Users/ye/Projects/inet/out/clang-release/src/libINET.dylib"
export DYLD_LIBRARY_PATH="/Users/ye/Projects/inet/out/clang-release/src"
```

## 4. Data Artifacts (Current Phase)
Location: `results/`
- Raw vectors/scalars (per case):
  - `fixk_K{10,30,60}_L0.6_N8_sym_s1_vectors.csv` / `_scalars.csv`
  - `fixk_K{10,30,60}_L0.6_N8_asym_s1_vectors.csv` / `_scalars.csv`
- FCT summaries:
  - `fct_L0.6_N8_sym_flows.csv` (per-flow FCT ms)
  - `fct_L0.6_N8_sym_summary.csv` (p50/p95/p99)
- Sanity & baseline: `incast8_vectors.csv`, `incast8_k30_vectors.csv`, etc.



## 5. Methodology Snapshot
1. Configure RED as a hard threshold: `minth=maxth=K`, `wq=0`, `maxp=1`, `gentle=false`.
2. Enable ECN marking flags (fallback to drops if unsupported) + large `packetCapacity` to isolate marking effects.
3. Generate incast flows (ROUNDS=20 bursts) with optional load scaling of inter-burst GAP.
4. Record receiver (host[0]) application vectors for cumulative bytes and per-packet arrivals.
5. Derive FCT as (first byte arrival timestamp → cumulative bytes ≥ sendBytes).
6. Export vectors/scalars with opp_scavetool; aggregate percentiles using pandas.

## 6. Preliminary Findings
- Queue Growth: Larger K values result in visibly higher sustained queue plateaus; asymmetry exacerbates peaks.
- RED Behavior: For single seed the RED queue length (RED internal vector shows incoming packet length stream) clamps near K but short bursts still accumulate around the threshold.
- Tail Latency: P95/P99 FCT appears to increase with K (expected: higher threshold → larger standing queue → added queuing delay). Statistical confidence requires multi-seed.

## 7. Outstanding Actions (Next Milestone)
| Action | Purpose | Script / Command Hint |
|--------|---------|------------------------|
| Run additional loads L=0.3,0.8 | Coverage of traffic intensity | Set `Ls="0.3 0.6 0.8"` and re-run grid |
| Add N=16 runs | Fan-in sensitivity | `Ns="8 16"` |
| Multi-seed (≥5) | Confidence in P95/P99 | `Seeds="1 2 3 4 5"` |
| Generate asym FCT plot | Compare tail latency shift | `plot_fct_vs_k.py --scenario asym` |
| Side-by-side queue comparison | Visual asym impact | `plot_queue_compare.py` |
| K reference in packets | Convert to bytes (MSS) or add packet unit mode | Extend `plot_sanity.py` |
| Aggregate summary table | Single CSV for all (K,L,N,scenario) | Post-process `fct_summary.csv` |
| Normalized FCT (rel. to K=30) | Easier cross-load comparison | Add ratio column (current / baseline) |

### Example Commands (after full grid)
```
# Extract all FCTs
auth python analysis/fct_extract.py --vectors results/*_vectors.csv \
  --rx-host 0 --out_flows results/fct_flows.csv --out_summary results/fct_summary.csv

# Plot FCT vs K (asym) once data exists
python analysis/plot_fct_vs_k.py --summary results/fct_summary.csv \
  --L 0.6 --N 8 --scenario asym --metric median \
  --output figs/fct_vs_k_L0.6_N8_asym.png

# Side-by-side queue (K=30 example)
python analysis/plot_queue_compare.py \
  --sym results/fixk_K30_L0.6_N8_sym_s1_vectors.csv \
  --asym results/fixk_K30_L0.6_N8_asym_s1_vectors.csv \
  --output figs/queue_compare_K30_L0.6_N8_s1.png \
  --module 'leaf[0].ppp[2].queue' --name 'incomingPacketLengths' --k 30 --unit KB
```

## 8. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Single seed variability | Misleading tail trends | Run ≥5 seeds; use median across seeds. |
| K shown as KB not packets | Misinterpretation of threshold scale | Add packets-to-bytes (MSS) conversion or separate packets unit axis. |
| Incomplete asym FCT plot | Missing comparative insight | Prioritize asym FCT extraction next run. |
| Eventlog size growth | Storage pressure | Keep eventlog only until signal vectors validated; then disable if not needed. |

