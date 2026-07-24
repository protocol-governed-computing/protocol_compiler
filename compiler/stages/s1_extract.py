"""
S1 EXTRACT — Discovery + parsing → initial Graph population.

Input: State (initial, with structure_config)
Output: State with Graph populated with nodes (address=-1, ir=None)

Each discovered artifact becomes a Node. References become Edges
with kind=REFERENCES (typed in S2 CANONICALIZE).
"""

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from compiler.graph.types import NodeKind, EdgeKind
from compiler.graph.node import Node
from compiler.graph.edge import Edge
from compiler.graph.graph import GraphBuilder
from compiler.graph.state import State
from compiler.graph.trace import TraceEvent
from compiler.graph.evidence import EventFamily
from compiler.atoms.errors import CompilerError
from compiler.atoms.error_codes import ErrorCode
from compiler.structure_loader import (
    load_structure_artifact,
    get_bootstrap_search_roots,
)

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver


# Machine block pattern: ## Machine\n```yaml\n{yaml}\n```
_MACHINE_BLOCK_PATTERN = re.compile(
    r"^## Machine\s*\n+```yaml\s*\n(?P<machine_yaml>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)

# Artifact type → NodeKind mapping
def _type_to_kind(artifact_type: str) -> NodeKind | None:
    """Artifact-type prefix → NodeKind, via the single-source-of-truth ArtifactKindRegistry.

    Replaces the legacy _TYPE_TO_KIND dict. The registry returns the NodeKind as a string (it is a
    governance-layer module and must not import this compiler enum); we map it to NodeKind here.
    """
    from compiler.governance_engine.artifact_kinds import REGISTRY
    nk = REGISTRY.node_kind(artifact_type)
    return NodeKind(nk) if nk is not None else None


def s1_extract(state: State) -> State:
    """
    S1 EXTRACT: Discover artifacts and populate Graph with nodes.

    Pure function: State → State.

    Steps:
        1. Load STRUCTURE_DISCOVERY_V0 + build-specific STRUCTURE config
        2. Discover artifact files from declared layers
        3. Parse Machine YAML from each artifact
        4. Derive FQDNs from STRUCTURE_IDENTITY_V0 rules
        5. Create Nodes for each artifact
        6. Extract references and create REFERENCES edges

    Args:
        state: Initial State (from State.initial())

    Returns:
        New State with graph populated (nodes + reference edges)
    """
    state = state.with_stage("S1_EXTRACT")
    errors: list[CompilerError] = []
    warnings: list[CompilerError] = []
    trace: list[TraceEvent] = []

    structure_config = dict(state.structure_config)
    structure_artifact_code = structure_config.get("structure_artifact_code", "")

    if not structure_artifact_code:
        return state.with_errors(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message="structure_config missing 'structure_artifact_code'",
            phase="S1_EXTRACT",
        ))

    search_roots = get_bootstrap_search_roots()

    # --- Step 1: Load discovery and build configs ---
    try:
        discovery_master = load_structure_artifact("STRUCTURE_DISCOVERY_V0", search_roots)
        build_config = load_structure_artifact(structure_artifact_code, search_roots)
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        return state.with_errors(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message=f"Failed to load STRUCTURE artifacts: {e}",
            phase="S1_EXTRACT",
        ))

    discovery_config = discovery_master.get("discovery", {})
    discovery_layers = discovery_config.get("layers", {})
    discovery_rules = discovery_config.get("rules", {})

    artifact_discovery = build_config.get("artifact_discovery", {})
    search_layers = artifact_discovery.get("search_layers", [])
    build_artifact_types = artifact_discovery.get("artifact_types", [])

    if not search_layers:
        return state.with_errors(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message=f"STRUCTURE {structure_artifact_code} artifact_discovery.search_layers is empty",
            phase="S1_EXTRACT",
        ))

    # --- Step 2: Load identity rules ---
    try:
        identity_master = load_structure_artifact("STRUCTURE_IDENTITY_V0", search_roots)
        identity_rules = (
            identity_master.get("identity", {})
            .get("fqdn", {})
            .get("namespace", {})
            .get("derivation", {})
            .get("rules", [])
        )
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        return state.with_errors(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message=f"Failed to load STRUCTURE_IDENTITY_V0: {e}",
            phase="S1_EXTRACT",
        ))

    # --- Domain-extension: merge the build manifest's additive layer defs + identity rules ---
    # The platform STRUCTURE_DISCOVERY_V0 / STRUCTURE_IDENTITY_V0 remain immutable and untouched;
    # a domain describes its own layer + namespace rule in its build manifest, merged only here.
    from compiler.governance_engine.structure.resolution.layer_resolver import (
        register_domain_layers, clear_domain_layers,
    )
    domain_layers = build_config.get("layer_definitions", {}) or {}
    clear_domain_layers()
    register_domain_layers(domain_layers)                       # LayerResolver path resolution
    discovery_layers = {**discovery_layers, **domain_layers}    # _discover_artifacts layer-config lookup
    identity_rules = list(build_config.get("identity_rules", []) or []) + list(identity_rules)

    # Authorized namespace allowlist: every namespace an identity rule can produce. A declared FQDN
    # whose namespace is outside this set is unauthorized (INVARIANT_FQDN_NAMESPACE_AUTHORIZED_V0).
    # This is the identity rules repurposed from derivation to authorization.
    authorized_namespaces = sorted({
        r.get("namespace") for r in identity_rules if r.get("namespace")
    })

    # --- Step 3: Discover artifact files ---
    discovered = _discover_artifacts(
        search_layers, discovery_layers, discovery_rules,
        build_artifact_types, errors
    )

    if not discovered and not errors:
        errors.append(CompilerError(
            code=ErrorCode.E001_NO_ARTIFACTS,
            message="No artifacts found in build scope",
            phase="S1_EXTRACT",
        ))

    if errors:
        return state.with_errors(*errors)

    # --- Step 4: Derive FQDNs ---
    _derive_fqdns(discovered, identity_rules, errors)

    if errors:
        return state.with_errors(*errors)

    trace.append(TraceEvent.create(
        stage="S1_EXTRACT",
        operation="discovery_complete",
        detail={"artifacts_discovered": len(discovered)},
        family=EventFamily.DISCOVERY.value,
    ))

    # --- Step 5: Parse and build graph ---
    builder = GraphBuilder()

    # Build artifact registry for reference validation
    artifact_registry: dict[str, list[str]] = {}
    for artifact in discovered:
        code = artifact["artifact_code"]
        ns = artifact["namespace"]
        if code not in artifact_registry:
            artifact_registry[code] = []
        if ns not in artifact_registry[code]:
            artifact_registry[code].append(ns)

    all_refs: set[str] = set()
    for artifact in discovered:
        node, refs, parse_errors, parse_warnings = _parse_artifact_to_node(
            artifact, artifact_registry
        )
        errors.extend(parse_errors)
        warnings.extend(parse_warnings)

        if node is not None:
            builder.add_node(node)
            all_refs.update(refs)
            trace.append(TraceEvent.create(
                stage="S1_EXTRACT",
                operation="node_created",
                subject_fqdn=node.fqdn,
                detail={"kind": node.kind.value, "layer_code": node.layer_code},
                family=EventFamily.DISCOVERY.value,
            ))

            # Create REFERENCES edges for each resolved reference
            for ref_fqdn in refs:
                edge = Edge.create(
                    source_fqdn=node.fqdn,
                    target_fqdn=ref_fqdn,
                    kind=EdgeKind.REFERENCES,
                )
                builder.add_edge(edge)

    # Carry imported platform CAPABILITIES (CS/CT consumed by this domain) into the graph so they are
    # addressed, wired into CC pipelines, and emitted into this domain's handlers/dispatch (Option A
    # "static link"). Governance imports stay resolve-only (tolerated + dropped in S2).
    _inject_imported_capabilities(builder, all_refs, build_config, errors)

    # Import platform governance as checked protocol state (design §2). Domain-applicable invariants
    # enter the graph so S4 can assert them against domain artifacts; platform-only invariants are
    # filtered out by declared scope. No-op for the platform build (no import_surface).
    _inject_imported_governance(builder, build_config, errors)

    # Provenance (design §6): bind the exact governance closure this build was checked against, so a
    # domain can never be re-verified — or paired at runtime — under different governance than it
    # compiled under. Empty on the platform build (nothing imported).
    governance_closure = _compute_governance_closure(builder, build_config)

    graph = builder.build()
    state = state.with_graph(graph)

    if errors:
        state = state.with_errors(*errors)
    if warnings:
        state = state.with_warnings(*warnings)
    if trace:
        state = state.with_trace_events(*trace)

    # Record extraction metadata
    state = state.with_metadata("node_count", len(graph.nodes))
    state = state.with_metadata("edge_count", len(graph.edges))
    state = state.with_metadata("authorized_namespaces", authorized_namespaces)
    if governance_closure is not None:
        state = state.with_metadata("governance_closure", governance_closure)

    return state


