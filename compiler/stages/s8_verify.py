"""
S8 VERIFY — Output integrity verification.

Input: State from S7 (materialized paths populated)
Output: State with verification results

Verifies:
1. All materialized files exist on disk
2. Roundtrip integrity — parse(materialized_json) matches projection
3. No undeclared files in output directories (strict mode)
4. No undeclared directories in output (zero extra directories)
"""

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver

from compiler.graph.state import State
from compiler.graph.trace import TraceEvent
from compiler.graph.evidence import EventFamily
from compiler.graph.hashing import compute_projection_hash
from compiler.atoms.errors import CompilerError
from compiler.atoms.error_codes import ErrorCode
from compiler.atoms.force import in_force
from compiler.atoms.sorting import ensure_deterministic_output
from compiler.graph.graph import Graph
from compiler.graph.types import NodeKind
from compiler.projections import ProjectionClass, ProjectionType, Projection


def s8_verify(state: State) -> State:
    """
    S8 VERIFY: Verify materialized output integrity.

    State → State.
    """
    state = state.with_stage("S8_VERIFY")
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    materialized_paths = state.materialized_paths
    canonical = state.get_projection(ProjectionType.CANONICAL.value)
    projections = canonical.content if canonical else MappingProxyType({})
    structure_config = dict(state.structure_config)

    if not materialized_paths:
        return state.with_errors(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message="No materialized paths to verify (S7 MATERIALIZE may have failed)",
            phase="S8_VERIFY",
        ))

    # --- Check 1: All expected files exist ---
    expected_paths = {Path(p) for p in materialized_paths}
    for expected_path in expected_paths:
        if not expected_path.exists():
            errors.append(CompilerError(
                code=ErrorCode.E401_MISSING_OUTPUT,
                message=f"Expected output not found: {expected_path}",
                phase="S8_VERIFY",
            ))

    # --- Check 2: Roundtrip integrity ---
    roundtrip_errors = _verify_roundtrip(projections, materialized_paths)
    errors.extend(roundtrip_errors)

    # --- Check 3: Undeclared files ---
    undeclared_errors = _check_undeclared_files(
        structure_config, expected_paths,
    )
    errors.extend(undeclared_errors)

    # --- Check 4: Undeclared directories ---
    undeclared_dir_errors = _check_undeclared_directories(
        structure_config, materialized_paths,
    )
    errors.extend(undeclared_dir_errors)

    # --- Check 5: Tokenized projection integrity ---
    tokenized = state.get_projection(ProjectionType.TOKENIZED.value)
    if tokenized is not None:
        integrity_errors = _verify_tokenized_integrity(tokenized, state.graph)
        errors.extend(integrity_errors)

    # --- Check 6: Evidence projection integrity ---
    evidence = state.get_projection(ProjectionType.EVIDENCE.value)
    if evidence is not None:
        evidence_errors = _verify_evidence_integrity(evidence, state.graph)
        errors.extend(evidence_errors)

    # --- Check 7: EvidenceGraph integrity (hash + structure) ---
    evidence_graph_path = next(
        (Path(p) for p in materialized_paths if Path(p).name == "evidence_graph.json"),
        None,
    )
    if evidence_graph_path is not None and evidence_graph_path.exists():
        eg_errors = _verify_evidence_graph_integrity(evidence_graph_path)
        errors.extend(eg_errors)

    # --- Check 8: Canonical references referential closure ---
    if canonical is not None:
        from compiler.stages.s2_canonicalize import _import_surface_fqdns
        imported = _import_surface_fqdns(state.structure_config)
        ref_errors = _verify_canonical_references(canonical, state.graph, imported)
        errors.extend(ref_errors)

    # --- Check 9: Dispatch routing fidelity ---
    dispatch = state.get_projection(ProjectionType.DISPATCH.value)
    if dispatch is not None:
        errors.extend(_verify_dispatch_routing(dispatch.content, state.graph))

    # --- Check 10: Nothing superseded is in force ---
    errors.extend(_verify_superseded_not_in_force(
        dispatch.content if dispatch is not None else {},
        dict(state.stage_metadata).get("assertion_coverage") or [],
        state.graph,
    ))

    trace.append(TraceEvent.create(
        stage="S8_VERIFY",
        operation="verification_complete",
        detail={
            "files_checked": len(materialized_paths),
            "errors": len(errors),
            "verified": len(errors) == 0,
        },
        family=EventFamily.VERIFICATION.value,
    ))

    if errors:
        state = state.with_errors(*errors)
    if trace:
        state = state.with_trace_events(*trace)

    state = state.with_metadata("verified", len(errors) == 0)

    return state


