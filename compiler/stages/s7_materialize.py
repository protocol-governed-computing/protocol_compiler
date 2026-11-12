"""
S7 MATERIALIZE — Write projected artifacts to disk.

Input: State from S6 (projections populated)
Output: State with materialized_paths populated

Writes each projected artifact as deterministic JSON to the STRUCTURE-driven
output directory. Handles:
- STRUCTURE-driven path resolution via LayerResolver
- Artifact type → directory mapping
- Atomic writes (temp file + rename)
- Post-materialization workflow graph generation (best-effort)
"""

import json
from pathlib import Path
from typing import Any


from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver
from compiler.governance_engine.artifact_kinds import REGISTRY

from compiler.graph.types import NodeKind
from compiler.graph.graph import Graph
from compiler.graph.state import State
from compiler.graph.trace import TraceEvent
from compiler.graph.evidence import EventFamily, EvidenceGraph
from compiler.graph.hashing import compute_projection_hash
from compiler.atoms.errors import CompilerError
from compiler.atoms.error_codes import ErrorCode
from compiler.projections.workflow_graph import build_graph, write_graph
from compiler.governance_engine.platform_root import output_root
from compiler.projections import (
    COMPILER_VERSION,
    EVIDENCE_GRAPH_SCHEMA_VERSION,
    ProjectionClass,
    ProjectionType,
    Projection,
    get_structure_scope,
)


def _write_json(path: Path, data: Any, what: str, fqdn: str | None = None) -> CompilerError | None:
    """Write data as sorted, indented JSON, atomically, creating its directory.

    A reader sees the old file or the new one, never part of either. Returns the compile error that
    stops this file, or None.
    """
    try:
        text = json.dumps(data, indent=2, sort_keys=True)
    except (TypeError, ValueError) as e:
        return CompilerError(code=ErrorCode.E302_JSON_SERIALIZE_FAILED,
                             message=f"JSON serialization failed for {what}: {e}",
                             phase="S7_MATERIALIZE", fqdn_id=fqdn)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
    except OSError as e:
        return CompilerError(code=ErrorCode.E301_WRITE_FAILED, message=f"Failed to write {what}: {e}",
                             phase="S7_MATERIALIZE", fqdn_id=fqdn)
    return None


def _recorded(path: Path, structure_config: dict[str, Any]) -> str:
    """A written path as the evidence records it: relative to the build's declared output root.

    The evidence is sealed into the snapshot, so an absolute path made the snapshot's identity
    depend on the directory the build ran in: one declaration built in two places sealed two
    identities. Relative to the root the configuration declares, the record is the same wherever
    the build runs. A path outside that root is a defect, and raises.
    """
    return Path(path).relative_to(output_root(structure_config)).as_posix()