def _compute_governance_closure(
    builder: GraphBuilder,
    build_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Deterministic digest over the exact imported governance set (design §6).

    The hash covers each imported invariant's FQDN + content_hash, sorted — so it changes only
    when the governance that checked this build changes, not when unrelated platform capabilities
    do. Returns None for the platform build (no import_surface, nothing imported).
    """
    imp = (build_config.get("artifact_discovery", {}) or {}).get("import_surface", {}) or {}
    domain = imp.get("domain")
    if not domain:
        return None

    members = sorted(
        (n.fqdn, n.content_hash)
        for n in builder._nodes.values()
        if (n.metadata or {}).get("import_role") == "governance"
    )
    h = hashlib.sha256()
    for fqdn, content_hash in members:
        h.update(fqdn.encode("utf-8"))
        h.update(b"\x00")
        h.update((content_hash or "").encode("utf-8"))
        h.update(b"\x00")
    return {
        "import_domain": domain,
        "governance_closure_hash": h.hexdigest(),
        "invariant_count": len(members),
    }


def _discover_artifacts(
    search_layers: list[str],
    discovery_layers: dict[str, Any],
    discovery_rules: dict[str, Any],
    build_artifact_types: list[str],
    errors: list[CompilerError],
) -> list[dict[str, Any]]:
    """Discover artifact files from declared layers."""
    all_discovered: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    artifact_pattern = re.compile(discovery_rules.get("filename_pattern", ""))
    excluded_dirs = discovery_rules.get("excluded_directories", [])

    for layer_code in search_layers:
        layer_config = discovery_layers.get(layer_code)
        if not layer_config:
            errors.append(CompilerError(
                code=ErrorCode.E901_INTERNAL_ERROR,
                message=f"Layer {layer_code} not found in STRUCTURE_DISCOVERY_V0",
                phase="S1_EXTRACT",
            ))
            continue

        if layer_code == "DOMAINS":
            allowed_domains = layer_config.get("allowed_domains", [])
            if not allowed_domains:
                errors.append(CompilerError(
                    code=ErrorCode.E901_INTERNAL_ERROR,
                    message="DOMAINS layer missing allowed_domains declaration",
                    phase="S1_EXTRACT",
                ))
                continue

            for domain_name in allowed_domains:
                _scan_layer(
                    layer_code, layer_config, artifact_pattern,
                    excluded_dirs, all_discovered, seen_paths,
                    errors, domain_name=domain_name,
                )
        else:
            _scan_layer(
                layer_code, layer_config, artifact_pattern,
                excluded_dirs, all_discovered, seen_paths,
                errors, domain_name=None,
            )

    # Apply scope filter
    filtered = [
        a for a in all_discovered
        if a["artifact_type"] in build_artifact_types
    ]

    return sorted(filtered, key=lambda x: (x["artifact_code"], x["source_path"]))


def _scan_layer(
    layer_code: str,
    layer_config: dict[str, Any],
    artifact_pattern: re.Pattern,
    excluded_dirs: list[str],
    artifacts: list[dict[str, Any]],
    seen_paths: set[Path],
    errors: list[CompilerError],
    domain_name: str | None = None,
) -> None:
    """Scan a layer's registry module recursively for artifact files."""
    registry_module = layer_config.get("registry_module", "")
    resolver = LayerResolver()

    if layer_code == "DOMAINS" and domain_name:
        root_path = resolver.resolve_layer_root(layer_code, domain=domain_name)
    else:
        root_path = resolver.resolve_layer_root(layer_code)

    if not root_path.exists():
        errors.append(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message=f"Layer {layer_code} registry path does not exist: {root_path}",
            phase="S1_EXTRACT",
        ))
        return

    for md_path in root_path.rglob("*.md"):
        if md_path.resolve() in seen_paths:
            continue
        seen_paths.add(md_path.resolve())

        if any(excl in md_path.parts for excl in excluded_dirs):
            continue

        match = artifact_pattern.match(md_path.name)
        if not match:
            continue

        artifact_type = match.group("type")
        artifact_name = match.group("name")
        version = match.group("version")
        artifact_code = f"{artifact_type}_{artifact_name}_V{version}"

        rel_path = md_path.parent.relative_to(root_path)
        if str(rel_path) == ".":
            full_module_path = registry_module
        else:
            full_module_path = f"{registry_module}.{str(rel_path).replace('/', '.')}"

        entry: dict[str, Any] = {
            "artifact_code": artifact_code,
            "artifact_type": artifact_type,
            "layer_code": layer_code,
            "module_path": full_module_path,
            "source_path": str(md_path),
            "version": version,
        }

        if domain_name:
            entry["domain_name"] = domain_name

        artifacts.append(entry)


