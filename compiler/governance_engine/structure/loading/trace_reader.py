"""
trace_reader.py — JSONL trace file loading (structure runtime)

This module provides runtime trace file loading.
Governance layer uses this for conformance testing and validation.

ARCHITECTURAL BOUNDARY:
- Structure: Implements trace file loading (this file)
- Governance: Defines trace validation rules and conformance logic

Moved from registry/conformance/utils/trace_loader.py to establish clean separation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any


class TraceLoadError(RuntimeError):
    """Raised when trace file loading fails."""
    pass


def load_trace(path: Path) -> List[Dict[str, Any]]:
    """
    Load a JSONL execution trace.

    Reads a file containing one JSON object per line (JSONL format).
    Used for execution traces, conformance test data, etc.

    Contract:
    - One JSON object per line
    - Order preserved exactly
    - No interpretation or validation (pure loading)
    - Fail loud on malformed input

    Args:
        path: Path to JSONL trace file.

    Returns:
        List of trace events (dicts) in order.

    Raises:
        TraceLoadError: If file not found, malformed JSON, or empty.
    """

    if not isinstance(path, Path):
        raise TraceLoadError("trace path must be a pathlib.Path")

    if not path.exists():
        raise TraceLoadError(f"trace file not found: {path}")

    events: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except Exception as e:
                raise TraceLoadError(
                    f"invalid JSON at {path}:{line_no}\n{e}"
                ) from e

            if not isinstance(obj, dict):
                raise TraceLoadError(
                    f"trace event must be JSON object at {path}:{line_no}"
                )

            events.append(obj)

    if not events:
        raise TraceLoadError(f"trace file is empty: {path}")

    return events


def load_trace_safe(path: Path) -> List[Dict[str, Any]] | None:
    """
    Load trace file, returning None on failure instead of raising.

    Useful for optional trace loading where missing traces are acceptable.

    Args:
        path: Path to JSONL trace file.

    Returns:
        List of trace events, or None if loading failed.
    """
    try:
        return load_trace(path)
    except TraceLoadError:
        return None
