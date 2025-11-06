# Cloud DCN ECN Simulation

> Repository pointer: https://github.com/yeshenghua/cloud-dcn-ecn

> Status update (Nov 2025): pipeline validated end-to-end (traffic → sim → export → plots/FCT); batch runners added; initial figures and CSVs are under `figs/` and `results/`.

## Overview
This project evaluates Explicit Congestion Notification (ECN) behavior and queue thresholds in a small leaf-spine datacenter network using OMNeT++/INET. It provides:
- A configurable topology (`sim/dcn/SmallLeafSpine.ned`)
- Flow generation scripts (`scripts/traffic.py`, `scripts/traffic_incast.py`) that populate `sim/flows.inc`
- Simulation configuration (`sim/omnetpp.ini`) with baseline (DropTail) and ECN (RED-like hard threshold) variants (`k10`, `k30`, `k60`, `k120`) and incast mixes
- Post-processing & plotting (`scripts/plot_sanity.py`) to quickly visualize a representative queue or drop vector
- Batch runners for grids and fixed-K (`scripts/run_grid.sh`, `scripts/run_fixed_k.sh`)
- FCT extraction and aggregations (`analysis/fct_extract.py`, `analysis/plot_fct_vs_k.py`) and queue comparisons (`analysis/plot_queue_compare.py`)

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
- `sim/omnetpp.ini`: Defines configs `sym`, `incast8`, and ECN threshold variants `k10|k30|k60|k120`, plus combined incast configs `incast8_k10|30|60|120`
- `sim/flows.inc`: Auto-generated flow definitions included by `omnetpp.ini`
 - `analysis/milestone.md`: Running notes on deliverables, figures to paste, and next steps

## Environment (macOS + OMNeT++/INET)
- OMNeT++ 6.2.x
- INET built (e.g., clang-release). On macOS, pass the absolute INET dylib with `-l` and ensure it’s discoverable via `DYLD_LIBRARY_PATH` when needed.

Helpful environment variables used by the batch scripts:
- `OMNETPP_BIN` — path to OMNeT++ binaries (e.g., `~/Downloads/omnetpp-6.2.0/bin`)
- `SCAVE_BIN` — path to `opp_scavetool` (often the same as `OMNETPP_BIN`)
- `INET_NED` — path to INET NEDs (e.g., `~/Projects/inet/src`)
- `INET_LIB` — absolute path to `libINET.dylib` (e.g., `~/Projects/inet/out/clang-release/src/libINET.dylib`)
- `DYLD_LIBRARY_PATH` — should include the INET build dir containing the dylib

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
opp_run -n .:sim:${INET_NED} -f sim/omnetpp.ini -c sym -l ${INET_LIB}
opp_run -n .:sim:${INET_NED} -f sim/omnetpp.ini -c incast8 -l ${INET_LIB}
# Fixed-K ECN (Route 1: RedDropperQueue, no code) — see section below
opp_run -n .:sim:${INET_NED} -f sim/omnetpp.ini -c incast8_k10 -l ${INET_LIB}
opp_run -n .:sim:${INET_NED} -f sim/omnetpp.ini -c incast8_k30 -l ${INET_LIB}
opp_run -n .:sim:${INET_NED} -f sim/omnetpp.ini -c incast8_k60 -l ${INET_LIB}
opp_run -n .:sim:${INET_NED} -f sim/omnetpp.ini -c incast8_k120 -l ${INET_LIB}
```
Notes:
- `-n .:sim:${INET_NED}` adds current and `sim/` directories plus INET to the NED path
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
opp_run -n .:sim -f sim/omnetpp.ini -c incast8_k120
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

Advanced usage (explicit CSV, output file, unit conversion, threshold line):
```bash
python scripts/plot_sanity.py \
   --module 'leaf[0].ppp[2].queue' \
   --name 'queueBitLength' \
   --source_csv results/incast8_k30_vectors.csv \
   --output figs/incast8_k30_queue.png \
   --y_unit KB \
   --k 30 --k_unit KB