def _read_declared_fqdn(source_path: str) -> str | None:
    """Extract the authoritative `fqdn` declared in an artifact's Machine block.

    Identity is declared by the artifact, not derived from its folder. Returns None if the
    file has no Machine block or no `fqdn` field (a hard error upstream).
    """
    try:
        content = Path(source_path).read_text(encoding="utf-8")
    except Exception:
        return None
    m = _MACHINE_BLOCK_PATTERN.search(content)
    if not m:
        return None
    try:
        block = yaml.safe_load(m.group("machine_yaml").rstrip())
    except yaml.YAMLError:
        return None
    if isinstance(block, dict):
        fq = block.get("fqdn")
        return fq if isinstance(fq, str) and "::" in fq else None
    return None


def _derive_fqdns(
    discovered: list[dict[str, Any]],
    identity_rules: list[dict[str, Any]],
    errors: list[CompilerError],
) -> None:
    """Resolve each artifact's identity from its DECLARED `fqdn`.

    The filesystem location has no semantic authority over identity (design: semantic alignment).
    The path-derived value is still computed and retained as `derived_fqdn` — a discovery default
    and the subject of the migration cross-check (INVARIANT_IDENTITY_MIGRATION_CROSSCHECK_V0) —
    but the authoritative `namespace`/`fqdn` come from the artifact's own declaration.
    """
    for artifact in discovered:
        module_path = artifact.get("module_path", "")
        layer_code = artifact.get("layer_code")
        domain_name = artifact.get("domain_name")

        # --- path-derived value (discovery default + cross-check target) ---
        if layer_code == "DOMAINS":
            derived_ns = f"domains.{domain_name}" if domain_name else None
        else:
            derived_ns = None
            for rule in identity_rules:
                if rule.get("match", "") in module_path:
                    template = rule.get("namespace_template")
                    derived_ns = template.format(module_path=module_path) if template else rule.get("namespace", "")
                    break
        derived_fqdn = f"{derived_ns}::{artifact['artifact_code']}" if derived_ns else None
        artifact["derived_namespace"] = derived_ns
        artifact["derived_fqdn"] = derived_fqdn

        # --- authoritative identity: the artifact's declared fqdn ---
        declared = _read_declared_fqdn(artifact.get("source_path", ""))
        if not declared:
            errors.append(CompilerError(
                code=ErrorCode.E104_INVALID_FQDN,
                message=(
                    f"Artifact declares no authoritative `fqdn` in its Machine block "
                    f"(artifact_code={artifact['artifact_code']}). Identity must be declared."
                ),
                phase="S1_EXTRACT",
            ))
            continue

        artifact["namespace"] = declared.split("::", 1)[0]
        artifact["fqdn"] = declared


