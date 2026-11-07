"""Pure-Python attendance engine (no Qt, no database access)."""
from .engine import Summary, compute, summarize

__all__ = ["compute", "summarize", "Summary"]
