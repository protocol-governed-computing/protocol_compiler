"""
structure — the compiler's structure layer

- Discovery: Artifact discovery and scanning
- Loading: Protocol file loading and parsing
- Resolution: Layer resolution

Quick imports for common use:
- from compiler.governance_engine.structure.resolution import LayerResolver
- from compiler.governance_engine.structure.loading import load_trace, parse_yaml_simple
- from compiler.governance_engine.structure.discovery import extract_codes, scan_artifacts_by_type
"""

# Re-export commonly used items for convenience
from compiler.governance_engine.structure.resolution import LayerResolver
from compiler.governance_engine.structure.loading import (
    ProtocolFSReader,
    ProtocolLoader,
    load_trace,
    TestCase,
    load_test_cases,
    parse_yaml_simple,
    load_vocabulary_md,
)
from compiler.governance_engine.structure.discovery import (
    extract_codes,
    extract_wf_codes,
    extract_in_codes,
    scan_artifacts_by_type,
)

__all__ = [
    # Resolution
    "LayerResolver",
    # Loading (commonly used)
    "ProtocolFSReader",
    "ProtocolLoader",
    "load_trace",
    "TestCase",
    "load_test_cases",
    "parse_yaml_simple",
    "load_vocabulary_md",
    # Discovery (commonly used)
    "extract_codes",
    "extract_wf_codes",
    "extract_in_codes",
    "scan_artifacts_by_type",
]