def s7_materialize(state: State) -> State:
    """
    S7 MATERIALIZE: Write projected artifacts to disk.

    State → State (with side effect: filesystem writes).
    """
    state = state.with_stage("S7_MATERIALIZE")
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []
    materialized: list[str] = []

    # Unwrap canonical projection — content is {fqdn: artifact_dict}
    canonical = state.get_projection(ProjectionType.CANONICAL.value)
    if canonical is None:
        return state.with_errors(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message="No canonical projection to materialize (S6 PROJECT may have failed)",
            phase="S7_MATERIALIZE",
        ))
    projections = canonical.content

    structure_config = dict(state.structure_config)

    resolver = LayerResolver()

    for fqdn in sorted(projections.keys()):
        artifact = projections[fqdn]
        artifact_type = artifact.get("artifact_type", "")
        artifact_code = artifact.get("artifact_code", "")
        # Where an artifact is written is its node's layer in this build. For an artifact this
        # domain authors that is also the layer its record states; a capability carried from the
        # platform records the platform's layer and is written under this domain's.
        node = state.graph.get_node(fqdn)
        layer_code = node.layer_code if node is not None else artifact.get("layer_code", "")
        domain_name = artifact.get("domain_name")

        if not layer_code:
            errors.append(CompilerError(
                code=ErrorCode.E301_WRITE_FAILED,
                message="Artifact missing layer_code",
                phase="S7_MATERIALIZE",
                fqdn_id=fqdn,
            ))
            continue

        # Resolve output directory via STRUCTURE
        try:
            artifact_output_dir = resolver.resolve_output_path(
                "layer_outputs",
                layer_code,
                structure_config,
                domain=domain_name,
            )
        except (RuntimeError, ValueError) as e:
            errors.append(CompilerError(
                code=ErrorCode.E301_WRITE_FAILED,
                message=f"Failed to resolve output path: {e}",
                phase="S7_MATERIALIZE",
                fqdn_id=fqdn,
            ))
            continue

        # Build output path
        encoded_fqdn = fqdn.replace("::", "__")
        try:
            type_dir_name = REGISTRY.directory(artifact_type)
        except ValueError as e:
            errors.append(CompilerError(
                code=ErrorCode.E301_WRITE_FAILED,
                message=f"Unknown artifact type for directory mapping: {e}",
                phase="S7_MATERIALIZE",
                fqdn_id=fqdn,
            ))
            continue

        type_dir = artifact_output_dir / type_dir_name
        output_path = type_dir / f"{encoded_fqdn}.json"

        error = _write_json(output_path, artifact, "artifact", fqdn=fqdn)
        if error:
            errors.append(error)
            continue
        materialized.append(str(output_path))

        trace.append(TraceEvent.create(
            stage="S7_MATERIALIZE",
            operation="artifact_written",
            subject_fqdn=fqdn,
            detail={"output_path": _recorded(output_path, structure_config), "artifact_type": artifact_type},
            family=EventFamily.MATERIALIZATION.value,
        ))

    # Post-materialization: generate conformance tests from TEST_DATA
    conf_paths, conf_errors, conf_trace = _generate_conformance_tests(
        state.graph, projections, structure_config, resolver
    )
    materialized.extend(conf_paths)
    errors.extend(conf_errors)
    trace.extend(conf_trace)

    # The behaviour-logic projection: one execution graph per workflow, under behavior_logic/.
    # They are not listed as materialized canonical output: the canonical metadata names canonical
    # artifacts only.
    _, graph_errors = _materialize_workflow_graphs(projections, structure_config, resolver)
    errors.extend(graph_errors)

    # Write metadata.json for canonical projection
    meta_paths, meta_errors = _write_projection_metadata(canonical, materialized, structure_config, resolver)
    materialized.extend(meta_paths)
    errors.extend(meta_errors)

    # Materialize vocabulary projection (per-structure address space)
    vocabulary = state.get_projection(ProjectionType.VOCABULARY.value)
    if vocabulary is not None:
        vocab_paths, vocab_errors, vocab_trace = _materialize_vocabulary(
            vocabulary, structure_config, resolver,
        )
        materialized.extend(vocab_paths)
        errors.extend(vocab_errors)
        trace.extend(vocab_trace)

    # Materialize tokenized topology projection (per-structure machine realization)
    tokenized = state.get_projection(ProjectionType.TOKENIZED.value)
    if tokenized is not None:
        vocabulary_hash = vocabulary.metadata.projection_hash if vocabulary else ""
        tok_paths, tok_errors, tok_trace = _materialize_tokenized(
            tokenized, structure_config, resolver, vocabulary_hash,
        )
        materialized.extend(tok_paths)
        errors.extend(tok_errors)
        trace.extend(tok_trace)

    # Materialize dispatch + handlers projections (token-native runtime substrate)
    dispatch = state.get_projection(ProjectionType.DISPATCH.value)
    handlers = state.get_projection(ProjectionType.HANDLERS.value)
    if dispatch is not None or handlers is not None:
        dis_paths, dis_errors, dis_trace = _materialize_dispatch_and_handlers(
            dispatch, handlers, structure_config, resolver,
        )
        materialized.extend(dis_paths)
        errors.extend(dis_errors)
        trace.extend(dis_trace)

    # Materialize evidence projection (per-structure dual-form substrate)
    evidence = state.get_projection(ProjectionType.EVIDENCE.value)
    if evidence is not None:
        vocabulary_hash_evi = vocabulary.metadata.projection_hash if vocabulary else ""
        tokenized_hash_evi = tokenized.metadata.projection_hash if tokenized else ""
        evi_paths, evi_errors, evi_trace = _materialize_evidence(
            evidence, structure_config, resolver, vocabulary_hash_evi, tokenized_hash_evi,
        )
        materialized.extend(evi_paths)
        errors.extend(evi_errors)
        trace.extend(evi_trace)

    # Flush accumulated errors and trace events so EvidenceGraph captures S1-S7
    if errors:
        state = state.with_errors(*errors)
    if trace:
        state = state.with_trace_events(*trace)
    errors = []
    trace = []

    # Materialize EvidenceGraph (compile trace substrate — S1-S7 events)
    eg_paths, eg_errors, eg_trace = _materialize_evidence_graph(
        state, structure_config, resolver,
    )
    materialized.extend(eg_paths)
    errors.extend(eg_errors)
    trace.extend(eg_trace)

    materialized_sorted = tuple(sorted(materialized))
    state = state.with_materialized_paths(materialized_sorted)

    if errors:
        state = state.with_errors(*errors)
    if trace:
        state = state.with_trace_events(*trace)

    state = state.with_metadata("materialized_count", len(materialized_sorted))

    return state


