#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEFAULT_TOPOLOGY="project/topologies/cluster_4node_16c_3ghz.json"

for d in "$PROJECT_ROOT/input_traces"/*; do
    [ -d "$d" ] || continue
    EXP_NAME=$(basename "$d")
    echo "=== Running experiment: $EXP_NAME ==="
    "$SCRIPT_DIR/run_from_traces.sh" "$EXP_NAME" "$DEFAULT_TOPOLOGY"
done
