"""
Dispatch projection — execution routing table for token-native runtime.

Derives from the PIRGraph after S5 CONSTRUCT. Produces three integer-keyed
tables that together constitute the execution routing substrate:

    routing   — WF_addr → {CC_addr → {condition_addr: next_CC_addr}}
    pipeline  — CC_addr → [CT/CS_addr, ...] in pipeline step order
    entry     — WF_addr → {start: CC_addr, rb: RB_addr, in: IN_addr}

Workspace target: tokenized_snapshot/<structure_id>/dispatch.json

Design constraints:
    - All keys and values are integers (JSON strings for dict keys per JSON spec)
    - No FQDNs at any level — all identities resolved to addresses
    - Deterministic: same graph → same dispatch.json
    - Zero semantic inference at runtime — compiler owns all routing decisions

Foundational rule:
    The runtime MUST NOT reconstruct semantics the compiler already knew.
    Routing, pipeline ordering, and entry points are compile-time decisions.
    The runtime reads this table and executes — nothing more.

Address space:
    Nodes:       0x0000–0x3FFF
    Edge kinds:  0x4000–0x40FF
    Node kinds:  0x4100–0x41FF
    Outcomes:    0x5000–0x5FFF
    Transitions: 0x6000–0x6FFF
"""

from types import MappingProxyType
from typing import Any

from compiler.graph.graph import Graph
from compiler.graph.types import EdgeKind, NodeKind
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