def _verify_roundtrip(
    projections: Any,
    materialized_paths: tuple[str, ...],
) -> list[CompilerError]:
    """
    Verify roundtrip: parse(materialized_json) == projection.

    Validation is conditional on projection_class, not filename:
    - CANONICAL_ARTIFACT files carry fqdn_id and are roundtrip-verified
      against the canonical projection content.
    - All other projection classes (machine, symbol, evidence substrates)
      do not carry fqdn_id and are skipped here; they have dedicated checks.

    This replaces ad-hoc name-based skips. Any new projection type that
    sets projection_class != canonical_artifact is automatically handled.
    """
    errors: list[CompilerError] = []

    for path_str in materialized_paths:
        path = Path(path_str)
        if not path.exists():
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                materialized = json.load(f)

            # Class-based gate: only CANONICAL_ARTIFACT files are roundtrip-verified.
            # All other projection classes embed projection_class in their JSON and
            # are skipped here; they have dedicated structural checks elsewhere.
            proj_class = materialized.get("projection_class")
            if proj_class is not None and proj_class != ProjectionClass.CANONICAL_ARTIFACT.value:
                continue

            # Metadata files carry projection_type without fqdn_id — not artifacts.
            if "projection_type" in materialized and "fqdn_id" not in materialized:
                continue

            # Conformance tests carry artifact_type "CT_CONFORMANCE" without fqdn_id.
            if materialized.get("artifact_type") == "CT_CONFORMANCE":
                continue

            # Vocabulary flat lookup tables (forward.json, reverse.json) cannot carry
            # projection_class without polluting the address→FQDN lookup schema.
            # Their class is declared in sibling metadata.json (projection_type: vocabulary).
            if path.name in ("forward.json", "reverse.json"):
                continue

            fqdn_id = materialized.get("fqdn_id")
            if not fqdn_id:
                errors.append(CompilerError(
                    code=ErrorCode.E403_OUTPUT_MISMATCH,
                    message=f"Materialized artifact missing fqdn_id: {path}",
                    phase="S8_VERIFY",
                ))
                continue

            original = projections.get(fqdn_id)
            if not original:
                errors.append(CompilerError(
                    code=ErrorCode.E403_OUTPUT_MISMATCH,
                    message=f"No projection for FQDN: {fqdn_id}",
                    phase="S8_VERIFY",
                    fqdn_id=fqdn_id,
                ))
                continue

            normalized_original = ensure_deterministic_output(dict(original))
            normalized_materialized = ensure_deterministic_output(materialized)

            if normalized_original != normalized_materialized:
                errors.append(CompilerError(
                    code=ErrorCode.E403_OUTPUT_MISMATCH,
                    message=f"Roundtrip mismatch: {fqdn_id}",
                    phase="S8_VERIFY",
                    fqdn_id=fqdn_id,
                ))

        except json.JSONDecodeError as e:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Invalid JSON in materialized file: {e}",
                phase="S8_VERIFY",
            ))
        except Exception as e:
            errors.append(CompilerError(
                code=ErrorCode.E901_INTERNAL_ERROR,
                message=f"Roundtrip verification error: {e}",
                phase="S8_VERIFY",
            ))

    return errors


def _check_undeclared_files(
    structure_config: dict[str, Any],
    expected_paths: set[Path],
) -> list[CompilerError]:
    """Check for undeclared files in output directories."""
    errors: list[CompilerError] = []
    resolver = LayerResolver()

    layer_outputs = structure_config.get("output_configuration", {}).get("layer_outputs", {})
    actual_paths: set[Path] = set()

    for layer_code in layer_outputs:
        layer_output_dir = resolver.resolve_output_path(
            "layer_outputs", layer_code, structure_config,
        )
        if layer_output_dir.exists():
            actual_paths.update(layer_output_dir.rglob("*.json"))

    actual_paths = {p for p in actual_paths if not p.name.endswith(".tmp")}
    undeclared = actual_paths - expected_paths

    for undeclared_path in undeclared:
        errors.append(CompilerError(
            code=ErrorCode.E402_UNDECLARED_OUTPUT,
            message=f"Undeclared output: {undeclared_path}",
            phase="S8_VERIFY",
        ))

    return errors


