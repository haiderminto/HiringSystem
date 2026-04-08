"""
Observability module — Arize integration via OpenTelemetry.

Provides:
  - init_tracing(): Registers the Arize OTEL tracer and auto-instruments
    OpenAI / Anthropic clients so every LLM call is captured automatically.
  - TraceContext: Wraps an OpenTelemetry trace for a single pipeline run,
    with helpers to create spans for each graph node.

If ARIZE_SPACE_ID / ARIZE_API_KEY are not set, tracing is disabled gracefully
and the module falls back to plain Python logging (no crash, no noise).
"""

import logging
import time
from typing import Optional

from config import settings

logger = logging.getLogger("ats.observability")

# Module-level state — populated by init_tracing()
_tracer = None
_tracing_enabled = False


def init_tracing() -> bool:
    """
    Initialize Arize Phoenix tracing via OpenTelemetry.

    Call once at application startup (before any LLM client is created).
    Returns True if tracing was successfully enabled.
    """
    global _tracer, _tracing_enabled

    if not settings.arize_enabled:
        logger.info("Arize tracing DISABLED (no API key configured)")
        return False

    try:
        from arize.otel import register
        from opentelemetry import trace

        # Register the Arize OTEL tracer provider
        tracer_provider = register(
            space_id=settings.arize_space_id,
            api_key=settings.arize_api_key,
            project_name=settings.arize_project_name,
        )
        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer("ats-resume-evaluator")

        # Auto-instrument OpenAI client
        try:
            from openinference.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("OpenAI auto-instrumentation enabled")
        except Exception as e:
            logger.warning(f"OpenAI auto-instrumentation skipped: {e}")

        # Auto-instrument Anthropic client
        try:
            from openinference.instrumentation.anthropic import AnthropicInstrumentor
            AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("Anthropic auto-instrumentation enabled")
        except Exception as e:
            logger.warning(f"Anthropic auto-instrumentation skipped: {e}")

        _tracing_enabled = True
        logger.info(
            f"Arize Phoenix tracing ENABLED — project={settings.arize_project_name}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Arize tracing: {e}")
        _tracing_enabled = False
        return False


def get_tracer():
    """Return the OpenTelemetry tracer (or None if tracing is disabled)."""
    return _tracer


def is_tracing_enabled() -> bool:
    return _tracing_enabled


class TraceContext:
    """
    Represents a single evaluation-run trace.

    When Arize tracing is enabled, creates real OpenTelemetry spans.
    Otherwise, falls back to Python logging.
    """

    def __init__(self, trace_id: str, metadata: Optional[dict] = None):
        self.trace_id = trace_id
        self.metadata = metadata or {}
        self.spans = []
        self.start_time = time.time()
        self._otel_span = None

        # Start a root span for the entire pipeline run
        if _tracing_enabled and _tracer:
            from opentelemetry import trace as otel_trace

            self._otel_span = _tracer.start_span(
                name=f"pipeline:{trace_id}",
                attributes={
                    "ats.trace_id": trace_id,
                    **{f"ats.meta.{k}": str(v) for k, v in self.metadata.items()},
                },
            )
            self._otel_context = otel_trace.set_span_in_context(self._otel_span)
        else:
            self._otel_context = None

        logger.info(f"[TRACE:{trace_id}] Started evaluation trace")

    def start_span(self, node_name: str, attributes: Optional[dict] = None) -> dict:
        """Start a new span for a node execution."""
        span_data = {
            "node": node_name,
            "start_time": time.time(),
            "attributes": attributes or {},
            "status": "running",
            "_otel_span": None,
        }

        if _tracing_enabled and _tracer:
            otel_span = _tracer.start_span(
                name=f"node:{node_name}",
                context=self._otel_context,
                attributes={
                    "ats.node": node_name,
                    "ats.trace_id": self.trace_id,
                    **{f"ats.attr.{k}": str(v) for k, v in (attributes or {}).items()},
                },
            )
            span_data["_otel_span"] = otel_span

        self.spans.append(span_data)
        logger.info(f"[TRACE:{self.trace_id}] Node '{node_name}' started")
        return span_data

    def end_span(self, span: dict, output: Optional[dict] = None, error: Optional[str] = None):
        """End a span with output or error."""
        span["end_time"] = time.time()
        span["latency_ms"] = int((span["end_time"] - span["start_time"]) * 1000)
        span["status"] = "error" if error else "completed"
        if output:
            span["output"] = output
        if error:
            span["error"] = error

        # Close the OpenTelemetry span
        otel_span = span.get("_otel_span")
        if otel_span:
            from opentelemetry.trace import StatusCode

            otel_span.set_attribute("ats.latency_ms", span["latency_ms"])
            otel_span.set_attribute("ats.status", span["status"])
            if error:
                otel_span.set_status(StatusCode.ERROR, error)
                otel_span.set_attribute("ats.error", error)
            else:
                otel_span.set_status(StatusCode.OK)
            otel_span.end()

        logger.info(
            f"[TRACE:{self.trace_id}] Node '{span['node']}' "
            f"{'failed' if error else 'completed'} in {span['latency_ms']}ms"
        )

    def end_trace(self, final_output: Optional[dict] = None):
        """End the trace and log summary."""
        total_ms = int((time.time() - self.start_time) * 1000)

        if self._otel_span:
            from opentelemetry.trace import StatusCode

            self._otel_span.set_attribute("ats.total_latency_ms", total_ms)
            self._otel_span.set_attribute("ats.total_spans", len(self.spans))
            self._otel_span.set_status(StatusCode.OK)
            self._otel_span.end()

        logger.info(
            f"[TRACE:{self.trace_id}] Trace completed in {total_ms}ms, "
            f"{len(self.spans)} spans recorded"
        )

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "spans": [
                {k: v for k, v in s.items() if k != "_otel_span"}
                for s in self.spans
            ],
            "total_latency_ms": int((time.time() - self.start_time) * 1000),
        }


def create_trace(trace_id: str, metadata: Optional[dict] = None) -> TraceContext:
    """Create a new trace context for an evaluation run."""
    return TraceContext(trace_id, metadata)