```
Flags:
- `--source_csv`: select a specific exported vectors CSV
- `--output`: custom figure path
- `--y_unit`: convert queue length to B/KB/MB
- `--k`, `--k_unit`: draw horizontal threshold reference line

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
| macOS cannot load INET | Use `-l ${INET_LIB}` with an absolute path; ensure `DYLD_LIBRARY_PATH` includes the INET build dir. |
| zsh globbing eats brackets | Quote module/name arguments, e.g., `'leaf[0].ppp[2].queue'`. |

## Data & Reproducibility
- Random seeds fixed to 1 in traffic scripts for reproducible flow patterns.
- Modify seeds or parameters (`ROUNDS`, `GAP`, sizes) in `scripts/traffic_incast.py` for variability.
- Adjust `LOAD`, `MICE_FRAC`, sizes, and `DURATION` in `scripts/traffic.py` for different stress levels.

## Next Steps / Extensions
- Add latency & throughput post-processing (e.g., parsing `omnetpp.sca` into pandas).
- Automate multi-config batch runs with a shell/Python driver.
- Introduce DCTCP-style marking (if INET build supports it) for deeper comparison.

## Batch Fixed-K Runner

Use the helper script to run all threshold configs and plot automatically:
```bash
./scripts/run_fixed_k.sh                # runs k30,k60,k120
./scripts/run_fixed_k.sh --incast8      # runs incast8_k30, incast8_k60, incast8_k120
./scripts/run_fixed_k.sh --only k60     # just k60
```
Outputs:
- Simulation raw: `sim/results/<config>/`
- Exported CSVs: `results/<config>_vectors.csv`, `results/<config>_scalars.csv`
- Figures: `figs/<config>_sanity_queue.png`

## Batch Grid Runner (K × Load × N × scenario × seeds)

Use the grid runner to automate multiple configs with environment overrides:
```bash
export OMNETPP_BIN=~/Downloads/omnetpp-6.2.0/bin
export SCAVE_BIN="$OMNETPP_BIN"
export INET_NED=~/Projects/inet/src
export INET_LIB=~/Projects/inet/out/clang-release/src/libINET.dylib
export DYLD_LIBRARY_PATH=~/Projects/inet/out/clang-release/src

./scripts/run_grid.sh \
   --Ks "10 30 60" \
   --Ls "0.6" \
   --Ns "8" \
   --Scenarios "sym asym" \
   --Seeds "1"
```
Artifacts per case land under `results/` and `figs/` (CSV exports and sanity plots). The script injects `-l ${INET_LIB}` automatically.

## Asymmetry Scenario
The NED topology uses a parametric `EthChan` channel, so link datarates can be overridden at runtime. The `asym` scenario sets a 5Gbps uplink on the ToR→Spine port to emulate bottleneck asymmetry; the grid runner toggles this via config.

## FCT Extraction and Plots
Compute per-flow FCT from vectors and aggregate percentiles:
```bash
python analysis/fct_extract.py \
   --vectors results/fixk_K30_L0.6_N8_sym_s1_vectors.csv \
   --rx-host 0 \
   --out_flows results/fct_flows.csv \
   --out_summary results/fct_summary.csv

python analysis/plot_fct_vs_k.py \
   --summary results/fct_summary.csv \
   --L 0.6 --N 8 --scenario sym \
   --output figs/fct_vs_k_L0.6_N8_sym.png
```
Compare symmetric vs asymmetric queue traces side-by-side:
```bash
python analysis/plot_queue_compare.py \
   --sym results/fixk_K30_L0.6_N8_sym_s1_vectors.csv \
   --asym results/fixk_K30_L0.6_N8_asym_s1_vectors.csv \
   --module 'leaf[0].ppp[2].queue' \
   --name 'incomingPacketLengths' \
   --k 30 \
   --output figs/queue_compare_K30_L0.6_N8_s1.png
```

## License
Add your chosen license here (e.g., MIT); currently unspecified.

---
Feel free to replace placeholder paths with your actual OMNeT++ install and add any institution/report references required for submission.