def _inject_imported_capabilities(
    builder: GraphBuilder,
    all_refs: set[str],
    build_config: dict[str, Any],
    errors: list[CompilerError],
) -> None:
    """Lift imported platform capabilities (CS/CT) that this domain CONSUMES into the graph.

    Governance imports (constitutions, execution structure) are resolve-only — S2 tolerates and drops
    them. But a capability the domain *invokes* in a CC pipeline must be executable here: its compiled
    node is loaded from the imported domain's canonical snapshot (bringing its machine.implementation),
    added to this graph, and then addressed + wired + emitted like a native node. The capability's
    governance/authoring stays platform-owned; the consumer carries only its execution binding.
    """
    import json

    imp = (build_config.get("artifact_discovery", {}) or {}).get("import_surface", {}) or {}
    domain = imp.get("domain")
    if not domain:
        return

    from compiler.governance_engine.platform_root import platform_root
    canon_root = platform_root() / "snapshot" / "compiled" / "canonical"
    if not canon_root.is_dir():
        return

    # Carried capabilities emit under THIS domain's own layer (they become part of its runtime
    # substrate) — whatever that layer is; no domain is named here. metadata.imported marks origin.
    search_layers = (build_config.get("artifact_discovery", {}) or {}).get("search_layers", [])
    if not search_layers:
        return
    domain_layer = search_layers[0]

    for fqdn in sorted(all_refs):
        if "::" not in fqdn or fqdn in builder._nodes:
            continue
        namespace, artifact_code = fqdn.split("::", 1)
        if artifact_code.split("_")[0] not in ("CS", "CT"):
            continue  # only capabilities are carried; governance stays resolve-only (S2)
        matches = list(canon_root.rglob(fqdn.replace("::", "__") + ".json"))
        if not matches:
            continue  # not a compiled imported capability — leave to S2 tolerance
        raw = json.loads(matches[0].read_text(encoding="utf-8"))
        kind = _type_to_kind(raw.get("artifact_type"))
        if kind is None:
            continue
        m = re.search(r"_V(\d+)$", artifact_code)
        builder.add_node(Node.create(
            fqdn=fqdn,
            kind=kind,
            namespace=namespace,
            artifact_code=artifact_code,
            version=f"V{m.group(1)}" if m else "V0",
            layer_code=domain_layer,
            content_hash=raw.get("content_hash", ""),
            frontmatter=raw.get("frontmatter", {}),   # carries machine.implementation → cs_ir/ct_ir in S5
            domain_name=None,
            metadata={
                "imported": True,
                "import_role": "execution",   # linked into the domain runtime AND emitted
                "import_domain": domain,
                "module_path": raw.get("module_path", ""),
            },
        ))


