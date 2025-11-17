import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import re

# ============================================================
# Select experiment to analyze
# ============================================================
EXP = "hpl_1node"   # change this to "hpl_4nodes", etc.

BASE = Path("project/output") / EXP / "raw-output" / "0" / "seed=0"
print("Reading from:", BASE)

# ============================================================
# Load parquet files
# ============================================================
df_host = pd.read_parquet(BASE / "host.parquet")
df_task = pd.read_parquet(BASE / "task.parquet")
df_service = pd.read_parquet(BASE / "service.parquet")
df_power = pd.read_parquet(BASE / "powerSource.parquet")

# Load workload definition to get CPU capacity (total FLOPs)
WORKLOAD = Path(f"project/workloads/{EXP}/tasks.parquet")

if WORKLOAD.exists():
    df_workload = pd.read_parquet(WORKLOAD)
else:
    raise FileNotFoundError(f"Workload file not found: {WORKLOAD}")



print("\n--- Loaded Files ---")
print(f"host.parquet columns: {np.array(df_host.columns)}")
print(f"host.parquet rows: {len(df_host)}")
print()
print(f"task.parquet columns: {np.array(df_task.columns)}")
print(f"task.parquet rows: {len(df_task)}")
print()
print(f"service.parquet columns: {np.array(df_service.columns)}")
print(f"service.parquet rows: {len(df_service)}")
print()
print(f"powerSource.parquet columns: {np.array(df_power.columns)}")
print(f"powerSource.parquet rows: {len(df_power)}")

# ============================================================
# Runtime: task-based (robust) + service-based (for debug)
# ============================================================
runtime_ms_tasks = df_task["finish_time"].max() - df_task["submission_time"].min()
runtime_tasks = pd.to_timedelta(runtime_ms_tasks, unit="ms")
print(f"\n[Task-based] Datacenter finished the workload in {runtime_tasks}")

runtime_ms_service = df_service["timestamp"].max() - df_service["timestamp"].min()
runtime_service = pd.to_timedelta(runtime_ms_service, unit="ms")
print(f"[Service-based] runtime from service table: {runtime_service}")

# ============================================================
# GFLOPS computation (simulation-based)
# ============================================================
# Flops achieved with openDC
total_flops = df_workload["cpu_capacity"].sum()
runtime_sec = runtime_ms_tasks / 1000.0

if runtime_sec > 0:
    gflops_sim = total_flops / runtime_sec / 1e9
else:
    print("\n[WARN] Runtime is zero; cannot compute GFLOPS.")

# ============================================================
# Compare with real GFLOPS from HPL output
# ============================================================
hpl_output_path = Path(f"project/input_traces/{EXP}/hpl_output.txt")

if hpl_output_path.exists():
    text = hpl_output_path.read_text()

    # Matches e.g.:
    # WR11C2R4  50000  192  8  8  53.02  1.5719e+03
    regex = r"WR11\w*\s+\d+\s+\d+\s+\d+\s+\d+\s+[0-9.]+\s+([0-9.eE+-]+)"
    m = re.search(regex, text)

    if m:
        gflops_real = float(m.group(1))
        print(f"Real HPL GFLOPS:      {gflops_real:.2f} GFLOPS")
        print(f"Simulated GFLOPS:     {gflops_sim:.2f} GFLOPS")
        diff = gflops_sim - gflops_real
        rel = (diff / gflops_real) * 100
        print(f"Difference:           {diff:+.2f} GFLOPS ({rel:+.2f}%)")
    else:
        print("[WARN] Could not parse GFLOPS from hpl_output.txt — regex did not match.")
else:
    print(f"[INFO] No hpl_output.txt found at {hpl_output_path}.")


# ============================================================
# Host CPU utilization (snapshot average)
# ============================================================
utilization = df_host["cpu_utilization"].mean()
print(f"\nAverage host CPU utilization (snapshot-based): {utilization * 100:.2f}%")

# ============================================================
# Active tasks plot (if we ever get >1 row)
# ============================================================
if len(df_service) > 1:
    plt.figure()
    plt.plot(df_service["timestamp"] / 1000 / 60 / 60, df_service["tasks_active"])
    plt.title(f"Active tasks during workload ({EXP})")
    plt.xlabel("time (h)")
    plt.ylabel("active tasks")
    plt.grid(True)
    plt.show()
else:
    print("\n[INFO] service.parquet has only one sample; skipping active tasks time-series plot.")

# ============================================================
# Rolling host plot helper
# ============================================================
def plotHost(df_host, column, aggregation_method="mean", window_size=1000):
    if aggregation_method not in ["mean", "sum"]:
        raise ValueError(f"Incorrect aggregation method: {aggregation_method}, pick one of [mean, sum]")

    df_agg = df_host.groupby("timestamp")[[column]].agg(aggregation_method)

    plt.figure()
    plt.plot(df_agg.index / 1000 / 60 / 60, df_agg.rolling(window_size, min_periods=1).mean())
    plt.title(f"{column} ({aggregation_method}) – rolling")
    plt.xlabel("timestamp (h)")
    plt.ylabel(column)
    plt.grid(True)
    plt.show()

# This will be boring with just 1 row, but will look good once sampling is richer:
plotHost(df_host, "cpu_utilization", "mean", window_size=1)

# ============================================================
# Power draw plot
# ============================================================
plt.figure()
plt.plot(df_power["timestamp"] / 1000 / 60 / 60, df_power["power_draw"])
plt.title(f"Power draw over time ({EXP})")
plt.xlabel("time (h)")
plt.ylabel("power_draw")
plt.grid(True)
plt.show()



