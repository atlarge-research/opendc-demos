#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <experiment_name> <topology_json> [cpu_count]"
  exit 1
fi

EXP_NAME="$1"
TOPOLOGY="$2"
CPU_COUNT="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNNER="$PROJECT_ROOT/../OpenDCExperimentRunner/bin/OpenDCExperimentRunner"

echo "[STEP 1] Build Parquet workload"
if [ -n "$CPU_COUNT" ]; then
  python3 "$SCRIPT_DIR/build_parquet_from_traces.py" \
    --experiment "$EXP_NAME" \
    --cpu-count "$CPU_COUNT"
else
  python3 "$SCRIPT_DIR/build_parquet_from_traces.py" \
    --experiment "$EXP_NAME"
fi

echo "[STEP 2] Generate experiment JSON"
python3 "$SCRIPT_DIR/make_experiment_json.py" \
  --experiment "$EXP_NAME" \
  --topology "$TOPOLOGY"

EXP_JSON="$PROJECT_ROOT/experiments/${EXP_NAME}.json"

echo "[STEP 3] Run Experiment → $EXP_JSON"
"$RUNNER" --experiment-path "$EXP_JSON"