# Artifact kinds a domain build instantiates. An imported invariant is domain-applicable
# iff its declared scope.applies_to intersects this set (design §2). The set is the single
# derivation point for domain-vs-platform applicability — never a declared build token.
_DOMAIN_INSTANTIATED = frozenset({"WF", "CC", "CS", "CT", "RB", "AC", "IN", "EV", "TI", "TE"})


def _inject_imported_governance(
    builder: GraphBuilder,
    build_config: dict[str, Any],
    errors: list[CompilerError],
) -> None:
    """Import platform governance as checked protocol state.

    Domain-applicable INVARIANT nodes are lifted from the imported platform snapshot into this
    domain's graph so S4 can assert them against the domain's own artifacts. Unlike capabilities
    (import_role="execution", linked + emitted), governance is import_role="governance": it acts on
    the domain graph and is dropped before materialize (canonical projection skips it) — it is the
    asserter, never a subject, and never part of the domain's artifact set.

    Applicability is derived, not declared: an invariant is imported iff its scope.applies_to
    intersects the domain-instantiated kinds. Platform-only invariants (COMPILER/INVARIANT/
    CONSTITUTION/SNAPSHOT/... scopes) have no domain subject and are never imported.
    """
    import json

    imp = (build_config.get("artifact_discovery", {}) or {}).get("import_surface", {}) or {}
    domain = imp.get("domain")
    if not domain:
        return  # platform build: no import_surface, no injection — must stay a no-op

    from compiler.governance_engine.platform_root import platform_root
    inv_root = platform_root() / "snapshot" / "compiled" / "canonical" / "invariants"
    if not inv_root.is_dir():
        return

    search_layers = (build_config.get("artifact_discovery", {}) or {}).get("search_layers", [])
    if not search_layers:
        return
    domain_layer = search_layers[0]

    for path in sorted(inv_root.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        fm = raw.get("frontmatter", {}) or {}
        proj = fm.get("assert_projection", {}) or {}
        kinds = proj.get("applies_to_kinds", []) or []
        if not (set(kinds) & _DOMAIN_INSTANTIATED):
            continue  # platform-only invariant — no domain subject
        # A layer/surface-scoped invariant governs a specific surface (its allowed-list is that
        # surface's); domains declare their own surface-closure, so it is not generically imported.
        if (proj.get("scope", {}) or {}).get("applies_to"):
            continue
        fqdn = raw.get("fqdn_id")
        if not fqdn or fqdn in builder._nodes:
            continue
        namespace, artifact_code = fqdn.split("::", 1)
        kind = _type_to_kind(raw.get("artifact_type"))
        if kind is None:
            continue
        m = re.search(r"_V(\d+)$", artifact_code)
        builder.add_node(Node.create(
            fqdn=fqdn,
            kind=kind,
            namespace=namespace,
            artifact_code=artifact_code,
            version=f"V{m.group(1)}" if m else "V0",
            layer_code=domain_layer,
            content_hash=raw.get("content_hash", ""),
            frontmatter=fm,                      # carries scope + assert_projection → derived ASSERT in S4
            domain_name=None,
            metadata={
                "imported": True,
                "import_role": "governance",     # asserts the domain graph; NOT emitted
                "import_domain": domain,
                "module_path": raw.get("module_path", ""),
            },
        ))


def _parse_artifact_to_node(
    artifact: dict[str, Any],
    artifact_registry: dict[str, list[str]],
) -> tuple[Node | None, list[str], list[CompilerError], list[CompilerError]]:
    """
    Parse a single artifact file into a Node + reference list.

    Returns:
        (node_or_None, reference_fqdns, errors, warnings)
    """
    errors: list[CompilerError] = []
    warnings: list[CompilerError] = []

    fqdn = artifact["fqdn"]
    artifact_code = artifact["artifact_code"]
    source_path = Path(artifact["source_path"])

    # Read source file
    try:
        content_raw = source_path.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message=f"Failed to read file: {e}",
            phase="S1_EXTRACT",
            fqdn_id=fqdn,
            artifact_code=artifact_code,
        ))
        return None, [], errors, warnings

    # Extract Machine block
    match = _MACHINE_BLOCK_PATTERN.search(content_raw)
    if not match:
        errors.append(CompilerError(
            code=ErrorCode.E101_INVALID_YAML,
            message="No ## Machine block found",
            phase="S1_EXTRACT",
            fqdn_id=fqdn,
            artifact_code=artifact_code,
        ))
        return None, [], errors, warnings

    try:
        frontmatter = yaml.safe_load(match.group("machine_yaml").rstrip())
    except yaml.YAMLError as e:
        errors.append(CompilerError(
            code=ErrorCode.E101_INVALID_YAML,
            message=f"YAML parse error in Machine block: {e}",
            phase="S1_EXTRACT",
            fqdn_id=fqdn,
            artifact_code=artifact_code,
        ))
        return None, [], errors, warnings

    if not isinstance(frontmatter, dict):
        errors.append(CompilerError(
            code=ErrorCode.E101_INVALID_YAML,
            message="Machine block YAML must be a dictionary",
            phase="S1_EXTRACT",
            fqdn_id=fqdn,
            artifact_code=artifact_code,
        ))
        return None, [], errors, warnings

    # Reject deprecated artifacts
    if frontmatter.get("status") == "deprecated":
        warnings.append(CompilerError(
            code=ErrorCode.E005_DEPRECATED_ARTIFACT,
            message=f"Skipping deprecated artifact: {artifact_code}",
            phase="S1_EXTRACT",
            fqdn_id=fqdn,
            artifact_code=artifact_code,
        ))
        return None, [], errors, warnings

    # Compute content hash
    content_hash = hashlib.sha256(content_raw.encode("utf-8")).hexdigest()

    # Determine node kind
    artifact_type = artifact["artifact_type"]
    kind = _type_to_kind(artifact_type)
    if kind is None:
        errors.append(CompilerError(
            code=ErrorCode.E901_INTERNAL_ERROR,
            message=f"Unknown artifact type: {artifact_type}",
            phase="S1_EXTRACT",
            fqdn_id=fqdn,
            artifact_code=artifact_code,
        ))
        return None, [], errors, warnings

    # Extract references
    references, ref_errors = _extract_references(
        frontmatter, fqdn, artifact_code, artifact_registry
    )
    errors.extend(ref_errors)

    # Create Node
    node = Node.create(
        fqdn=fqdn,
        kind=kind,
        namespace=artifact["namespace"],
        artifact_code=artifact_code,
        version=artifact["version"],
        layer_code=artifact["layer_code"],
        content_hash=content_hash,
        frontmatter=frontmatter,
        domain_name=artifact.get("domain_name"),
        metadata={
            "source_path": artifact["source_path"],
            "module_path": artifact.get("module_path", ""),
            "content": content_raw,
            "references": sorted(references),
            "derived_fqdn": artifact.get("derived_fqdn", ""),
        },
    )

    return node, references, errors, warnings


