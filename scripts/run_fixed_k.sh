#!/usr/bin/env bash
set -euo pipefail
# Batch runner for Fixed-K ECN experiments (k30,k60,k120) and sanity plots.
# Requirements: OMNeT++ env activated; opp_run and opp_scavetool on PATH; INET NED path configured via NEDPATH.
# Usage: ./scripts/run_fixed_k.sh [--incast8] [--only k30,k60,k120]

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SIM_DIR="$ROOT_DIR/sim"
RES_DIR="$ROOT_DIR/results"
FIG_DIR="$ROOT_DIR/figs"

mkdir -p "$RES_DIR" "$FIG_DIR"

# Resolve OMNeT++ executables (allow overrides via env)
OMNETPP_BIN=${OMNETPP_BIN:-$(command -v opp_run || echo "")}
SCAVE_BIN=${SCAVE_BIN:-$(command -v opp_scavetool || echo "")}
if [[ -z "$OMNETPP_BIN" ]]; then
  echo "ERROR: opp_run not found on PATH. Export OMNETPP_BIN=/path/to/omnetpp/bin/opp_run and retry." >&2
  exit 1
fi
if [[ -z "$SCAVE_BIN" ]]; then
  echo "ERROR: opp_scavetool not found on PATH. Export SCAVE_BIN=/path/to/omnetpp/bin/opp_scavetool and retry." >&2
  exit 1
fi

# Optional INET NED path (export INET_NED=/path/to/inet/src to include automatically)
NED_PATH="$SIM_DIR"
if [[ -n "${INET_NED:-}" ]]; then
  NED_PATH="$SIM_DIR:$INET_NED"
fi

# Optional shared libs for opp_run (default to load INET when INET_NED is provided)
OPP_LIBS=${OPP_LIBS:-}
if [[ -z "$OPP_LIBS" && -n "${INET_NED:-}" ]]; then
  # Prefer absolute path to libINET.dylib to avoid DYLD search issues on macOS
  inet_base="${INET_NED%/src}"
  inet_lib_default="$inet_base/out/clang-release/src/libINET.dylib"
  if [[ -n "${INET_LIB:-}" ]]; then
    OPP_LIBS=( -l "${INET_LIB}" )
  elif [[ -f "$inet_lib_default" ]]; then
    OPP_LIBS=( -l "$inet_lib_default" )
  else
    # Fall back to bare name
    OPP_LIBS=( -l INET )
  fi
fi

INCAST_FLAG=false
ONLY_LIST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --incast8)
      INCAST_FLAG=true
      shift
      ;;
    --only)
      if [[ $# -lt 2 ]]; then
        echo "--only requires a comma-separated list argument (e.g., --only k30,k60)"
        exit 1
      fi
      ONLY_LIST="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

configs=(k30 k60 k120)
if [[ -n "$ONLY_LIST" ]]; then
  IFS=',' read -r -a configs <<< "$ONLY_LIST"
fi

# Helper to run one config and export CSVs
run_and_export() {
  local cfg="$1"
  local full_cfg="$cfg"
  if [[ "$INCAST_FLAG" == true ]]; then
    full_cfg="incast8_${cfg}"
  fi

  echo "==> Running $full_cfg"
  (cd "$SIM_DIR" && "$OMNETPP_BIN" -u Cmdenv -n "$NED_PATH" ${OPP_LIBS[@]:-} -f omnetpp.ini -c "$full_cfg")

  local sim_out_dir="$SIM_DIR/results/$full_cfg"
  local vec_out="$RES_DIR/${full_cfg}_vectors.csv"
  local sca_out="$RES_DIR/${full_cfg}_scalars.csv"

  echo "==> Exporting $sim_out_dir -> $vec_out / $sca_out"
  "$SCAVE_BIN" x "$sim_out_dir/omnetpp.vec" -o "$vec_out" || true
  "$SCAVE_BIN" x "$sim_out_dir/omnetpp.sca" -o "$sca_out" || true

  echo "==> Plotting sanity for $full_cfg"
  python3 "$ROOT_DIR/scripts/plot_sanity.py" \
    --module "leaf[0].ppp[2].queue" \
    --name "queueBitLength" \
    --source_csv "$vec_out" \
    --output "$FIG_DIR/${full_cfg}_sanity_queue.png" \
    --y_unit KB \
    --k $(echo "$cfg" | sed 's/[^0-9]//g') \
    --k_unit KB || true
}

for c in "${configs[@]}"; do
  run_and_export "$c"
done

echo "All done. Results in $RES_DIR and figures in $FIG_DIR" 