def _check_undeclared_directories(
    structure_config: dict[str, Any],
    materialized_paths: tuple[str, ...],
) -> list[CompilerError]:
    """Check for undeclared directories in output."""
    errors: list[CompilerError] = []
    resolver = LayerResolver()

    layer_outputs = structure_config.get("output_configuration", {}).get("layer_outputs", {})
    output_dirs: list[Path] = []

    for layer_code in layer_outputs:
        layer_output_dir = resolver.resolve_output_path(
            "layer_outputs", layer_code, structure_config,
        )
        output_dirs.append(layer_output_dir)

    # Build allowed directory set
    allowed_dirs: set[Path] = set()
    for path_str in materialized_paths:
        path = Path(path_str)
        for out_dir in output_dirs:
            try:
                if path.is_relative_to(out_dir):
                    current = path.parent
                    while current != out_dir and current != current.parent:
                        allowed_dirs.add(current)
                        current = current.parent
                    break
            except (ValueError, TypeError):
                continue

    # Scan actual directories
    actual_dirs: set[Path] = set()
    for out_dir in output_dirs:
        if not out_dir.exists():
            continue
        for item in out_dir.rglob("*"):
            if item.is_dir() and not any(part.startswith(".") for part in item.parts):
                actual_dirs.add(item)

    undeclared = actual_dirs - allowed_dirs
    for undeclared_dir in undeclared:
        is_parent = any(
            allowed.is_relative_to(undeclared_dir) for allowed in allowed_dirs
        )
        if not is_parent:
            errors.append(CompilerError(
                code=ErrorCode.E402_UNDECLARED_OUTPUT,
                message=f"Undeclared output directory: {undeclared_dir}",
                phase="S8_VERIFY",
            ))

    return errors


def _verify_tokenized_integrity(
    tokenized: Projection,
    graph: Graph,
) -> list[CompilerError]:
    """
    Verify tokenized projection structural integrity.

    Goes beyond roundtrip — checks that the tokenized topology is
    internally consistent and faithful to the source graph.
    """
    errors: list[CompilerError] = []

    nodes = tokenized.content.get("nodes", [])
    edges = tokenized.content.get("edges", [])
    adjacency = tokenized.content.get("adjacency", {})

    # Build node address set from projection
    node_addresses = {n["address"] for n in nodes}

    # Check 1: Every node address resolves in graph.reverse_table
    for node in nodes:
        addr = node["address"]
        if addr not in graph.reverse_table:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Tokenized node address {addr} not in graph reverse_table",
                phase="S8_VERIFY",
            ))

    # Check 2: Every edge from/to references an existing node address
    for edge in edges:
        if edge["from"] not in node_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Tokenized edge 'from' address {edge['from']} not in node set",
                phase="S8_VERIFY",
            ))
        if edge["to"] not in node_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Tokenized edge 'to' address {edge['to']} not in node set",
                phase="S8_VERIFY",
            ))

    # Check 3: Every edge kind resolves to a valid address
    valid_kind_addresses = set(graph.address_table.values())
    for edge in edges:
        if edge["kind"] not in valid_kind_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Tokenized edge kind address {edge['kind']} not in address_table",
                phase="S8_VERIFY",
            ))

    # Check 4: Adjacency keys are subset of node addresses
    for key_str in adjacency:
        key_addr = int(key_str)
        if key_addr not in node_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Tokenized adjacency key {key_addr} not in node set",
                phase="S8_VERIFY",
            ))

    # Check 5: Adjacency targets match edge targets
    # Build expected adjacency from edges
    expected_adjacency: dict[int, set[int]] = {}
    for edge in edges:
        expected_adjacency.setdefault(edge["from"], set()).add(edge["to"])

    for key_str, targets in adjacency.items():
        key_addr = int(key_str)
        expected_targets = expected_adjacency.get(key_addr, set())
        actual_targets = set(targets)
        if actual_targets != expected_targets:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Tokenized adjacency mismatch for node {key_addr}: "
                        f"expected {sorted(expected_targets)}, got {sorted(actual_targets)}",
                phase="S8_VERIFY",
            ))

    return errors


