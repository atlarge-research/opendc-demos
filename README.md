# README

Trace-Based Execution of HPL Benchmarks in OpenDC

## Overview

This project provides a complete pipeline for converting real High-Performance Linpack (HPL) benchmark runs into trace-based workloads for the OpenDC simulator. The final goal is to reproduce HPL experiments using simulation, analyze and compare simulated performance with real performance, and study causes of divergence.

The pipeline includes:

1. Real HPL run logs (from DAS-5 or another HPC cluster).
2. A workload generator that converts run logs into OpenDC-compatible Parquet workload traces.
3. Experiment configuration files referencing the generated traces.
4. Scripts to execute the experiments using the OpenDC Experiment Runner.
5. Analysis scripts to compute simulated GFLOPS, runtime, utilization, and compare with real HPL numbers.

The project supports single- and multi-node MPI runs.

---

## Directory Structure

```
project/
├── input_traces/
│   └── hpl_1node/
│       ├── run_info.txt
│       ├── hpl_output.txt
│       └── config.json             # optional per-experiment overrides
│
├── topologies/
│   ├── cluster_1node_16c_3ghz.json
│   ├── cluster_2nodes_16c_3ghz.json
│   ├── cluster_4nodes_16c_3ghz.json
│   └── cluster_8nodes_16c_3ghz.json
│
├── workloads/
│   └── hpl_1node/
│       ├── tasks.parquet
│       └── fragments.parquet
│
├── experiments/
│   └── hpl_1node.json
│
├── output/
│   └── hpl_1node/
│       └── raw-output/0/seed=0/
│           ├── host.parquet
│           ├── task.parquet
│           ├── service.parquet
│           └── powerSource.parquet
│
└── scripts/
    ├── build_parquet_from_traces.py
    ├── make_experiment_json.py
    ├── run_from_traces.sh
    └── analyze_experiment.py
```

---

## Pipeline Summary

### Step 1: Prepare real HPL logs

Each experiment folder under `project/input_traces/<exp_name>/` must contain:

* `run_info.txt`
* `hpl_output.txt`
* Optional: `config.json` for overrides

  ```
  {
    "cpu_count": 4,
    "mem_capacity": 2147483648,
    "submission_time": 100000,
    "multi_fragment": false
  }
  ```

### Step 2: Convert HPL logs to OpenDC workload traces

Run:

```
python project/scripts/build_parquet_from_traces.py \
    --experiment hpl_1node \
    --source-dir project/input_traces/hpl_1node
```

This produces:

```
project/workloads/hpl_1node/tasks.parquet
project/workloads/hpl_1node/fragments.parquet
```

The generator uses:

* Parsed runtime from HPL output
* Parsed MPI ranks
* Algorithmic HPL FLOPs (if using Solution A)
* Fragmentation (single or multi-fragment)
* Capacity and memory overrides from `config.json`

### Step 3: Create an OpenDC experiment JSON

Run:

```
python project/scripts/make_experiment_json.py hpl_1node
```

This produces:

```
project/experiments/hpl_1node.json
```

### Step 4: Run the experiment in OpenDC

From the project root:

```
bash project/scripts/run_from_traces.sh \
    hpl_1node \
    project/topologies/cluster_1node_16c_3ghz.json
```

This runs:

```
./OpenDCExperimentRunner --experiment-path project/experiments/hpl_1node.json
```

OpenDC writes results to:

```
project/output/hpl_1node/raw-output/0/seed=0/
```

### Step 5: Analyze the results

Run:

```
python project/scripts/analyze_experiment.py
```

Outputs include:

* Simulated GFLOPS
* Real GFLOPS
* Absolute and percentage difference
* Runtime (task-based and service-based)
* Average CPU utilization
* Time-series plots (host utilization, power draw, active tasks)

---

## Interpretation and Comparison

The key research question:

**Does the trace-based OpenDC execution achieve similar GFLOPS to the real HPL run?**

Depending on how the workload traces are generated, outcomes differ:

### Case 1: FLOP-based replay (uses real GFLOPS)

If the trace generator uses:

```
total_flops = real_GFLOPS × time
```

then:

* Simulated GFLOPS == Real GFLOPS (by construction)
* No divergence, because the workload exactly replays the real performance.

### Case 2: Algorithmic-FLOP model (Solution A)

Using:

```
total_flops = (2/3) * N^3
```

and ignoring measured GFLOPS, OpenDC produces GFLOPS based on:

* Topology capacity
* Scheduling
* Resource contention
* Fragmentation
* CPU throttling
* Model imperfections

This yields divergence and makes comparison meaningful.

### Possible causes of divergence

* The simulator does not model MPI communication
* No representation of HPL panel factorization or blocking (NB)
* No interconnect bandwidth modeling
* No NUMA, noise, or system overhead
* Simplified CPU and memory model
* Missing network contention and communication latency
* Inaccurate per-core peak performance assumptions
* Fragmentation oversimplifies dynamic CPU usage

These differences must be discussed in your report.

---

## Troubleshooting

### Permission denied when running scripts

```
chmod +x project/scripts/*.sh
```

### Experiment shows zero runtime

Service table may contain only one sample; use task-based runtime.

### Cannot spawn task / does not fit

Increase `mem_capacity` or reduce `cpu_count` in `config.json`.

### Parquet schema mismatch

Ensure:

* `id` is int32
* `duration` and `submission_time` are int64
* `cpu_usage` and `cpu_capacity` are float64

---

## Extending the Project

* Model MPI communication using synthetic idle fragments
* Add network topology constraints
* Add random cluster noise
* Simulate throttling or oversubscription
* Automate multi-node sweeps (1, 2, 4, 8 nodes)

