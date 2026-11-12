"""
Handlers projection — runtime implementation dispatch table for token-native runtime.

Derives from the PIRGraph after S5 CONSTRUCT. Produces three integer-keyed
tables that together constitute the implementation binding substrate:

    ct        — CT_addr → {ct_ir}
    cs        — CS_addr → {handler_ref, cs_metadata}
    rb_policy — RB_addr → {CS_addr: policy_config}

Workspace target: tokenized_snapshot/<structure_id>/handlers.json

Design constraints:
    - All keys are integer addresses (JSON strings for dict keys per JSON spec)
    - handler_ref contains {module, callable} — resolved to Python callable at runtime
    - rb_policy values carry {{module_data_root}} templates — runtime expands, compiler emits as-is
    - Deterministic: same graph → same handlers.json
    - Zero semantic inference at runtime — compiler owns all binding decisions

Foundational rule:
    The runtime MUST NOT reconstruct handler bindings the compiler already knew.
    CT/CS implementations and RB policies are compile-time decisions.
    The runtime reads this table and dispatches — nothing more.
"""

from types import MappingProxyType
from typing import Any

from compiler.graph.graph import Graph
from compiler.graph.types import NodeKind
from compiler.graph.hashing import compute_projection_hash
from compiler.graph.trace import TraceEvent
from compiler.graph.evidence import EventFamily
from compiler.projections import (
    COMPILER_VERSION,
    PROJECTION_SCHEMA_VERSION,
    Projection,
    ProjectionType,
    make_metadata,
)