def _verify_evidence_integrity(
    evidence: Projection,
    graph: Graph,
) -> list[CompilerError]:
    """
    Verify evidence projection structural integrity.

    Checks dual-form consistency: every entity must have matching
    FQDN and address representations that agree with the graph.
    """
    errors: list[CompilerError] = []

    nodes = evidence.content.get("nodes", [])
    edges = evidence.content.get("edges", [])
    event_catalog = evidence.content.get("event_catalog", [])

    # Build node address set from projection
    node_addresses = {n["address"] for n in nodes}
    node_fqdns = {n["fqdn"] for n in nodes}

    # Check 1: Dual-form node consistency — FQDN resolves to claimed address
    for node in nodes:
        fqdn = node["fqdn"]
        address = node["address"]

        # FQDN must exist in graph
        graph_node = graph.nodes.get(fqdn)
        if graph_node is None:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence node FQDN {fqdn} not in graph",
                phase="S8_VERIFY",
            ))
            continue

        # Address must match graph node's address
        if graph_node.address != address:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence node {fqdn}: address {address} != graph address {graph_node.address}",
                phase="S8_VERIFY",
            ))

    # Check 2: Edge dual-form consistency — source/target FQDNs and addresses match
    for edge in edges:
        source_fqdn = edge["source_fqdn"]
        target_fqdn = edge["target_fqdn"]

        if source_fqdn not in node_fqdns:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence edge source FQDN {source_fqdn} not in evidence node set",
                phase="S8_VERIFY",
            ))
        if target_fqdn not in node_fqdns:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence edge target FQDN {target_fqdn} not in evidence node set",
                phase="S8_VERIFY",
            ))
        if edge["source_address"] not in node_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence edge source address {edge['source_address']} not in node set",
                phase="S8_VERIFY",
            ))
        if edge["target_address"] not in node_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence edge target address {edge['target_address']} not in node set",
                phase="S8_VERIFY",
            ))

    # Check 3: Edge kind resolution — kind_address must be valid
    valid_kind_addresses = set(graph.address_table.values())
    for edge in edges:
        if edge["kind_address"] not in valid_kind_addresses:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence edge kind address {edge['kind_address']} not in address_table",
                phase="S8_VERIFY",
            ))

    # Check 4: Event catalog validity — must be EV nodes in graph with schemas
    for event in event_catalog:
        fqdn = event["fqdn"]
        graph_node = graph.nodes.get(fqdn)
        if graph_node is None:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence event catalog FQDN {fqdn} not in graph",
                phase="S8_VERIFY",
            ))
            continue
        if graph_node.kind != NodeKind.EV:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"Evidence event catalog entry {fqdn} is not NodeKind.EV (is {graph_node.kind.value})",
                phase="S8_VERIFY",
            ))

    return errors


def _verify_canonical_references(
    canonical: Projection,
    graph: Graph,
    imported: set[str] | None = None,
) -> list[CompilerError]:
    """
    Verify canonical projection referential closure.

    Every FQDN listed in any artifact's `references` field must exist as a node in the compiled
    graph, OR in the imported platform surface (references resolved AGAINST an already-compiled
    platform). A reference in neither is a genuine dangling dependency.
    """
    errors: list[CompilerError] = []
    imported = imported or set()

    for fqdn, artifact in canonical.content.items():
        references = artifact.get("references", [])
        if not isinstance(references, list):
            continue
        for ref_fqdn in references:
            if not isinstance(ref_fqdn, str):
                continue
            if ref_fqdn not in graph.nodes and ref_fqdn not in imported:
                errors.append(CompilerError(
                    code=ErrorCode.E201_MISSING_REFERENCE,
                    message=(
                        f"Canonical artifact {fqdn} references {ref_fqdn} "
                        f"which is not in the compiled graph"
                    ),
                    phase="S8_VERIFY",
                    fqdn_id=fqdn,
                ))

    return errors


