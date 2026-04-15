"""Trace & observability for coach-agents.

Exports :class:`TraceEmitter` and helpers for wiring request-id scoped
logging across router, brain, and CLI eval runners.
"""

from observability.trace import TraceEmitter, TRACE_ROOT, get_emitter

__all__ = ["TraceEmitter", "TRACE_ROOT", "get_emitter"]
