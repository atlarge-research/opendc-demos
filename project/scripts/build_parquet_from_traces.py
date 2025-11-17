#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_run_info(path: Path):
    """Parse nodes and MPI procs from run_info.txt."""
    nodes = None
    procs = None
    for line in path.read_text().splitlines():
        if line.startswith("Nodes:"):
            nodes = int(line.split(":", 1)[1])
        if line.startswith("Total MPI processes:"):
            procs = int(line.split(":", 1)[1])
    if nodes is None or procs is None:
        raise RuntimeError(f"Could not parse nodes / procs from {path}")
    return nodes, procs


def parse_hpl_output(path: Path):
    pat = re.compile(
        r"WR11\w+\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+([0-9.eE+-]+)"
    )
    for line in path.read_text().splitlines():
        m = pat.search(line)
        if m:
            N = int(m.group(1))
            time_sec = float(m.group(5))
            gflops = float(m.group(6))
            return N, time_sec, gflops
    raise RuntimeError("Could not find WR11* result line in HPL output")


def load_config(src_dir: Path, cli_cpu_count: int | None) -> dict:
    """
    Merge defaults, config.json, and CLI overrides into a single config dict.
    Supported keys in config.json:

      {
        "cpu_count": 4,
        "mem_capacity": 100000,
        "submission_time": 100000,
        "multi_fragment": false
      }
    """
    cfg = {
        "cpu_count": 1,
        # This should match the kind of scale your topology expects.
        "mem_capacity": 100_000,  # SURF-ish default; adjust if needed
        "submission_time": 0,     # default submission time (ms)
        "multi_fragment": False,
    }

    config_path = src_dir / "config.json"
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text())
            if "cpu_count" in raw:
                cfg["cpu_count"] = int(raw["cpu_count"])
            if "mem_capacity" in raw:
                cfg["mem_capacity"] = int(raw["mem_capacity"])
            if "submission_time" in raw:
                cfg["submission_time"] = int(raw["submission_time"])
            if "multi_fragment" in raw:
                cfg["multi_fragment"] = bool(raw["multi_fragment"])
        except Exception as e:
            print(f"[WARN] Failed reading {config_path}: {e}. Using defaults/CLI.")

    # CLI value wins over config.json for cpu_count
    if cli_cpu_count is not None:
        cfg["cpu_count"] = cli_cpu_count

    return cfg


def build_fragments_for_task(
    task_id: int,
    total_duration_ms: float,
    cpu_capacity_flops: float,
    multi_fragment: bool,
):
    """
    Create fragment rows for a single task.

    Units:
      - total_duration_ms is in milliseconds
      - cpu_capacity_flops is total FLOPs for this task
      - cpu_usage will be FLOPs per millisecond

    If not multi_fragment:
      - one fragment covering full duration
    If multi_fragment:
      - split into ~10 equal fragments, same cpu_usage
    """
    if total_duration_ms <= 0:
        return [
            {
                "id": task_id,
                "duration": 0.0,
                "cpu_usage": 0.0,
            }
        ]

    # FLOPs per ms
    cpu_usage = cpu_capacity_flops / total_duration_ms

    if not multi_fragment:
        return [
            {
                "id": task_id,
                "duration": float(total_duration_ms),
                "cpu_usage": float(cpu_usage),
            }
        ]

    # Multi-fragment: split into up to 10 equal fragments
    target_frags = 10
    if total_duration_ms < target_frags:
        # Too short to split nicely, just return one
        return [
            {
                "id": task_id,
                "duration": float(total_duration_ms),
                "cpu_usage": float(cpu_usage),
            }
        ]

    frag_duration = total_duration_ms / target_frags
    fragments = []
    remaining = total_duration_ms

    while remaining > 0:
        d = frag_duration if remaining > frag_duration else remaining
        fragments.append(
            {
                "id": task_id,
                "duration": float(d),
                "cpu_usage": float(cpu_usage),
            }
        )
        remaining -= d

    return fragments


