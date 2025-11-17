#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--topology", required=True)
    args = ap.parse_args()

    exp_name = args.experiment
    topology = args.topology  # e.g. "project/topologies/cluster_1node_16c_3ghz.json"

    template_path = PROJECT_ROOT / "experiments" / "template_experiment.json"
    out_path = PROJECT_ROOT / "experiments" / f"{exp_name}.json"

    template = json.loads(template_path.read_text())

    # Set experiment name
    template["name"] = exp_name

    # Set the single topology for this run
    template["topologies"] = [
        {
            "pathToFile": topology
        }
    ]

    # Point workload to the correct folder
    # (our parquet builder writes to project/workloads/<exp_name>/)
    if "workloads" in template and len(template["workloads"]) > 0:
        template["workloads"][0]["pathToFile"] = f"project/workloads/{exp_name}"
    else:
        template["workloads"] = [
            {
                "type": "ComputeWorkload",
                "pathToFile": f"project/workloads/{exp_name}"
            }
        ]

    out_path.write_text(json.dumps(template, indent=2))
    print(f"[OK] Wrote experiment JSON → {out_path}")


if __name__ == "__main__":
    main()