def project_dispatch(graph: Graph) -> tuple[Projection, list[TraceEvent]]:
    """
    Generate dispatch routing projection from Graph.

    Reads NODE_NEXT, CC_BINDS_CT, CC_BINDS_CS, WF_START, WF_BINDS_RB,
    and WF_ADMITS_VIA_IN edges (all with addresses populated by S3).

    Content shape:
        {
            "routing":  {"WF_addr": {"CC_addr": {"condition_addr": next_CC_addr}}},
            "pipeline": {"CC_addr": [<step>, ...]},
            "entry":    {"WF_addr": {"start": CC_addr, "rb": RB_addr, "in": IN_addr}},
            "bindings": {"WF_addr": {"CC_addr": {"input_name": path_or_literal}}},
        }

    Pipeline step format (named-field execution instruction record):
        {
            "addr":      <int>,           # CT or CS address
            "op":        <str | null>,    # null for CT, operation name for CS
            "inputs":    <dict | null>,   # resolved input bindings ($.inputs.X, $.results.step_id.X, literals)
            "outputs":   <dict | null>,   # output surface mapping (CT: {surface_name: "$.capability_result.field"})
            "on_result": <dict | null>,   # step continuation semantics ({"SUCCESS": "continue", ...})
            "step_id":   <str>,           # symbolic step name for $.results.<step_id>.<field> references
        }

    All semantics are compiler-materialized. The dispatcher is a blind executor.
    FQDN values in step inputs are resolved to integer addresses at compile time.

    Bindings path format:
        - "$.payload.field"           — payload reference (key name stays symbolic)
        - "$.results.<CC_addr>.field" — previous CC result (CC code converted to addr)
        - "literal_value"             — constant (not a path)

    All dict keys are strings (JSON requirement). All address values are integers.

    Args:
        graph: Fully constructed and addressed PIRGraph (post-S5)

    Returns:
        Tuple of (Projection with dispatch content, trace events)
    """
    trace: list[TraceEvent] = []

    # --- Pre-pass: build node_key routing annotation tables from WF frontmatter ---
    # wf_node_next_keys[wf_addr][src_CC_addr][condition_str] = target_node_key
    # Needed to annotate routing values with target_node_key so the scheduler can
    # distinguish different WF usages of the same CC (e.g. four denial audit nodes).
    wf_node_next_keys: dict[str, dict[str, dict[str, str]]] = {}
    # wf_start_keys[wf_addr] = start_node_key (from core.start_node)
    wf_start_keys: dict[int, str] = {}
    # Authority: wf_actor[wf_addr] = actor_context FQDN bound at WF level (core.actor_context).
    wf_actor: dict[int, str] = {}
    # Observation: wf_emits[str(wf_addr)] = {exit_node_key: [EV_FQDN, ...]} — the moments announced
    # on exit, in the order the artifact declares them. A single moment is a sequence of one: the
    # order is normative, so what is sealed is a list even where the declaration names one, and the
    # runtime never has to know which form the author wrote.
    wf_emits: dict[str, dict[str, list[str]]] = {}
    # Every declared ending, by node key. An EXIT carries no address, so the sealed representation
    # previously carried no trace of it — and a transition to a declared ending was indistinguishable
    # at runtime from an outcome nobody routed. `3a` EX-5 requires an outcome with no declared
    # routing to REFUSE, which is unenforceable while the two look the same.
    wf_exit_keys: dict[str, dict[str, str]] = {}

    for _wf_fqdn, _wf_n in graph.nodes.items():
        if _wf_n.kind != NodeKind.WF or _wf_n.address < 0:
            continue
        _core = _wf_n.frontmatter.get("core", {})
        if not hasattr(_core, "get"):
            continue
        _start_nk = _core.get("start_node", "")
        if _start_nk:
            wf_start_keys[_wf_n.address] = _start_nk
        _actor = _core.get("actor_context")
        if _actor:
            wf_actor[_wf_n.address] = _actor
        _nodes_dict = _core.get("nodes", {})
        if not hasattr(_nodes_dict, "items"):
            continue
        _wf_s = str(_wf_n.address)
        _src_map: dict[str, dict[str, str]] = {}
        for _nk, _nd in _nodes_dict.items():
            if not hasattr(_nd, "get"):
                continue
            # Observation: an EXIT node may emit a domain event when reached.
            if _nd.get("type") == "EXIT":
                wf_exit_keys.setdefault(_wf_s, {})[_nk] = str(_nd.get("type"))
            if _nd.get("type") == "EXIT" and _nd.get("emit"):
                _em = _nd.get("emit")
                wf_emits.setdefault(_wf_s, {})[_nk] = [_em] if isinstance(_em, str) else list(_em)
            _fqdn_id = _nd.get("fqdn_id", "")
            if not _fqdn_id or _fqdn_id not in graph.nodes:
                continue
            _cc_n = graph.nodes[_fqdn_id]
            if _cc_n.address < 0:
                continue
            _next_map = _nd.get("next", {})
            if not isinstance(_next_map, dict) or not _next_map:
                continue
            _src_s = str(_cc_n.address)
            if _src_s not in _src_map:
                _src_map[_src_s] = {}
            for _cond_str, _tgt_nk in _next_map.items():
                _src_map[_src_s][_cond_str] = _tgt_nk
        wf_node_next_keys[_wf_s] = _src_map

    # Observation: resolve exit-node emits to the (source_CC, outcome) transition that routes there,
    # so the runtime emits the domain event when the CC produces that outcome (exits carry no address).
    # emit_map[str(wf_addr)][str(cc_addr)][outcome_str] = [EV_FQDN, ...] in announced order
    emit_map: dict[str, dict[str, dict[str, list[str]]]] = {}
    for _wf_s, _src_map in wf_node_next_keys.items():
        _exits = wf_emits.get(_wf_s, {})
        if not _exits:
            continue
        for _cc_s, _cond_map in _src_map.items():
            for _cond_str, _tgt_nk in _cond_map.items():
                if _tgt_nk in _exits:
                    emit_map.setdefault(_wf_s, {}).setdefault(_cc_s, {})[_cond_str] = _exits[_tgt_nk]

    # Termination, declared rather than inferred from absence.
    # terminal[str(wf_addr)][str(cc_addr)][str(condition_addr)] = {"exit": node_key, "type": "EXIT"}
    #
    # The scheduler consults routing first, then this. An outcome in neither is an outcome the
    # declarations do not answer for, and `3a` EX-5 and `3c` RT-9 both require refusal there. Ending
    # the traversal instead made a dead end indistinguishable from an ending — the workflow reported
    # the last contract's status as its own, and reported success.
    terminal: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    for _wf_s, _src_map in wf_node_next_keys.items():
        _exits = wf_exit_keys.get(_wf_s, {})
        if not _exits:
            continue
        for _cc_s, _cond_map in _src_map.items():
            for _cond_str, _tgt_nk in _cond_map.items():
                if _tgt_nk not in _exits:
                    continue
                _cond_addr = _resolve_condition_address(graph, _cond_str)
                if _cond_addr < 0:
                    continue
                terminal.setdefault(_wf_s, {}).setdefault(_cc_s, {})[str(_cond_addr)] = {
                    "exit": _tgt_nk, "type": _exits[_tgt_nk],
                }

    # --- Routing: WF_addr → {CC_addr → {condition_addr: {"addr": next_CC_addr, "key": next_node_key}}} ---
    # Source: NODE_NEXT edges (each carries wf_fqdn in metadata from S2).
    # Keyed by WF so shared CCs have correct per-WF continuations.
    # Values carry both address and node_key so the scheduler can distinguish
    # different WF usages of the same CC (e.g. multiple denial audit nodes).
    routing: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}

    for edge in graph.edges:
        if edge.kind != EdgeKind.NODE_NEXT:
            continue
        if edge.source_address < 0 or edge.target_address < 0:
            continue

        condition = edge.metadata.get("condition", "")
        condition_addr = _resolve_condition_address(graph, condition)
        if condition_addr < 0:
            continue  # Unaddressed condition — skip; compiler should have caught this

        wf_fqdn_meta = edge.metadata.get("wf_fqdn", "")
        wf_node = graph.nodes.get(wf_fqdn_meta)
        if wf_node is None or wf_node.address < 0:
            continue  # Edge has no valid WF context — skip

        wf_key = str(wf_node.address)
        src = str(edge.source_address)
        if wf_key not in routing:
            routing[wf_key] = {}
        if src not in routing[wf_key]:
            routing[wf_key][src] = {}
        condition_str = edge.metadata.get("condition", "")
        target_nk = wf_node_next_keys.get(wf_key, {}).get(src, {}).get(condition_str, "")
        routing[wf_key][src][str(condition_addr)] = {"addr": edge.target_address, "key": target_nk}

    # --- Pipeline: CC_addr → [<step_dict>, ...] ---
    # Source: CC_BINDS_CT and CC_BINDS_CS edges, sorted by pipeline_index.
    # Each step is a named-field execution instruction record (see docstring above).
    # All semantics (inputs, outputs, on_result) are compiler-materialized here.
    # The dispatcher consumes these records blindly — no semantic reconstruction.
    pipeline_raw: dict[str, list[tuple[int, dict]]] = {}

    for edge in graph.edges:
        if edge.kind not in (EdgeKind.CC_BINDS_CT, EdgeKind.CC_BINDS_CS):
            continue
        if edge.source_address < 0 or edge.target_address < 0:
            continue
        if "pipeline_index" not in edge.metadata:
            continue  # Skip re-typed S1 reference edges (no pipeline metadata)

        src = str(edge.source_address)
        idx = int(edge.metadata.get("pipeline_index", 0))
        step_id = edge.metadata.get("step_id", "") or ""
        raw_inputs = edge.metadata.get("inputs") or {}
        raw_outputs = edge.metadata.get("outputs") or {}
        raw_on_result = edge.metadata.get("on_result") or {}

        if edge.kind == EdgeKind.CC_BINDS_CT:
            op = None
            step_inputs = _resolve_cs_inputs(
                raw_inputs if isinstance(raw_inputs, dict) else {},
                "",  # no store for CT steps
                graph,
            ) or None
        else:  # CC_BINDS_CS
            op = edge.metadata.get("op") or None
            store = edge.metadata.get("store") or ""
            step_inputs = _resolve_cs_inputs(
                raw_inputs if isinstance(raw_inputs, dict) else {},
                store,
                graph,
            )

        step: dict = {
            "addr":      edge.target_address,
            "op":        op,
            "inputs":    step_inputs,
            "outputs":   raw_outputs or None,
            "on_result": raw_on_result or None,
            "step_id":   step_id,
        }

        if src not in pipeline_raw:
            pipeline_raw[src] = []
        pipeline_raw[src].append((idx, step))

    pipeline: dict[str, list[dict]] = {
        cc: [s for _, s in sorted(steps, key=lambda t: t[0])]
        for cc, steps in pipeline_raw.items()
    }

    # --- Bindings: WF_addr → {CC_addr: {input_name: path_or_literal}} ---
    # Source: WF nodes frontmatter.core.nodes (each CC node declares its WF-level inputs).
    # Paths of the form "$.results.CC_CODE.field" are converted to "$.results.<CC_addr>.field".
    bindings: dict[str, dict[str, dict[str, Any]]] = {}

    for wf_fqdn, wf_node in graph.nodes.items():
        if wf_node.kind != NodeKind.WF or wf_node.address < 0:
            continue

        # frontmatter may be MappingProxyType (not a subclass of dict) — use .get() directly
        core = wf_node.frontmatter.get("core", {})
        if not hasattr(core, "get"):
            continue

        nodes_dict = core.get("nodes", {})
        if not hasattr(nodes_dict, "items"):
            continue

        # Build CC artifact_code → address mapping for this WF's declared nodes
        code_to_addr: dict[str, int] = {}
        for node_key, wf_node_data in nodes_dict.items():
            if not hasattr(wf_node_data, "get"):
                continue
            if wf_node_data.get("type") != "CC":
                continue
            fqdn_id = wf_node_data.get("fqdn_id", "")
            if fqdn_id and fqdn_id in graph.nodes:
                cc_addr = graph.nodes[fqdn_id].address
                if cc_addr >= 0:
                    code_to_addr[node_key] = cc_addr

        wf_bindings: dict[str, dict[str, Any]] = {}
        for node_key, wf_node_data in nodes_dict.items():
            if not hasattr(wf_node_data, "get"):
                continue
            if wf_node_data.get("type") != "CC":
                continue
            fqdn_id = wf_node_data.get("fqdn_id", "")
            if not fqdn_id or fqdn_id not in graph.nodes:
                continue
            cc_node = graph.nodes[fqdn_id]
            if cc_node.address < 0:
                continue

            raw_inputs = wf_node_data.get("inputs", {})
            if not isinstance(raw_inputs, dict) or not raw_inputs:
                continue

            converted: dict[str, Any] = {}
            for input_name, binding in raw_inputs.items():
                converted[input_name] = _convert_binding(binding, code_to_addr)

            wf_bindings[node_key] = converted

        if wf_bindings:
            bindings[str(wf_node.address)] = wf_bindings

    # --- Entry: WF_addr → {start, rb, in} ---
    # Source: WF_START, WF_BINDS_RB, WF_ADMITS_VIA_IN edges
    wf_start: dict[int, int] = {}
    wf_rb: dict[int, int] = {}
    wf_in: dict[int, int] = {}

    for edge in graph.edges:
        if edge.source_address < 0 or edge.target_address < 0:
            continue
        if edge.kind == EdgeKind.WF_START:
            wf_start[edge.source_address] = edge.target_address
        elif edge.kind == EdgeKind.WF_BINDS_RB:
            # Owned binding only — set below from the declaration. An act that declares a reach
            # produces several WF→RB edges, because an edge kind is derived from the two node kinds
            # and cannot tell the binding an act owns from one it merely consults. Taking the last
            # edge would make which binding an act writes through depend on edge order.
            pass
        elif edge.kind == EdgeKind.WF_ADMITS_VIA_IN:
            wf_in[edge.source_address] = edge.target_address

    # The owned binding, read from the declaration that names it. `runtime_binding` is exactly one:
    # an act writes what it owns, and ownership that is shared is not ownership.
    for node in graph.nodes.values():
        if node.kind != NodeKind.WF or node.address < 0:
            continue
        owned = node.frontmatter.get("runtime_binding")
        if not owned:
            continue
        owned_node = graph.nodes.get(owned)
        if owned_node is not None and owned_node.address >= 0:
            wf_rb[node.address] = owned_node.address

    entry: dict[str, dict[str, Any]] = {}
    for wf_addr, start_addr in wf_start.items():
        e: dict[str, Any] = {
            "start": start_addr,
            "start_key": wf_start_keys.get(wf_addr, ""),
        }
        if wf_addr in wf_rb:
            e["rb"] = wf_rb[wf_addr]
        if wf_addr in wf_in:
            e["in"] = wf_in[wf_addr]
        if wf_addr in wf_actor:
            e["actor"] = wf_actor[wf_addr]   # Authority: actor context (FQDN) — runtime attribution
        entry[str(wf_addr)] = e

    # Admission contracts, so the gate determines rather than assumes.
    # admission[str(in_addr)] = {field: {"type": str, "required": bool}}
    #
    # The IN node declares `core.inputs`; the runtime admitted everything with an unconditional ACK,
    # which is `1c` AI-6 — inability to determine producing the same outcome as governance that
    # permits. Projecting the contract makes admission a determination over declared content.
    admission: dict[str, dict[str, Any]] = {}
    for _n in graph.nodes.values():
        if _n.kind != NodeKind.IN or _n.address < 0:
            continue
        _inputs = (_n.frontmatter.get("core", {}) or {}).get("inputs", {}) or {}
        if not hasattr(_inputs, "items"):
            continue
        admission[str(_n.address)] = {
            str(_f): {"type": _s.get("type"), "required": bool(_s.get("required", False))}
            for _f, _s in _inputs.items() if hasattr(_s, "get")
        }

    content = {
        "routing":  routing,
        "admission": admission,
        "terminal": terminal,
        "pipeline": pipeline,
        "entry":    entry,
        "bindings": bindings,
        "emits":    emit_map,   # Observation: {wf_addr: {cc_addr: {outcome: EV_FQDN}}}
    }

    projection_hash = compute_projection_hash(content)

    metadata = make_metadata(
        projection_type=ProjectionType.DISPATCH,
        graph_topology_hash=graph.topology_hash,
        graph_address_hash=graph.address_hash,
        projection_hash=projection_hash,
        compiler_version=COMPILER_VERSION,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
    )

    projection = Projection(
        projection_type=ProjectionType.DISPATCH,
        metadata=metadata,
        content=MappingProxyType(content),
    )

    trace.append(TraceEvent.create(
        stage="S6_PROJECT",
        operation="dispatch_projected",
        detail={
            "routing_count":  len(routing),
            "terminal_count": sum(len(c) for w in terminal.values() for c in w.values()),
            "pipeline_count": len(pipeline),
            "entry_count":    len(entry),
            "bindings_count": len(bindings),
            "projection_hash": projection_hash,
        },
        family=EventFamily.PROJECTION.value,
    ))

    return projection, trace