def build_parquet(exp_name: str, src_dir: Path, cli_cpu_count: int | None):
    # --- Load input trace files ---
    run_info = src_dir / "run_info.txt"
    hpl_out = src_dir / "hpl_output.txt"

    if not run_info.exists() or not hpl_out.exists():
        raise FileNotFoundError(
            f"{src_dir} must contain run_info.txt and hpl_output.txt"
        )

    nodes, procs = parse_run_info(run_info)

    N, time_sec, gflops = parse_hpl_output(hpl_out)
    time_ms = int(round(time_sec * 1000))
    cfg = load_config(src_dir, cli_cpu_count)

    cpu_count = cfg["cpu_count"]
    mem_capacity = cfg["mem_capacity"]
    submission_time = cfg["submission_time"]
    multi_fragment = cfg["multi_fragment"]

    print(f"[INFO] Experiment = {exp_name}")
    print(f"[INFO] Nodes = {nodes}, MPI ranks = {procs}")
    print(f"[INFO] HPL runtime = {time_sec:.3f} s ({time_ms} ms), GFLOPS = {gflops}")
    print(
        f"[INFO] cfg: cpu_count={cpu_count}, "
        f"mem_capacity={mem_capacity}, submission_time={submission_time}, "
        f"multi_fragment={multi_fragment}"
    )

    
    # --- Compute total FLOPs and per-rank work ---
    flops_alg = (2.0 / 3.0) * (N ** 3)
    # total_flops = GFLOPS * 1e9 FLOPs/s * time_sec
    
    flops_per_rank = flops_alg / procs
    cpu_capacity = flops_per_rank  # interpret as "total work (FLOPs) per rank"
    
    # --- Output paths ---
    out_dir = PROJECT_ROOT / "workloads" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.parquet"
    frags_path = out_dir / "fragments.parquet"

    tasks_rows = []
    frags_rows = []

    # One task per MPI rank
    for rank in range(procs):
        task_id = rank

        tasks_rows.append(
            {
                "id": int(task_id),
                "submission_time": int(submission_time),  # ms
                "duration": float(time_ms),               # ms
                "cpu_count": int(cpu_count),
                "cpu_capacity": float(cpu_capacity),      # FLOPs for this rank
                "mem_capacity": int(mem_capacity),
            }
        )

        frags_rows.extend(
            build_fragments_for_task(
                task_id=task_id,
                total_duration_ms=time_ms,
                cpu_capacity_flops=cpu_capacity,
                multi_fragment=multi_fragment,
            )
        )

    df_tasks = pd.DataFrame(tasks_rows)
    df_frags = pd.DataFrame(frags_rows)

    # Enforce column order
    df_tasks = df_tasks[
        ["id", "submission_time", "duration", "cpu_count", "cpu_capacity", "mem_capacity"]
    ]
    df_frags = df_frags[["id", "duration", "cpu_usage"]]

    # ---------------- TASKS: explicit schema ----------------
    df_tasks = df_tasks.fillna(0)

    df_tasks["id"] = df_tasks["id"].astype("int32")
    df_tasks["submission_time"] = df_tasks["submission_time"].astype("int64")
    df_tasks["duration"] = df_tasks["duration"].round().astype("int64")
    df_tasks["cpu_count"] = df_tasks["cpu_count"].astype("int32")
    df_tasks["cpu_capacity"] = df_tasks["cpu_capacity"].astype("float64")
    df_tasks["mem_capacity"] = df_tasks["mem_capacity"].astype("int64")

    tasks_schema = pa.schema([
        pa.field("id", pa.int32(), nullable=False),
        pa.field("submission_time", pa.int64(), nullable=False),
        pa.field("duration", pa.int64(), nullable=False),
        pa.field("cpu_count", pa.int32(), nullable=False),
        pa.field("cpu_capacity", pa.float64(), nullable=False),
        pa.field("mem_capacity", pa.int64(), nullable=False),
    ])

    tasks_table = pa.Table.from_pandas(df_tasks, schema=tasks_schema, preserve_index=False)
    pq.write_table(tasks_table, tasks_path)

    # ---------------- FRAGMENTS: explicit schema ----------------
    df_frags = df_frags.fillna(0)
    df_frags["id"] = df_frags["id"].astype("int32")
    df_frags["duration"] = df_frags["duration"].astype("int64")
    df_frags["cpu_usage"] = df_frags["cpu_usage"].astype("float64")

    frag_schema = pa.schema([
        pa.field("id", pa.int32(), nullable=False),
        pa.field("duration", pa.int64(), nullable=False),
        pa.field("cpu_usage", pa.float64(), nullable=False),
    ])

    frags_table = pa.Table.from_pandas(df_frags, schema=frag_schema, preserve_index=False)
    pq.write_table(frags_table, frags_path)

    print(f"[OK] Wrote tasks → {tasks_path}")
    print(f"[OK] Wrote fragments → {frags_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--source-dir")
    ap.add_argument(
        "--cpu-count",
        type=int,
        default=None,
        help="override cpu_count (else config.json or default=1)",
    )
    args = ap.parse_args()

    exp_name = args.experiment
    src_dir = (
        Path(args.source_dir)
        if args.source_dir
        else PROJECT_ROOT / "input_traces" / exp_name
    )

    build_parquet(exp_name, src_dir, args.cpu_count)


if __name__ == "__main__":
    main()