def project_handlers(graph: Graph) -> tuple[Projection, list[TraceEvent]]:
    """
    Generate handler dispatch projection from Graph.

    Reads CT and CS nodes with populated ir (set by S5 CONSTRUCT) and
    RB nodes with frontmatter.core.bindings for policy resolution.

    Content shape:
        {
            "ct": {
                "<CT_addr>": {"ct_ir": {...}}
            },
            "cs": {
                "<CS_addr>": {"handler_ref": {...}, "cs_metadata": {...}}
            },
            "rb_policy": {
                "<RB_addr>": {"<CS_addr>": {"policy": {...}}}
            },
        }

    All dict keys are strings (JSON requirement). All address values are integers.

    Args:
        graph: Fully constructed and addressed PIRGraph (post-S5)

    Returns:
        Tuple of (Projection with handlers content, trace events)
    """
    trace: list[TraceEvent] = []

    ct: dict[str, dict[str, Any]] = {}
    cs: dict[str, dict[str, Any]] = {}
    rb_policy: dict[str, dict[str, Any]] = {}

    for fqdn, node in graph.nodes.items():
        if node.address < 0:
            continue

        if node.kind == NodeKind.CT and node.ir is not None:
            ct[str(node.address)] = {
                "ct_ir": _to_plain(node.ir),
            }

        elif node.kind == NodeKind.CS and node.ir is not None:
            cs[str(node.address)] = _to_plain(node.ir)

        elif node.kind == NodeKind.RB:
            core = node.frontmatter.get("core", {})
            bindings = core.get("bindings", {})
            if not isinstance(bindings, dict) or not bindings:
                continue

            # Look up storage_structure artifact if declared
            # Wrap as {"frontmatter": ...} to match how the executor reads it:
            #   storage_structure_artifact.get("frontmatter", {}).get("core", {})
            storage_structure_artifact = None
            storage_structure_fqdn = core.get("storage_structure", "")
            if storage_structure_fqdn:
                struct_node = graph.nodes.get(storage_structure_fqdn)
                if struct_node is not None:
                    storage_structure_artifact = {"frontmatter": _to_plain(struct_node.frontmatter)}

            rb_bindings: dict[str, Any] = {}
            for cs_fqdn, policy_config in bindings.items():
                cs_node = graph.nodes.get(cs_fqdn)
                if cs_node is None or cs_node.address < 0:
                    continue
                plain_policy = _to_plain(policy_config)
                # Inject storage topology when RB declares a storage_structure
                if storage_structure_artifact is not None:
                    policy = plain_policy.get("policy", {})
                    policy["storage_structure_artifact"] = storage_structure_artifact
                    policy["module_data_root"] = "{{module_data_root}}"
                    plain_policy = {"policy": policy}
                rb_bindings[str(cs_node.address)] = plain_policy

            if rb_bindings:
                rb_policy[str(node.address)] = rb_bindings

    # --- Per-act composed storage, with the reach of every entity marked ---
    #
    # An act resolves its records against the bindings it operates under: the one it owns, and any
    # it declares it consults. Composed here and sealed, rather than resolved when the act runs —
    # the runtime reads what it is handed and never resolves for itself, and that property is worth
    # more than the few lines it saves.
    #
    # Keyed by act rather than by binding, because a binding is shared: two acts may own the same
    # one and consult different others, and composing into the binding would hand each act the
    # other's reach.
    #
    # Every entity carries `reach`. `owned` is written and read; `consulted` is read only, and the
    # runtime refuses a write against it. The distinction cannot be inferred later: once two
    # descriptions are merged, an entity's origin is gone unless it is recorded here.
    wf_storage: dict[str, dict[str, Any]] = {}

    for node in graph.nodes.values():
        if node.kind != NodeKind.WF or node.address < 0:
            continue

        owned_fqdn = node.frontmatter.get("runtime_binding")
        consulted = list(node.frontmatter.get("consults") or [])
        if not owned_fqdn or not consulted:
            # An act that consults nothing needs no composition: its owned binding already carries
            # the one description it resolves against, and the policy injection below hands it over
            # unchanged. Composing anyway would seal a second copy of one description.
            continue

        composed: dict[str, Any] = {}
        for binding_fqdn, reach in [(owned_fqdn, "owned")] + [(c, "consulted") for c in consulted]:
            rb_node = graph.nodes.get(binding_fqdn)
            if rb_node is None:
                continue
            struct_fqdn = rb_node.frontmatter.get("core", {}).get("storage_structure", "")
            struct_node = graph.nodes.get(struct_fqdn) if struct_fqdn else None
            if struct_node is None:
                continue
            entities = _to_plain(struct_node.frontmatter).get("core", {}).get("entity_stores", {})
            for entity, config in (entities or {}).items():
                if entity in composed:
                    # One record described twice, reached by one act. Which description answers
                    # would depend on the order the bindings were named, and the model says a
                    # record is described once. Left out of the composition and reported by the
                    # rule that owns the question rather than silently preferred here.
                    continue
                composed[entity] = {**config, "reach": reach, "described_by": binding_fqdn}

        if composed:
            wf_storage[str(node.address)] = {
                "frontmatter": {"core": {"entity_stores": composed}}
            }

    content = {
        "ct":       ct,
        "cs":       cs,
        "rb_policy": rb_policy,
        "wf_storage": wf_storage,
    }

    projection_hash = compute_projection_hash(content)

    metadata = make_metadata(
        projection_type=ProjectionType.HANDLERS,
        graph_topology_hash=graph.topology_hash,
        graph_address_hash=graph.address_hash,
        projection_hash=projection_hash,
        compiler_version=COMPILER_VERSION,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
    )

    projection = Projection(
        projection_type=ProjectionType.HANDLERS,
        metadata=metadata,
        content=MappingProxyType(content),
    )

    trace.append(TraceEvent.create(
        stage="S6_PROJECT",
        operation="handlers_projected",
        detail={
            "ct_count":       len(ct),
            "cs_count":       len(cs),
            "rb_policy_count": len(rb_policy),
            "projection_hash": projection_hash,
        },
        family=EventFamily.PROJECTION.value,
    ))

    return projection, trace


def _to_plain(obj: Any) -> Any:
    """
    Recursively convert MappingProxyType (and any nested proxies) to plain
    Python dicts so the result is JSON-serializable.
    """
    if isinstance(obj, MappingProxyType):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(item) for item in obj]
    return obj
