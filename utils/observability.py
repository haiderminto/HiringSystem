"""
Observability module — placeholder for Arize Phoenix integration.

This module provides a consistent interface for tracing and logging.
Currently logs to Python's logging module. Will be wired to Arize later.

To integrate Arize Phoenix:
1. pip install arize-phoenix opentelemetry-api opentelemetry-sdk
2. Initialize the Phoenix tracer in this module
3. Replace the stub functions with actual span creation
"""

import logging
import time
from typing import Optional

logger = logging.getLogger("ats.observability")


class TraceContext:
    """Represents a single evaluation run trace."""

    def __init__(self, trace_id: str, metadata: Optional[dict] = None):
        self.trace_id = trace_id
        self.metadata = metadata or {}
        self.spans = []
        self.start_time = time.time()
        logger.info(f"[TRACE:{trace_id}] Started evaluation trace")

    def start_span(self, node_name: str, attributes: Optional[dict] = None) -> dict:
        """Start a new span for a node execution."""
        span = {
            "node": node_name,
            "start_time": time.time(),
            "attributes": attributes or {},
            "status": "running",
        }
        self.spans.append(span)
        logger.info(f"[TRACE:{self.trace_id}] Node '{node_name}' started")
        return span

    def end_span(self, span: dict, output: Optional[dict] = None, error: Optional[str] = None):
        """End a span with output or error."""
        span["end_time"] = time.time()
        span["latency_ms"] = int((span["end_time"] - span["start_time"]) * 1000)
        span["status"] = "error" if error else "completed"
        if output:
            span["output"] = output
        if error:
            span["error"] = error
        logger.info(
            f"[TRACE:{self.trace_id}] Node '{span['node']}' "
            f"{'failed' if error else 'completed'} in {span['latency_ms']}ms"
        )

    def end_trace(self, final_output: Optional[dict] = None):
        """End the trace and log summary."""
        total_ms = int((time.time() - self.start_time) * 1000)
        logger.info(
            f"[TRACE:{self.trace_id}] Trace completed in {total_ms}ms, "
            f"{len(self.spans)} spans recorded"
        )
        # Future: send to Arize here

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "spans": self.spans,
            "total_latency_ms": int((time.time() - self.start_time) * 1000),
        }


def create_trace(trace_id: str, metadata: Optional[dict] = None) -> TraceContext:
    """Create a new trace context for an evaluation run."""
    return TraceContext(trace_id, metadata)


# --- Future Arize Integration Point ---
# def init_arize():
#     """Initialize Arize Phoenix tracer."""
#     import phoenix as px
#     from opentelemetry import trace
#     from opentelemetry.sdk.trace import TracerProvider
#     from phoenix.otel import register
#
#     px.launch_app()
#     tracer_provider = register(project_name="ats-resume-evaluator")
#     trace.set_tracer_provider(tracer_provider)
