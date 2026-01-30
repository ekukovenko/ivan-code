"""LangFuse tracing integration for SDLC Agent.

Provides observability for agent runs with session tracking.
"""

from contextlib import contextmanager
from typing import Any, Generator

from src.core.config import get_settings

# Lazy import to avoid errors when langfuse is not configured
_langfuse_client = None


def get_langfuse():
    """Get or create LangFuse client (singleton)."""
    global _langfuse_client

    settings = get_settings()
    if not settings.langfuse_enabled:
        return None

    if _langfuse_client is None:
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_host,
            )
        except Exception as e:
            print(f"Warning: Failed to initialize LangFuse: {e}")
            return None

    return _langfuse_client


@contextmanager
def trace_agent_run(
    session_id: str,
    agent_name: str,
    metadata: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Context manager for tracing agent runs.

    Args:
        session_id: Unique session identifier (e.g., issue-123)
        agent_name: Name of the agent (code_agent, reviewer_agent)
        metadata: Additional metadata to attach to the trace

    Yields:
        LangFuse span object or None if tracing is disabled
    """
    langfuse = get_langfuse()

    if langfuse is None:
        yield None
        return

    # Use start_span for tracing (new LangFuse API)
    span = langfuse.start_span(
        name=f"{agent_name}_run",
        metadata={
            "session_id": session_id,
            **(metadata or {}),
        },
    )

    try:
        yield span
    finally:
        # End span and flush
        if span:
            span.end()
        langfuse.flush()


def log_agent_generation(
    trace: Any,
    name: str,
    input_text: str,
    output_text: str,
    model: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log a generation (LLM call) to the trace.

    Args:
        trace: LangFuse span object
        name: Name of the generation step
        input_text: Input prompt
        output_text: Model output
        model: Model name used
        metadata: Additional metadata
    """
    if trace is None:
        return

    langfuse = get_langfuse()
    if langfuse is None:
        return

    langfuse.start_generation(
        name=name,
        input=input_text,
        output=output_text,
        model=model,
        metadata=metadata or {},
    )


def log_tool_call(
    trace: Any,
    tool_name: str,
    input_args: dict[str, Any],
    output: Any,
) -> None:
    """Log a tool call to the trace.

    Args:
        trace: LangFuse span object
        tool_name: Name of the tool
        input_args: Tool input arguments
        output: Tool output
    """
    if trace is None:
        return

    langfuse = get_langfuse()
    if langfuse is None:
        return

    span = langfuse.start_span(
        name=f"tool_{tool_name}",
        input=input_args,
        output=str(output) if output else None,
    )
    if span:
        span.end()


def flush_traces() -> None:
    """Flush all pending traces to LangFuse."""
    langfuse = get_langfuse()
    if langfuse:
        langfuse.flush()
