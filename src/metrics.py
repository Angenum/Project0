"""Prometheus метрики для observability."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

PIPELINE_RUNS = Counter("pipeline_runs_total", "Total pipeline runs", ["status"])
STEP_DURATION = Histogram("step_duration_seconds", "Time per step", ["step_name"])
STEP_TOKENS = Counter("step_tokens_total", "Tokens per step", ["step_name", "model"])
STEP_COST = Counter("step_cost_usd_total", "Cost per step in USD", ["step_name", "model"])
