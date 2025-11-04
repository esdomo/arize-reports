import numpy as np

# Convert start and end times to datetime
df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")

# Compute latency
df["latency_seconds"] = (df["end_time"] - df["start_time"]).dt.total_seconds()

# --- 1. Thread-level summary ---
thread_summary = (
    df.groupby("context.trace_id")
    .agg(
        human_input=("input.value", "first"),
        final_ai_response=("output.value", "last"),
        latency_seconds=("latency_seconds", "sum"),
        token_prompt=("llm.token_count.prompt", "sum"),
        token_cached=("llm.token_count.prompt_details.cache_read", "sum"),
        token_completion=("llm.token_count.completion", "sum"),
        token_total=("llm.token_count.total", "sum"),
    )
    .reset_index()
)

# --- 2. LLM-call breakdown ---
llm_calls = df[~df["llm.model_name"].isna()].copy()
llm_calls = llm_calls[[
    "context.trace_id",
    "context.span_id",
    "llm.model_name",
    "llm.token_count.prompt",
    "llm.token_count.prompt_details.cache_read",
    "llm.token_count.completion",
    "llm.token_count.total",
    "latency_seconds",
]]

# --- 3. Session-level summary ---
session_summary = (
    df.groupby("session.id")
    .agg(
        total_prompt_tokens=("llm.token_count.prompt", "sum"),
        total_cached_tokens=("llm.token_count.prompt_details.cache_read", "sum"),
        total_completion_tokens=("llm.token_count.completion", "sum"),
        total_tokens=("llm.token_count.total", "sum"),
        total_latency_seconds=("latency_seconds", "sum"),
    )
    .reset_index()
)

# --- Cost estimation ---
# Approximate cost rates (USD per 1k tokens)
model_rates = {
    "gpt-4o": {"prompt": 0.0025 / 1000, "completion": 0.01 / 1000},
    "gpt-4o-mini": {"prompt": 0.00015 / 1000, "completion": 0.0006 / 1000},
}

def estimate_cost(row):
    model = row.get("llm.model_name", "")
    if pd.isna(model):
        return np.nan
    if "mini" in model:
        rate = model_rates["gpt-4o-mini"]
    else:
        rate = model_rates["gpt-4o"]
    return (
        (row.get("llm.token_count.prompt", 0) or 0) * rate["prompt"]
        + (row.get("llm.token_count.completion", 0) or 0) * rate["completion"]
    )

llm_calls["estimated_cost_usd"] = llm_calls.apply(estimate_cost, axis=1)

# Aggregate cost per session
total_cost_usd = llm_calls["estimated_cost_usd"].sum()

import caas_jupyter_tools
caas_jupyter_tools.display_dataframe_to_user("Thread-level Summary", thread_summary)
caas_jupyter_tools.display_dataframe_to_user("LLM-call Breakdown", llm_calls)
caas_jupyter_tools.display_dataframe_to_user("Session-level Summary", session_summary)

total_cost_usd



# Include LLM input and output messages for each call
llm_calls_detailed = llm_calls.merge(
    df[["context.span_id", "llm.input_messages", "llm.output_messages"]],
    on="context.span_id",
    how="left"
)

# Reorder for clarity
llm_calls_detailed = llm_calls_detailed[[
    "context.trace_id",
    "context.span_id",
    "llm.model_name",
    "llm.input_messages",
    "llm.output_messages",
    "llm.token_count.prompt",
    "llm.token_count.prompt_details.cache_read",
    "llm.token_count.completion",
    "llm.token_count.total",
    "latency_seconds",
    "estimated_cost_usd",
]]

import caas_jupyter_tools
caas_jupyter_tools.display_dataframe_to_user("LLM-call Breakdown (with Input/Output Messages)", llm_calls_detailed)
