"""
structure.discovery — Artifact Discovery

This module provides artifact discovery and code extraction utilities.

Public API:
- artifact_locator: Discover and scan protocol artifacts
"""

from compiler.governance_engine.structure.discovery.artifact_locator import (
    iter_protocol_jsons,
    load_json_strict,
    extract_codes,
    extract_wf_codes,
    extract_in_codes,
    extract_cc_codes,
    scan_artifacts_by_type,
)

__all__ = [
    "iter_protocol_jsons",
    "load_json_strict",
    "extract_codes",
    "extract_wf_codes",
    "extract_in_codes",
    "extract_cc_codes",
    "scan_artifacts_by_type",
]