def _verify_evidence_graph_integrity(path: Path) -> list[CompilerError]:
    """
    Verify EvidenceGraph structural integrity and hash.

    Checks:
    1. Hash integrity — evidence_graph_hash matches hash of core content
    2. Count consistency — event_count/edge_count match actual array lengths
    3. Edge referential integrity — all source/target IDs reference valid events
    4. STAGE_SEQUENCE edge count is bounded and non-zero
    """
    errors: list[CompilerError] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E403_OUTPUT_MISMATCH,
            message=f"Failed to load evidence_graph.json: {e}",
            phase="S8_VERIFY",
        ))
        return errors

    events = data.get("events", [])
    edges = data.get("edges", [])

    # Check 1: Hash integrity — recompute over core content keys
    stored_hash = data.get("evidence_graph_hash")
    if stored_hash:
        _CORE_KEYS = {"event_count", "edge_count", "events", "edges", "families"}
        core_content = {k: v for k, v in data.items() if k in _CORE_KEYS}
        recomputed = compute_projection_hash(core_content)
        if recomputed != stored_hash:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=(
                    f"evidence_graph.json hash mismatch: "
                    f"stored {stored_hash[:16]}... != computed {recomputed[:16]}..."
                ),
                phase="S8_VERIFY",
            ))
    else:
        errors.append(CompilerError(
            code=ErrorCode.E403_OUTPUT_MISMATCH,
            message="evidence_graph.json missing evidence_graph_hash field",
            phase="S8_VERIFY",
        ))

    # Check 2: Count consistency
    declared_event_count = data.get("event_count")
    if declared_event_count != len(events):
        errors.append(CompilerError(
            code=ErrorCode.E403_OUTPUT_MISMATCH,
            message=(
                f"evidence_graph.json event_count {declared_event_count} "
                f"!= actual {len(events)}"
            ),
            phase="S8_VERIFY",
        ))
    declared_edge_count = data.get("edge_count")
    if declared_edge_count != len(edges):
        errors.append(CompilerError(
            code=ErrorCode.E403_OUTPUT_MISMATCH,
            message=(
                f"evidence_graph.json edge_count {declared_edge_count} "
                f"!= actual {len(edges)}"
            ),
            phase="S8_VERIFY",
        ))

    # Check 3: Edge referential integrity
    event_ids = {e["event_id"] for e in events if "event_id" in e}
    for edge in edges:
        src = edge.get("source_event_id")
        tgt = edge.get("target_event_id")
        if src not in event_ids:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"evidence_graph.json edge source_event_id {src} not in event set",
                phase="S8_VERIFY",
            ))
        if tgt not in event_ids:
            errors.append(CompilerError(
                code=ErrorCode.E403_OUTPUT_MISMATCH,
                message=f"evidence_graph.json edge target_event_id {tgt} not in event set",
                phase="S8_VERIFY",
            ))

    # Check 4: STAGE_SEQUENCE edges — non-zero when events exist, bounded by stage count
    _MAX_STAGES = 8  # S1 through S8
    stage_seq_count = sum(1 for e in edges if e.get("kind") == "STAGE_SEQUENCE")
    if events and stage_seq_count == 0:
        errors.append(CompilerError(
            code=ErrorCode.E403_OUTPUT_MISMATCH,
            message="evidence_graph.json has events but no STAGE_SEQUENCE edges",
            phase="S8_VERIFY",
        ))
    if stage_seq_count > _MAX_STAGES:
        errors.append(CompilerError(
            code=ErrorCode.E403_OUTPUT_MISMATCH,
            message=(
                f"evidence_graph.json STAGE_SEQUENCE edge count {stage_seq_count} "
                f"exceeds maximum stage count {_MAX_STAGES}"
            ),
            phase="S8_VERIFY",
        ))

    return errors


def _declared_transitions(graph: Graph):
    """Every transition a workflow declares: (wf_fqdn, wf_addr, node_key, condition, target_key, nodes)."""
    for wf_fqdn, wf_node in graph.nodes.items():
        if wf_node.kind != NodeKind.WF or wf_node.address < 0:
            continue
        core = wf_node.frontmatter.get("core", {})
        nodes = core.get("nodes", {}) if hasattr(core, "get") else {}
        if not hasattr(nodes, "items"):
            continue
        for node_key, node in nodes.items():
            next_map = node.get("next", {}) if hasattr(node, "get") else {}
            if not hasattr(next_map, "items"):
                continue
            for condition, target_key in next_map.items():
                yield wf_fqdn, wf_node.address, node_key, str(condition), target_key, nodes