def _resolve_condition_address(graph: Graph, condition: str) -> int:
    """
    Resolve a routing condition string to its integer address.

    Conditions originate from WF transition declarations. They are allocated
    in the transition:: (0x6000) address space by S3 SEMANTIC_ADDRESSING.
    Outcome:: (0x5000) is checked as fallback for CC-outcome conditions.

    Returns -1 if the condition is not found in the address table.
    """
    if not condition:
        return -1
    addr = graph.address_table.get(f"transition::{condition}")
    if addr is not None:
        return addr
    addr = graph.address_table.get(f"outcome::{condition}")
    if addr is not None:
        return addr
    return -1


def _resolve_cs_inputs(
    raw_inputs: dict,
    store: str,
    graph: Graph,
) -> dict[str, Any]:
    """
    Resolve CS step input bindings for the dispatch pipeline.

    Converts FQDN string values (containing "::") to their integer addresses.
    Preserves $.inputs.X and $.results.step_name.X paths as-is (CT-atom step references).
    Preserves literal string values as-is.
    Includes store key if declared (tells dispatcher which config key to use).
    """
    resolved: dict[str, Any] = {}
    for k, v in raw_inputs.items():
        resolved[k] = _resolve_value(v, graph)
    if store:
        resolved["__store__"] = store
    return resolved