def _extract_references(
    frontmatter: dict[str, Any],
    source_fqdn: str,
    artifact_code: str,
    artifact_registry: dict[str, list[str]],
) -> tuple[list[str], list[CompilerError]]:
    """
    Extract FQDN references from artifact frontmatter.

    CONSTITUTIONAL: FQDN-only enforcement — bare codes are rejected.
    """
    references: set[str] = set()
    errors: list[CompilerError] = []

    def validate_ref(ref_value: str) -> str | None:
        if "::" not in ref_value:
            errors.append(CompilerError(
                code=ErrorCode.E104_INVALID_FQDN,
                message=f"Bare code forbidden: '{ref_value}'. Use FQDN (namespace::code)",
                phase="S1_EXTRACT",
                fqdn_id=source_fqdn,
                artifact_code=artifact_code,
            ))
            return None

        # Self-reference filter
        if ref_value == source_fqdn:
            return None

        return ref_value

    # Singular reference fields
    singular_fields = ["vocabulary_id", "governed_by", "structure", "runtime_binding", "transform"]
    # Plural reference fields
    plural_fields = ["transforms", "side_effects"]

    # RB bindings: keys are artifact FQDNs
    core = frontmatter.get("core", {})
    if isinstance(core, dict) and "bindings" in core:
        bindings = core["bindings"]
        if isinstance(bindings, dict):
            for binding_key in bindings.keys():
                resolved = validate_ref(binding_key)
                if resolved:
                    references.add(resolved)

    def scan_recursive(data: Any) -> None:
        if isinstance(data, dict):
            for k, v in data.items():
                if k in singular_fields:
                    # A singular reference field is usually a scalar FQDN, but `governed_by` (and
                    # potentially others) may be authored as a list of FQDNs. Both must become
                    # REFERENCES edges — otherwise a list-valued governed_by is silently dropped and
                    # its GOVERNED_BY edge never emitted (CSI Finding #001).
                    for item in ([v] if isinstance(v, str) else (v if isinstance(v, list) else [])):
                        if isinstance(item, str):
                            resolved = validate_ref(item)
                            if resolved:
                                references.add(resolved)
                elif k in plural_fields and isinstance(v, list):
                    for item in v:
                        if isinstance(item, str):
                            resolved = validate_ref(item)
                            if resolved:
                                references.add(resolved)
                else:
                    scan_recursive(v)
        elif isinstance(data, list):
            for item in data:
                scan_recursive(item)

    scan_recursive(frontmatter)

    return sorted(references), errors
