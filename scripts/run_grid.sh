#!/usr/bin/env bash
set -euo pipefail
# Grid runner for Fixed-K ECN experiments
# Axes: K in {10,30,60}, Load L in {0.3,0.6,0.8}, N in {8,16}, Scenario {sym, asym}, Seeds {1..5}
# Requires: OMNETPP_BIN, SCAVE_BIN exported; INET_NED optional

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SIM_DIR="$ROOT_DIR/sim"
RES_DIR="$ROOT_DIR/results"
FIG_DIR="$ROOT_DIR/figs"
mkdir -p "$RES_DIR" "$FIG_DIR"

OMNETPP_BIN=${OMNETPP_BIN:-$(command -v opp_run || echo "")}
SCAVE_BIN=${SCAVE_BIN:-$(command -v opp_scavetool || echo "")}
if [[ -z "$OMNETPP_BIN" || -z "$SCAVE_BIN" ]]; then
  echo "ERROR: Set OMNETPP_BIN and SCAVE_BIN environment variables." >&2
  exit 1
fi
NED_PATH="$SIM_DIR"; [[ -n "${INET_NED:-}" ]] && NED_PATH="$SIM_DIR:$INET_NED"

# Optional shared libs for opp_run (default to load INET when INET_NED is provided)
OPP_LIBS=${OPP_LIBS:-}
if [[ -z "$OPP_LIBS" && -n "${INET_NED:-}" ]]; then
  inet_base="${INET_NED%/src}"
  inet_lib_default="$inet_base/out/clang-release/src/libINET.dylib"
  if [[ -n "${INET_LIB:-}" ]]; then
    OPP_LIBS=( -l "${INET_LIB}" )
  elif [[ -f "$inet_lib_default" ]]; then
    OPP_LIBS=( -l "$inet_lib_default" )
  else
    OPP_LIBS=( -l INET )
  fi
fi

# Axes (overridable via environment: Ks, Ls, Ns, Seeds, Scenarios)
Ks=(${Ks:-10 30 60})
Ls=(${Ls:-0.3 0.6 0.8})
Ns=(${Ns:-8 16})
Seeds=(${Seeds:-1 2 3 4 5})
Scenarios=(${Scenarios:-sym asym}) # asym implies a 5Gbps override on a chosen uplink

# Choose one deterministic link to throttle for asym: leaf[2].ppp[0]
ASYM_5G_LINE='*.leaf[2].ppp[0].channel.datarate=5Gbps'

run_case() {
  local K="$1"; local L="$2"; local N="$3"; local seed="$4"; local scen="$5"
  local cfg_name="fixk_K${K}_L${L}_N${N}_${scen}_s${seed}"
  echo "==> Case $cfg_name"

  # Generate flows.inc for this case
  if [[ "$scen" == "sym" ]]; then
    python3 "$ROOT_DIR/scripts/traffic_incast.py" "$N" "$L" "$seed"
  else
    # asym uses the same traffic; only channel override differs at runtime
    python3 "$ROOT_DIR/scripts/traffic_incast.py" "$N" "$L" "$seed"
  fi

  # Pick base config by N and K: incast8/incast16 combined with kXX
  local base_cfg="incast${N}_k${K}"
  # Additional runtime overrides: recording on, result dir, optional channel datarate throttle
  local overrides=(
    "--**.scalar-recording=true"
    "--**.vector-recording=true"
    "--result-dir=results/$cfg_name"
  )
  if [[ "$scen" == "asym" ]]; then
    overrides+=("--$ASYM_5G_LINE")
  fi

  (cd "$SIM_DIR" && \
    "$OMNETPP_BIN" -u Cmdenv -n "$NED_PATH" ${OPP_LIBS[@]:-} -f omnetpp.ini -c "$base_cfg" "${overrides[@]}")

  # Export
  "$SCAVE_BIN" x "$SIM_DIR/results/$cfg_name/omnetpp.vec" -o "$RES_DIR/${cfg_name}_vectors.csv" || true
  "$SCAVE_BIN" x "$SIM_DIR/results/$cfg_name/omnetpp.sca" -o "$RES_DIR/${cfg_name}_scalars.csv" || true

  # Quick queue sanity plot (ToR->RX)
  python3 "$ROOT_DIR/scripts/plot_sanity.py" \
    --module "leaf[0].ppp[2].queue" \
    --name "queueBitLength" \
    --source_csv "$RES_DIR/${cfg_name}_vectors.csv" \
    --output "$FIG_DIR/${cfg_name}_queue.png" \
    --y_unit KB \
    --k "$K" --k_unit KB || true
}

for K in "${Ks[@]}"; do
  for L in "${Ls[@]}"; do
    for N in "${Ns[@]}"; do
      for seed in "${Seeds[@]}"; do
        for scen in "${Scenarios[@]}"; do
          run_case "$K" "$L" "$N" "$seed" "$scen"
        done
      done
    done
  done
done

echo "Grid done. CSVs in $RES_DIR; figures in $FIG_DIR" 