def _resolve_value(value: Any, graph: Graph) -> Any:
    """Recursively resolve a value, converting FQDN strings to addresses."""
    if isinstance(value, str):
        if "::" in value and not value.startswith("$"):
            # FQDN reference — convert to integer address
            node = graph.nodes.get(value)
            if node is not None and node.address >= 0:
                return node.address
        return value
    if isinstance(value, dict):
        return {k: _resolve_value(v, graph) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_resolve_value(v, graph) for v in value]
    return value


def _convert_binding(binding: Any, code_to_addr: dict[str, int]) -> Any:
    """Recursively convert binding values, applying path conversion to leaf strings."""
    if isinstance(binding, str):
        return _convert_binding_path(binding, code_to_addr)
    if isinstance(binding, dict):
        return {k: _convert_binding(v, code_to_addr) for k, v in binding.items()}
    if isinstance(binding, (list, tuple)):
        return [_convert_binding(v, code_to_addr) for v in binding]
    return binding


def _convert_binding_path(binding: str, code_to_addr: dict[str, int]) -> str:
    """
    Convert WF-level CC input binding path from code-based to address-based.

    Transforms "$.results.CC_CODE.field" → "$.results.<CC_addr>.field".
    Leaves "$.payload.field" and literal values unchanged.
    """
    if not binding.startswith("$.results."):
        return binding
    # Split: "$.results.CC_CODE.rest_of_path"
    after_results = binding[len("$.results."):]
    dot_idx = after_results.find(".")
    if dot_idx < 0:
        return binding  # Malformed — leave as-is
    cc_code = after_results[:dot_idx]
    rest = after_results[dot_idx + 1:]
    addr = code_to_addr.get(cc_code)
    if addr is None:
        return binding  # Unknown code — leave as-is
    return f"$.results.{addr}.{rest}"
