"""
structure.resolution — Path and Layer Resolution

This module provides layer resolution and path registry.

Public API:
- layer_resolver: Query layer authority and resolve layer paths
- path_registry: Single source of truth for filesystem paths
"""

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver
from compiler.governance_engine.structure.resolution.path_registry import (
    bootstrap,
    paths,
)

__all__ = [
    "LayerResolver",
    "bootstrap",
    "paths",
    # Phase 7: Removed set_workspace_root (dual-root model deleted)
]
