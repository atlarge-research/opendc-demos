# %%

import pandas as pd
import numpy as np

# %%

df_task_no = pd.read_parquet("output/7.checkpointing/raw-output/0/seed=0/task.parquet")
df_task_5min = pd.read_parquet("output/7.checkpointing/raw-output/1/seed=0/task.parquet")

df_task_inp = pd.read_parquet("workload_traces/surf_week/tasks.parquet")
df_fragments_inp = pd.read_parquet("workload_traces/surf_week/fragments.parquet")
df_task_inp["task_id"] = df_task_inp["id"]
df_task_inp["finish_time"] = df_task_inp["submission_time"] + df_task_inp["duration"]
df_task_inp["finish_time_relative"] = df_task_inp["finish_time"] - 1656604920000
df_task_inp["submission_time_relative"] = df_task_inp["submission_time"] - 1656604920000

df_task_no_meta = pd.read_parquet("output/7.checkpointing/raw-output/0/seed=0/meta/task.parquet")

# %%



# %%

def removeTerminatedTasks(df_task):
    # Remove tasks that are not terminated
    terminated_ids = df_task[df_task["task_state"] == "TERMINATED"].task_id.unique()
    df_task = df_task[~df_task["task_id"].isin(terminated_ids)]

    return df_task

df_task_no_filtered = removeTerminatedTasks(df_task_no)
df_task_5min_filtered = removeTerminatedTasks(df_task_5min)


# %%

df_task_no["total_delay"] = df_task_no["scheduling_delay"] + df_task_no["failure_delay"] + df_task_no["checkpoint_delay"]

df_merged_no = pd.merge(df_task_no, df_task_inp, on="task_id", suffixes=("_opendc", "_data"))
df_grouped_no = df_merged_no.groupby("task_id")[["finish_time_opendc", "finish_time_relative", "total_delay"]].agg("max")
df_grouped_no["delay"] = df_grouped_no["finish_time_opendc"] - df_grouped_no["finish_time_relative"]

avg_delay_no = df_grouped_no['delay'].mean()
print(f"Average delay (no checkpointing): {avg_delay_no}")
df_grouped_no[df_grouped_no["delay"] != df_grouped_no["total_delay"]]

# %%

df_task_5min["total_delay"] = df_task_5min["scheduling_delay"] + df_task_5min["failure_delay"] + df_task_5min["checkpoint_delay"]

df_merged_5min = pd.merge(df_task_5min, df_task_inp, on="task_id", suffixes=("_opendc", "_data"))
df_grouped_5min = df_merged_5min.groupby("task_id")[["finish_time_opendc", "finish_time_relative", "total_delay"]].agg("max")
df_grouped_5min["delay"] = df_grouped_5min["finish_time_opendc"] - df_grouped_5min["finish_time_relative"]

avg_delay_5min = df_grouped_5min['delay'].mean()
print(f"Average delay (5-minute checkpointing): {avg_delay_5min}")
df_grouped_5min[df_grouped_5min["delay"] != df_grouped_5min["total_delay"]]


df_grouped_5min["delay_diff"] = df_grouped_5min["total_delay"] - df_grouped_5min["delay"]

# %%

df_grouped_5min[df_grouped_5min["delay_diff"] == 0]


# %%

df_grouped_5min.loc[1605692]

# %%
df_grouped_5min

# %%

df_task_5min[df_task_5min["task_id"] == 1553224][["timestamp", "task_state", "failure_delay", "checkpoint_delay", "total_delay"]]

# %%

df_task_inp[df_task_inp["task_id"] == 1553224]

# %%

df_fragments_inp[df_fragments_inp["id"] == 1605692]