def _write_projection_metadata(
    projection: Any,
    materialized: list[str],
    structure_config: dict[str, Any],
    resolver: LayerResolver,
) -> tuple[list[str], list[CompilerError]]:
    """
    Write metadata.json for a projection to each output root directory.

    Determines output roots from the STRUCTURE layer_outputs configuration.
    metadata.json sits alongside artifact type directories in each
    compiled output root.
    """
    written: list[str] = []
    errors: list[CompilerError] = []

    if not materialized:
        return written, errors

    meta_dict = projection.metadata.to_dict()

    # Collect all output roots from STRUCTURE layer_outputs
    layer_outputs = structure_config.get("output_configuration", {}).get("layer_outputs", {})
    output_roots: set[Path] = set()

    for layer_code, layer_config in layer_outputs.items():
        domain = layer_config.get("domain") if isinstance(layer_config, dict) else None
        layer_dir = resolver.resolve_output_path(
            "layer_outputs", layer_code, structure_config,
            domain=domain,
        )
        if layer_dir.exists():
            output_roots.add(layer_dir)

    for output_root in sorted(output_roots):
        meta_path = output_root / "metadata.json"
        error = _write_json(meta_path, meta_dict, f"projection metadata to {output_root}")
        if error:
            errors.append(error)
        else:
            written.append(str(meta_path))

    return written, errors


