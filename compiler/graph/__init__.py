"""
Compiler graph — core data model.

The canonical, immutable, topology-native semantic graph
representing the entire governed system. Graph is the sole
semantic authority from which all projections are derived.
"""

from compiler.graph.types import NodeKind, EdgeKind
from compiler.graph.node import Node
from compiler.graph.edge import Edge
from compiler.graph.graph import Graph
from compiler.graph.trace import TraceEvent
from compiler.graph.state import State
from compiler.graph.evidence import (
    EventFamily,
    EventKind,
    EVENT_KIND_TO_FAMILY,
    EvidenceEdge,
    EvidenceEdgeKind,
    EvidenceGraph,
)

__all__ = [
    "NodeKind",
    "EdgeKind",
    "Node",
    "Edge",
    "Graph",
    "TraceEvent",
    "State",
    "EventFamily",
    "EventKind",
    "EVENT_KIND_TO_FAMILY",
    "EvidenceEdge",
    "EvidenceEdgeKind",
    "EvidenceGraph",
]
