# Cloud DCN ECN Simulation

> Repository pointer: https://github.com/yeshenghua/cloud-dc://github.com/yeshenghua/cloud-dcndecnecn
n>
> Status update checklist: ✅ Codebase pointer ✅ README with setup & usage

## Overview
This project evaluates Explicit Congestion Notification (ECN) behavior and queue thresholds in a small leaf-spine datacenter network using OMNeT++/INET. It provides:
- A configurable topology (`sim/dcn/SmallLeafSpine.ned`)
- Flow generation scripts (`scripts/traffic.py`, `scripts/traffic_incast.py`) that populate `sim/flows.inc`
- Simulation configuration (`sim/omnetpp.ini`) with baseline (DropTail) and ECN (RED-like hard threshold) variants (`k10`, `k30`, `k60`) and incast mixes
- Post-processing & plotting (`scripts/plot_sanity.py`) to quickly visualize a representative queue or drop vector

## Repository Structure
```
omnetpp.sca / .vci / .vec   # (Top-level sample results – may be stale)
analysis/                    # (Optional analysis artifacts)
figs/                        # Generated figures (e.g., incast8_sanity_queue.png)
results/                     # Output directories per config (sym, incast8, kXX, ...)
scripts/                     # Python helpers (traffic generation & plotting)
sim/                         # Simulation inputs (NED, omnetpp.ini, generated flows.inc)
```
Key files:
- `sim/dcn/SmallLeafSpine.ned`: 4-leaf spine topology, 3 hosts per leaf (total 12 hosts)
- `sim/omnetpp.ini`: Defines configs `sym`, `incast8`, and ECN threshold variants `k10|k30|k60`, plus combined incast configs `incast8_k10|30|60`
- `sim/flows.inc`: Auto-generated flow definitions included by `omnetpp.ini`

## Prerequisites
1. OMNeT++ 6.2.x (paths assume you extracted to `~/Downloads/omnetpp-6.2.0` — adjust as needed)
2. INET (if required for queue modules; ensure it's compiled and in your OMNeT++ project search path)
3. Python 3.9+ with packages listed in `requirements.txt`
4. (Optional) A virtual environment

## Python Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Generating Traffic
Two modes:
1. Synthetic mixed workload (load-controlled):
   ```bash
   python scripts/traffic.py 0.6   # 60% target load (default if arg omitted)
   ```
2. Incast pattern (N senders → 1 victim + overlapping elephant):
   ```bash
   python scripts/traffic_incast.py 8  # N=8 (default if omitted)
   ```
Both commands overwrite `sim/flows.inc`.

## Running Simulations
From repo root (adjust OMNeT++ executable path if not on PATH):
```bash
opp_run -n .:sim -f sim/omnetpp.ini -c sym
opp_run -n .:sim -f sim/omnetpp.ini -c incast8
# Fixed-K ECN (Route 1: RedDropperQueue, no code) — see section below
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k10
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k30
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k60
```
Notes:
- `-n .:sim` adds current and `sim/` directories to NED path (include INET if needed: `-n .:sim:/path/to/inet/src`)
- Output goes to `results/<config>/` (e.g., `results/sym/omnetpp.vec`)
- If `markEcn` / `ecnEnabled` parameters cause unknown parameter errors, comment them out in `sim/omnetpp.ini` (these vary across INET versions).

## Fixed-K ECN without code (Route 1)

Configs `k10|k30|k60` extend an `ecn` base that switches interface queues to `inet.queueing.queue.RedDropperQueue` and sets:
- `minth = maxth = K` (packets) as the hard threshold
- `wq = 0` (disable EWMA) and `maxp = 1` (100% action above threshold)
- Try ECN marking if available: `markEcn = true`, `ecnMarking = true` (names vary across INET versions); otherwise RED will drop above K, which still gives a close Fixed-K behavior for pipeline testing.

Run incast variants:
```bash
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k10
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k30
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k60
```

Tip: to focus the ToR→RX queue in plots, pass a module/name filter:
```bash
python scripts/plot_sanity.py --module 'leaf[0].ppp[2].queue' --name 'queueBitLength'
```

## Exporting Vectors (If Needed)
`plot_sanity.py` auto-detects or exports a `_vectors.csv` using `opp_scavetool` if missing.
Manual example:
```bash
~/Downloads/omnetpp-6.2.0/bin/opp_scavetool export -T v \
  -o results/incast8_vectors.csv results/incast8/omnetpp.vec
```

## Plotting a Sanity Figure
```bash
python scripts/plot_sanity.py
```
Behavior:
- Locates `results/*_vectors.csv` or exports one from `results/incast8/omnetpp.vec`
- Picks a queue length vector with largest variation (else a drop counter with max growth)
- Downsamples to ≤20k points
- Saves `figs/incast8_sanity_queue.png` (or `_drop.png`)

## Interpreting Output
- Queue plot lets you visually check if thresholding (K) behaves correctly (flat below K, instantaneous ECN marking above K).
- For incast configs, look for burst-induced queue spikes; compare K variants to gauge marking aggressiveness.
- Drop vs ECN: Ideally near-zero drops with ECN marking enabled.

## Troubleshooting
| Symptom | Hint |
|---------|------|
| Unknown parameter `markEcn` | Comment out `**.ppp[*].queue.markEcn` lines; feature name differs in INET version. |
| Empty or missing vectors CSV | Ensure `**.vector-recording = true` and run a config that produces traffic; re-run export. |
| Plot script exits with CSV error | Use `opp_scavetool export -T v` (row-wise wide format required). |
| No ECN marking observed | Verify queue type actually supports ECN; check module typename; ensure `**.tcp.ecn = true`. |
| Too many drops | Confirm large `packetCapacity` settings; ensure RED thresholds set to K (minth=maxth). |

## Data & Reproducibility
- Random seeds fixed to 1 in traffic scripts for reproducible flow patterns.
- Modify seeds or parameters (`ROUNDS`, `GAP`, sizes) in `scripts/traffic_incast.py` for variability.
- Adjust `LOAD`, `MICE_FRAC`, sizes, and `DURATION` in `scripts/traffic.py` for different stress levels.

## Next Steps / Extensions
- Add latency & throughput post-processing (e.g., parsing `omnetpp.sca` into pandas).
- Automate multi-config batch runs with a shell/Python driver.
- Introduce DCTCP-style marking (if INET build supports it) for deeper comparison.

## License
Add your chosen license here (e.g., MIT); currently unspecified.

---
Feel free to replace placeholder paths with your actual OMNeT++ install and add any institution/report references required for submission.