def _materialize_vocabulary(
    vocabulary: Projection,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
) -> tuple[list[str], list[CompilerError], list[TraceEvent]]:
    """
    Materialize vocabulary projection as per-structure JSON files.

    Writes to STRUCTURE-resolved vocabulary output path under a
    structure-identity subdirectory:
        <vocabulary_root>/<structure_id>/forward.json
        <vocabulary_root>/<structure_id>/reverse.json
        <vocabulary_root>/<structure_id>/metadata.json
    """
    written: list[str] = []
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    structure_id = get_structure_scope(structure_config)
    if not structure_id:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize vocabulary: unknown structure identity",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Resolve vocabulary output root from STRUCTURE config
    output_config = structure_config.get("output_configuration", {})
    vocab_config = output_config.get("vocabulary_projection_path")
    if not vocab_config:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize vocabulary: no vocabulary_projection_path in STRUCTURE",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    try:
        vocab_root = resolver.resolve_output_path(
            "vocabulary_projection_path",
            "",  # not used for non-layer_outputs types
            structure_config,
        )
    except (RuntimeError, ValueError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message=f"Failed to resolve vocabulary output path: {e}",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Structure-specific subdirectory
    structure_dir = vocab_root / structure_id

    # Write forward.json, reverse.json, metadata.json
    # Note: forward/reverse are flat lookup tables (hex_addr → FQDN).
    # projection_class is NOT embedded in them — adding a non-address key
    # would pollute the table and break runtime loaders.
    # S8 skips them by projection_type declared in sibling metadata.json.
    files_to_write = {
        "forward.json": vocabulary.content.get("forward", {}),
        "reverse.json": vocabulary.content.get("reverse", {}),
        "metadata.json": {
            **vocabulary.metadata.to_dict(),
            "structure_id": structure_id,
            "allocation_strategy": "deterministic_fqdn_order",
            "address_count": len(vocabulary.content.get("forward", {})),
        },
    }

    for filename, data in files_to_write.items():
        output_path = structure_dir / filename
        error = _write_json(output_path, data, f"vocabulary {filename}")
        if error:
            errors.append(error)
        else:
            written.append(str(output_path))

    if written:
        trace.append(TraceEvent.create(
            stage="S7_MATERIALIZE",
            operation="vocabulary_materialized",
            detail={
                "structure_id": structure_id,
                "output_dir": _recorded(structure_dir, structure_config),
                "files_written": len(written),
            },
            family=EventFamily.MATERIALIZATION.value,
        ))

    return written, errors, trace


def _materialize_tokenized(
    tokenized: Projection,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
    vocabulary_hash: str,
) -> tuple[list[str], list[CompilerError], list[TraceEvent]]:
    """
    Materialize tokenized topology projection as per-structure JSON files.

    Writes to STRUCTURE-resolved tokenized output path under a
    structure-identity subdirectory:
        <tokenized_root>/<structure_id>/topology.json
        <tokenized_root>/<structure_id>/metadata.json
    """
    written: list[str] = []
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    structure_id = get_structure_scope(structure_config)
    if not structure_id:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize tokenized: unknown structure identity",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Resolve tokenized output root from STRUCTURE config
    output_config = structure_config.get("output_configuration", {})
    tok_config = output_config.get("tokenized_projection_path")
    if not tok_config:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize tokenized: no tokenized_projection_path in STRUCTURE",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    try:
        tok_root = resolver.resolve_output_path(
            "tokenized_projection_path",
            "",  # not used for non-layer_outputs types
            structure_config,
        )
    except (RuntimeError, ValueError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message=f"Failed to resolve tokenized output path: {e}",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Structure-specific subdirectory
    structure_dir = tok_root / structure_id

    # Write topology.json and metadata.json
    nodes = tokenized.content.get("nodes", [])
    edges = tokenized.content.get("edges", [])

    files_to_write = {
        "topology.json": {
            "projection_class": tokenized.metadata.projection_class.value,
            "nodes": list(nodes),
            "edges": list(edges),
            "adjacency": dict(tokenized.content.get("adjacency", {})),
        },
        "metadata.json": {
            **tokenized.metadata.to_dict(),
            "structure_id": structure_id,
            "vocabulary_hash": vocabulary_hash,
            "allocation_strategy": "deterministic_fqdn_order",
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    }

    for filename, data in files_to_write.items():
        output_path = structure_dir / filename
        error = _write_json(output_path, data, f"tokenized {filename}")
        if error:
            errors.append(error)
        else:
            written.append(str(output_path))

    if written:
        trace.append(TraceEvent.create(
            stage="S7_MATERIALIZE",
            operation="tokenized_materialized",
            detail={
                "structure_id": structure_id,
                "output_dir": _recorded(structure_dir, structure_config),
                "files_written": len(written),
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
            family=EventFamily.MATERIALIZATION.value,
        ))

    return written, errors, trace


def _materialize_dispatch_and_handlers(
    dispatch: Projection | None,
    handlers: Projection | None,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
) -> tuple[list[str], list[CompilerError], list[TraceEvent]]:
    """
    Materialize dispatch.json and handlers.json into the tokenized_snapshot directory.

    Both files land alongside topology.json in:
        <tokenized_root>/<structure_id>/dispatch.json
        <tokenized_root>/<structure_id>/handlers.json

    Uses the same tokenized_projection_path resolver as _materialize_tokenized.
    Writes atomically (temp + rename). Skips gracefully if either projection is None.
    """
    written: list[str] = []
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    structure_id = get_structure_scope(structure_config)
    if not structure_id:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize dispatch/handlers: unknown structure identity",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    try:
        tok_root = resolver.resolve_output_path(
            "tokenized_projection_path",
            "",
            structure_config,
        )
    except (RuntimeError, ValueError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message=f"Failed to resolve tokenized output path for dispatch/handlers: {e}",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    structure_dir = tok_root / structure_id

    files_to_write: dict[str, Any] = {}

    if dispatch is not None:
        files_to_write["dispatch.json"] = {
            "projection_class": dispatch.metadata.projection_class.value,
            "routing":   dict(dispatch.content.get("routing", {})),
            "terminal":  dict(dispatch.content.get("terminal", {})),
            "admission": dict(dispatch.content.get("admission", {})),
            "pipeline":  dict(dispatch.content.get("pipeline", {})),
            "entry":     dict(dispatch.content.get("entry", {})),
            "bindings":  dict(dispatch.content.get("bindings", {})),
            "emits":     dict(dispatch.content.get("emits", {})),
        }

    if handlers is not None:
        files_to_write["handlers.json"] = {
            "projection_class": handlers.metadata.projection_class.value,
            "ct":        dict(handlers.content.get("ct", {})),
            "cs":        dict(handlers.content.get("cs", {})),
            "rb_policy": dict(handlers.content.get("rb_policy", {})),
            # Per-act composed storage, present only for an act that declares a reach. Written
            # explicitly like every other key: this materializer enumerates what it writes rather
            # than copying the projection wholesale, so a projection key absent from this list is
            # sealed nowhere and read by nothing.
            "wf_storage": dict(handlers.content.get("wf_storage", {})),
        }

    for filename, data in files_to_write.items():
        output_path = structure_dir / filename
        error = _write_json(output_path, data, filename)
        if error:
            errors.append(error)
        else:
            written.append(str(output_path))

    if written:
        trace.append(TraceEvent.create(
            stage="S7_MATERIALIZE",
            operation="dispatch_handlers_materialized",
            detail={
                "structure_id": structure_id,
                "output_dir": _recorded(structure_dir, structure_config),
                "files_written": [_recorded(path, structure_config) for path in written],
            },
            family=EventFamily.MATERIALIZATION.value,
        ))

    return written, errors, trace


def _materialize_evidence(
    evidence: Projection,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
    vocabulary_hash: str,
    tokenized_hash: str,
) -> tuple[list[str], list[CompilerError], list[TraceEvent]]:
    """
    Materialize evidence projection as per-structure JSON files.

    Writes to STRUCTURE-resolved evidence output path under a
    structure-identity subdirectory:
        <evidence_root>/<structure_id>/evidence.json
        <evidence_root>/<structure_id>/metadata.json
    """
    written: list[str] = []
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    structure_id = get_structure_scope(structure_config)
    if not structure_id:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize evidence: unknown structure identity",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Resolve evidence output root from STRUCTURE config
    output_config = structure_config.get("output_configuration", {})
    evi_config = output_config.get("evidence_projection_path")
    if not evi_config:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize evidence: no evidence_projection_path in STRUCTURE",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    try:
        evi_root = resolver.resolve_output_path(
            "evidence_projection_path",
            "",
            structure_config,
        )
    except (RuntimeError, ValueError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message=f"Failed to resolve evidence output path: {e}",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Structure-specific subdirectory
    structure_dir = evi_root / structure_id

    # Write evidence.json and metadata.json
    nodes = list(evidence.content.get("nodes", []))
    edges = list(evidence.content.get("edges", []))
    event_catalog = list(evidence.content.get("event_catalog", []))

    files_to_write = {
        "evidence.json": {
            "projection_class": evidence.metadata.projection_class.value,
            "nodes": nodes,
            "edges": edges,
            "event_catalog": event_catalog,
        },
        "metadata.json": {
            **evidence.metadata.to_dict(),
            "structure_id": structure_id,
            "vocabulary_hash": vocabulary_hash,
            "tokenized_hash": tokenized_hash,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "ev_schema_count": len(event_catalog),
        },
    }

    for filename, data in files_to_write.items():
        output_path = structure_dir / filename
        error = _write_json(output_path, data, f"evidence {filename}")
        if error:
            errors.append(error)
        else:
            written.append(str(output_path))

    if written:
        trace.append(TraceEvent.create(
            stage="S7_MATERIALIZE",
            operation="evidence_materialized",
            detail={
                "structure_id": structure_id,
                "output_dir": _recorded(structure_dir, structure_config),
                "files_written": len(written),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "ev_schema_count": len(event_catalog),
            },
            family=EventFamily.MATERIALIZATION.value,
        ))

    return written, errors, trace


def _materialize_evidence_graph(
    state: State,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
) -> tuple[list[str], list[CompilerError], list[TraceEvent]]:
    """
    Materialize EvidenceGraph as compile trace substrate.

    Builds EvidenceGraph from accumulated trace events (S1-S7) and writes
    to evidence_snapshot/<structure_id>/evidence_graph.json.

    Writes:
        <evidence_root>/<structure_id>/evidence_graph.json
    """
    written: list[str] = []
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    structure_id = get_structure_scope(structure_config)
    if not structure_id:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize evidence graph: unknown structure identity",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    # Resolve evidence output root from STRUCTURE config
    output_config = structure_config.get("output_configuration", {})
    evi_config = output_config.get("evidence_projection_path")
    if not evi_config:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message="Cannot materialize evidence graph: no evidence_projection_path in STRUCTURE",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    try:
        evi_root = resolver.resolve_output_path(
            "evidence_projection_path",
            "",
            structure_config,
        )
    except (RuntimeError, ValueError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message=f"Failed to resolve evidence graph output path: {e}",
            phase="S7_MATERIALIZE",
        ))
        return written, errors, trace

    structure_dir = evi_root / structure_id

    # Build EvidenceGraph from all trace events accumulated so far (S1-S7)
    eg = EvidenceGraph.from_trace_events(state.trace_events)

    # Hash the core content (events + edges + families) — envelope fields excluded
    eg_content = eg.to_dict()
    evidence_graph_hash = compute_projection_hash(eg_content)

    data = {
        "projection_class": ProjectionClass.EVIDENCE_SUBSTRATE.value,
        **eg_content,
        "evidence_graph_hash": evidence_graph_hash,
        "structure_id": structure_id,
        "compiler_version": COMPILER_VERSION,
        "schema_version": EVIDENCE_GRAPH_SCHEMA_VERSION,
    }

    output_path = structure_dir / "evidence_graph.json"
    error = _write_json(output_path, data, "evidence graph")
    if error:
        errors.append(error)
    else:
        written.append(str(output_path))
        return written, errors, trace

    trace.append(TraceEvent.create(
        stage="S7_MATERIALIZE",
        operation="evidence_graph_materialized",
        detail={
            "structure_id": structure_id,
            "output_dir": _recorded(structure_dir, structure_config),
            "event_count": eg.event_count,
            "edge_count": eg.edge_count,
            "evidence_graph_hash": evidence_graph_hash,
        },
        family=EventFamily.MATERIALIZATION.value,
    ))

    return written, errors, trace


def _conformance_cases(
    td_fqdn: str, frontmatter: dict[str, Any], ct_by_fqdn: dict[str, dict],
) -> tuple[list[dict[str, Any]], list[CompilerError]]:
    """The runnable cases one vector declares, each bound to its target as sealed.

    Pure, so the binding can be judged without a build. Cases are governed content and are read from
    the vector's Machine block (`SCHEMA_TEST_DATA_V0`). A vector whose target does not resolve, or
    resolves to a transform with no sealed form, is a build failure: skipping it would report a domain
    as having run its vectors when one of them was never run.
    """
    errors: list[CompilerError] = []
    target = frontmatter.get("target")
    ct_artifact = ct_by_fqdn.get(target) if isinstance(target, str) else None
    if ct_artifact is None:
        errors.append(CompilerError(
            code=ErrorCode.E201_MISSING_REFERENCE,
            message=f"Test vector targets {target!r}, which is not a transform this build declares",
            phase="S7_MATERIALIZE", fqdn_id=td_fqdn,
        ))
        return [], errors
    ct_ir_base = ct_artifact.get("ct_ir")
    if not ct_ir_base:
        errors.append(CompilerError(
            code=ErrorCode.E205_CT_VALIDATION_FAILED,
            message=f"Test vector targets {target}, which has no sealed form to run",
            phase="S7_MATERIALIZE", fqdn_id=td_fqdn,
        ))
        return [], errors

    input_types = {
        key: spec["type"]
        for key, spec in (ct_ir_base.get("inputs") or {}).items()
        if isinstance(spec, dict) and "type" in spec
    } if isinstance(ct_ir_base.get("inputs"), dict) else {}

    out: list[dict[str, Any]] = []
    for case in frontmatter.get("cases") or []:
        ct_ir = dict(ct_ir_base)
        ct_ir["inputs"] = case.get("bindings", {})
        if input_types:
            ct_ir["input_types"] = input_types
        runnable: dict[str, Any] = {
            "artifact_type": "CT_CONFORMANCE",
            "ct_fqdn": target,
            "ct_ir": ct_ir,
            "expected": case.get("expected", {}),
            "expected_outcome": case["expected_outcome"],
            "fqdn": f"{target}::{case['case_id']}",
            "test_data_source": td_fqdn,
        }
        if case.get("assertions"):
            runnable["assertions"] = case["assertions"]
        if case.get("recorded"):
            runnable["recorded"] = case["recorded"]
        out.append(runnable)
    return out, errors


def _generate_conformance_tests(
    graph: Graph,
    projections: Any,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
) -> tuple[list[str], list[CompilerError], list[TraceEvent]]:
    """
    Write every runnable case the build's vectors declare, where the build declares.

    One file per case, bound to its target transform as sealed. A build with no vectors writes
    nothing and declares nothing; a build with vectors must declare where its cases go.
    """
    materialized: list[str] = []
    errors: list[CompilerError] = []
    trace: list[TraceEvent] = []

    test_data_nodes = [
        node for node in graph.nodes.values()
        if node.kind == NodeKind.TEST_DATA
    ]
    if not test_data_nodes:
        return materialized, errors, trace

    try:
        conf_dir = resolver.resolve_output_path("conformance", "COMPILER", structure_config)
    except (RuntimeError, ValueError) as e:
        errors.append(CompilerError(
            code=ErrorCode.E301_WRITE_FAILED,
            message=f"Failed to resolve conformance output path: {e}",
            phase="S7_MATERIALIZE",
        ))
        return materialized, errors, trace

    ct_by_fqdn: dict[str, dict] = {
        artifact["fqdn_id"]: artifact
        for artifact in projections.values()
        if artifact.get("artifact_type") == "CT"
    }

    for td_node in test_data_nodes:
        cases, case_errors = _conformance_cases(td_node.fqdn, dict(td_node.frontmatter), ct_by_fqdn)
        errors.extend(case_errors)
        for runnable in cases:
            filename = runnable["fqdn"].replace("::", "__") + ".json"
            output_path = conf_dir / filename
            error = _write_json(output_path, runnable, f"conformance case {filename}", fqdn=td_node.fqdn)
            if error:
                errors.append(error)
                continue
            materialized.append(str(output_path))
            trace.append(TraceEvent.create(
                stage="S7_MATERIALIZE",
                operation="conformance_written",
                subject_fqdn=runnable["fqdn"],
                detail={"output_path": _recorded(output_path, structure_config), "test_data_source": td_node.fqdn},
                family=EventFamily.MATERIALIZATION.value,
            ))

    return materialized, errors, trace


def _materialize_workflow_graphs(
    projections: Any,
    structure_config: dict[str, Any],
    resolver: LayerResolver,
) -> tuple[list[str], list[CompilerError]]:
    """Write each workflow's execution graph into behavior_logic/.

    The graph is a sealed constituent of the snapshot that the runtime, the inspector and the
    clients read, so a workflow whose graph cannot be written fails the build.
    """
    cc_artifacts = {a["artifact_code"]: a for a in projections.values()
                    if a.get("artifact_type") == "CC" and a.get("artifact_code")}
    written: list[str] = []
    errors: list[CompilerError] = []

    for fqdn, wf_artifact in sorted(projections.items()):
        if wf_artifact.get("artifact_type") != "WF":
            continue
        layer_code = wf_artifact.get("layer_code")
        if not layer_code:
            errors.append(CompilerError(
                code=ErrorCode.E301_WRITE_FAILED, message="Workflow missing layer_code",
                phase="S7_MATERIALIZE", fqdn_id=fqdn))
            continue
        try:
            compiled_root = resolver.resolve_output_path(
                "layer_outputs", layer_code, structure_config, domain=wf_artifact.get("domain_name"))
            path = write_graph(build_graph(wf_artifact, cc_artifacts), compiled_root.parent / "behavior_logic")
        except (OSError, RuntimeError, ValueError) as e:
            errors.append(CompilerError(
                code=ErrorCode.E301_WRITE_FAILED, message=f"Failed to write workflow graph: {e}",
                phase="S7_MATERIALIZE", fqdn_id=fqdn))
            continue
        written.append(str(path))

    return written, errors