def _verify_dispatch_routing(content: Any, graph: Graph) -> list[CompilerError]:
    """
    The sealed dispatch realizes every transition each workflow declares, at the node that declares
    it, and nothing else.

    Routing, endings and announcements were once indexed by the contract a node runs. A contract run
    at several places kept only the last place's continuation, and every phase check and every
    earlier verification passed over it: they read the declarations, and the declarations were right.
    Only the sealed tables were wrong. So this reads the sealed tables against the declarations —
    a transition the runtime would take differently from the one declared refuses the build.
    """
    from compiler.projections.dispatch import _resolve_condition_address

    errors: list[CompilerError] = []

    def refuse(message: str) -> None:
        errors.append(CompilerError(code=ErrorCode.E403_OUTPUT_MISMATCH, message=message,
                                    phase="S8_VERIFY"))

    routing = content.get("routing", {}) or {}
    terminal = content.get("terminal", {}) or {}
    emits = content.get("emits", {}) or {}
    realized: set[tuple[str, str, str, str]] = set()   # (table, wf, node_key, condition key)

    for wf_fqdn, wf_addr, node_key, condition, target_key, nodes in _declared_transitions(graph):
        wf_s = str(wf_addr)
        where = f"{wf_fqdn} node {node_key!r} on {condition}"
        condition_addr = _resolve_condition_address(graph, condition)
        if condition_addr < 0:
            refuse(f"{where}: the outcome has no address, so the transition was never sealed")
            continue
        target = nodes.get(target_key)
        if not hasattr(target, "get"):
            refuse(f"{where}: routes to {target_key!r}, which the workflow does not declare")
            continue
        cond_s = str(condition_addr)
        if target.get("type") == "EXIT":
            sealed = terminal.get(wf_s, {}).get(node_key, {}).get(cond_s)
            realized.add(("terminal", wf_s, node_key, cond_s))
            if not sealed or sealed.get("exit") != target_key:
                refuse(f"{where}: declared to end at {target_key!r}; sealed ending is {sealed!r}")
            declared_emit = target.get("emit")
            if declared_emit:
                want = [declared_emit] if isinstance(declared_emit, str) else list(declared_emit)
                got = emits.get(wf_s, {}).get(node_key, {}).get(condition)
                realized.add(("emits", wf_s, node_key, condition))
                if got != want:
                    refuse(f"{where}: declared to announce {want}; sealed announcement is {got!r}")
        else:
            sealed = routing.get(wf_s, {}).get(node_key, {}).get(cond_s)
            realized.add(("routing", wf_s, node_key, cond_s))
            if not sealed or sealed.get("key") != target_key:
                refuse(f"{where}: declared to continue at {target_key!r}; sealed routing is {sealed!r}")

    for table_name, table in (("routing", routing), ("terminal", terminal), ("emits", emits)):
        for wf_s, node_map in table.items():
            for node_key, cond_map in node_map.items():
                for cond in cond_map:
                    if (table_name, wf_s, node_key, cond) not in realized:
                        refuse(f"sealed {table_name} for workflow {wf_s} node {node_key!r} on {cond} "
                               f"answers to no declared transition")
    return errors


def _verify_superseded_not_in_force(content: Any, coverage: list, graph: Graph) -> list[CompilerError]:
    """No superseded artifact confers effect in what the build produced.

    `artifact::INVARIANT_SUPERSEDED_NOT_IN_FORCE_V0`. Checked over the outputs rather than the code
    paths: a superseded workflow with a dispatch entry, a superseded intent with an admission
    contract, or a superseded invariant that ran an assertion is refused, whichever path let it
    through. A new path that forgets `in_force` fails here rather than leaving both a predecessor and
    its successor in force.
    """
    errors: list[CompilerError] = []
    entry = (content or {}).get("entry") or {}
    admission = (content or {}).get("admission") or {}
    ran = {c.get("fqdn_id") for c in coverage}
    for fqdn, node in graph.nodes.items():
        if in_force(node.frontmatter):
            continue
        reason = None
        if node.kind == NodeKind.WF and str(node.address) in entry:
            reason = "has a dispatch entry, so execution can start there"
        elif node.kind == NodeKind.IN and str(node.address) in admission:
            reason = "has an admission contract, so the gate admits through it"
        elif node.frontmatter.get("artifact_kind") == "INVARIANT":
            code = node.frontmatter.get("invariant_code") or node.artifact_code or ""
            if f"{node.namespace}::ASSERT_{code[len('INVARIANT_'):]}" in ran:
                reason = "derived an assertion that ran, so it is still enforced"
        if reason:
            errors.append(CompilerError(
                code=ErrorCode.E901_INTERNAL_ERROR,
                message=(f"{fqdn} is superseded and {reason}. A superseded artifact is present and "
                         f"not in force (INVARIANT_SUPERSEDED_NOT_IN_FORCE_V0); the path that put it "
                         f"there does not ask compiler.atoms.force.in_force."),
                phase="S8_VERIFY",
                fqdn_id=fqdn,
            ))
    return errors
