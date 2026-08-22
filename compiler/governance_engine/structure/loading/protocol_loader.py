import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from compiler.governance_engine.structure.resolution.domain_resolver import extract_domain_from_artifact_path
from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver

# ============================================================================
# PROTOCOL LOADER
# ============================================================================
# Core loader for all protocol artifacts.
# All resolution is driven by a STRUCTURE artifact.
# ============================================================================


class ProtocolLoader:
    """
    Loads protocol artifacts (workflows, intents, capability contracts)
    based on a given set of search roots.
    """

    def __init__(self, search_roots: List[Path]):
        self.search_roots = search_roots
        self.layer_resolver = LayerResolver()

    def load(self, workflow_code: str) -> Dict[str, Any]:
        """
        Loads a workflow and its associated intents, capability contracts, and CT-IR.
        """
        # Load workflow artifact
        wf_artifact, wf_source_path = resolve_artifact_with_path(workflow_code, self.search_roots)

        # Extract domain from source path
        domain = extract_domain_from_artifact_path(wf_source_path)

        # Extract workflow namespace for FQDN construction
        # PROTOCOL: Compiled artifacts have namespace at top-level (compiler metadata)
        workflow_namespace = wf_artifact.get("namespace")

        # Load intents and capability contracts referenced by the workflow
        intent_specs = {}
        capability_contracts = {}

        # PROTOCOL: Extract dependencies from workflow nodes (canonical format)
        # Compiled workflows have nodes in frontmatter.core.nodes
        frontmatter = wf_artifact.get('frontmatter', {})
        core = frontmatter.get('core', {})
        nodes = core.get('nodes', {})

        for node_id, node_spec in nodes.items():
            node_type = node_spec.get('type')
            node_code = node_spec.get('code')

            if not node_code:
                continue

            try:
                # PROTOCOL: Domain artifacts use FQDN format (namespace::CODE)
                # Check if code already has namespace
                if "::" in node_code:
                    artifact_fqdn = node_code
                else:
                    # Domain artifact: prefix with workflow namespace
                    artifact_fqdn = (
                        f"{workflow_namespace}::{node_code}"
                        if workflow_namespace
                        else node_code
                    )

                if node_type == 'IN':
                    # Load intent artifact
                    intent_artifact = resolve_artifact(artifact_fqdn, self.search_roots)
                    # Store with short code as key (for workflow_runner lookup)
                    intent_specs[node_code] = intent_artifact
                elif node_type == 'CC':
                    # Load capability contract artifact
                    cc_artifact = resolve_artifact(artifact_fqdn, self.search_roots)
                    # Store with short code as key (for capability_pipeline lookup)
                    capability_contracts[node_code] = cc_artifact
            except Exception:
                # Skip unknown/missing dependencies - will fail at runtime (correct behavior)
                continue

        # Load CT-IR artifacts referenced by CC pipelines
        # PROTOCOL: ct_ir_registry must be provided by compiler (pre-validated CT-IR)
        ct_ir_registry = {}
        for cc_code, cc_artifact in capability_contracts.items():
            # PROTOCOL: Compiled artifacts have core in frontmatter
            frontmatter = cc_artifact.get("frontmatter", {})
            core = frontmatter.get("core", {})
            pipeline = core.get("pipeline", [])

            # Scan pipeline for CT references
            for step in pipeline:
                if isinstance(step, dict):
                    artifact_code = step.get("transform")
                    if artifact_code and artifact_code not in ct_ir_registry:
                        try:
                            # PROTOCOL SOVEREIGNTY: Transform codes MUST be FQDN (namespace::CODE)
                            # No inference, no defaulting, no prefixing allowed
                            if "::" not in artifact_code:
                                raise ValueError(
                                    f"Transform code must be FQDN (namespace::CODE), got bare code: {artifact_code}. "
                                    f"Update artifact to use FQDN (e.g., 'capability_transforms::{artifact_code}' or 'domains.blockchain::{artifact_code}')"
                                )

                            ct_artifact = resolve_artifact(artifact_code, self.search_roots)
                            # Store CT-IR section only (not entire artifact)
                            ct_ir = ct_artifact.get("ct_ir")
                            if ct_ir:
                                # Store by FQDN (artifact_code is already FQDN)
                                ct_ir_registry[artifact_code] = ct_ir
                            else:
                                # CT artifact missing ct_ir - fail hard
                                raise ValueError(
                                    f"CT artifact {artifact_code} missing ct_ir section. "
                                    f"Compiler must generate ct_ir for all CT artifacts."
                                )
                        except FileNotFoundError:
                            # CT artifact not found - will fail at runtime (correct behavior)
                            pass

        return {
            "workflow_spec": wf_artifact,
            "intent_specs": intent_specs,
            "capability_contracts": capability_contracts,
            "ct_ir_registry": ct_ir_registry,
            "domain": domain,
        }


def load_bootstrap_artifact(artifact_code: str) -> Dict[str, Any]:
    """
    Loads a bootstrap artifact using LayerResolver and FQDN resolution.

    PROTOCOL: Zero inference - all behavior declared explicitly.
    Full FQDN format is required: "namespace::ARTIFACT_CODE_V0"
    Examples:
      - "execution::STRUCTURE_RUNTIME_EXECUTION_V0"
      - "domains.blockchain::WF_CREATE_WALLET_V0"
      - "capability_transforms::CT_HASH_DATA_V0"

    Args:
        artifact_code: Artifact FQDN (namespace::CODE format, no short codes)

    Returns:
        Loaded artifact dictionary

    Raises:
        FileNotFoundError: Artifact not found at expected path
        ValueError: Unsupported namespace (not in declared mapping)

    Governed By:
        INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0
        CONSTITUTION_STRUCTURE_V0
    """
    resolver = LayerResolver()

    # Parse FQDN format (namespace::CODE) or infer platform namespace
    if "::" in artifact_code:
        # FQDN format: namespace::CODE
        namespace, code = artifact_code.split("::", 1)
    else:
        raise ValueError(
            f"PROTOCOL VIOLATION: Bootstrap artifact must use FQDN format.\n"
            f"Expected: 'namespace::ARTIFACT_CODE', got: '{artifact_code}'\n"
            f"Examples:\n"
            f"  - execution::STRUCTURE_RUNTIME_EXECUTION_V0\n"
            f"  - domains.blockchain::WF_CREATE_WALLET_V0\n"
            f"  - capability_transforms::CT_HASH_DATA_V0"
        )

    # PROTOCOL: Declared namespace → layer mapping (no inference)
    # This mapping is constitutional - defines which layer owns which namespace.
    # All fb.* namespaces are federation-boundary governance artifacts compiled to structures/.
    # Every federation-boundary namespace resolves identically, so the rule is stated once
    # rather than enumerated — adding a namespace requires no edit here.
    FB_LAYER = ("GOVERNANCE", "compiled/artifacts/structures")
    NAMESPACE_LAYER_MAPPING = {
        # Reusable capability namespaces (instance declarations, not governance)
        "capability_transforms": ("REUSABLE_TRANSFORMS", "compiled/artifacts/capability_transforms"),
        "capability_side_effects": ("REUSABLE_SIDE_EFFECTS", "compiled/artifacts/capability_side_effects"),
    }

    # Check for domain namespace pattern: domains.{domain_name}
    if namespace.startswith("domains."):
        # Extract domain name from namespace
        domain_parts = namespace.split(".")
        if len(domain_parts) != 2:
            raise ValueError(
                f"PROTOCOL VIOLATION: Invalid domain namespace format: '{namespace}'\n"
                f"Expected: 'domains.{{domain_name}}', e.g., 'domains.blockchain'"
            )

        domain_name = domain_parts[1]

        # Resolve DOMAINS layer with domain isolation
        try:
            domains_repo_root = resolver.resolve_layer_repo_root("DOMAINS")
        except Exception as e:
            raise RuntimeError(f"Failed to resolve DOMAINS layer root for bootstrap: {e}")

        # Construct domain-specific path
        # Pattern: domains/{domain}/compiled/artifacts/{artifact_type}/{fqdn_filename}
        artifact_type_dir = _get_artifact_type_dir(code)
        fqdn_filename = f"{namespace}_{code}.json"
        artifact_path = (
            domains_repo_root / "domains" / domain_name /
            "compiled" / "artifacts" / artifact_type_dir / fqdn_filename
        )

    elif namespace.startswith("fb.") or namespace in NAMESPACE_LAYER_MAPPING:
        # Platform namespace: use declared mapping
        layer_code, subpath = (
            FB_LAYER if namespace.startswith("fb.") else NAMESPACE_LAYER_MAPPING[namespace]
        )

        # For platform builds, compiled artifacts are centralized at protocol root
        # (not in layer repo root) per STRUCTURE_BUILD_PLATFORM_CONFIG_V0
        protocol_root = resolver._project_root

        # Construct artifact path
        fqdn_filename = f"{namespace}_{code}.json"
        artifact_path = protocol_root / subpath / fqdn_filename

    else:
        raise ValueError(
            f"PROTOCOL VIOLATION: Unsupported namespace: '{namespace}'\n"
            f"Supported platform namespaces: any 'fb.*' federation boundary, plus "
            f"{list(NAMESPACE_LAYER_MAPPING.keys())}\n"
            f"Supported domain namespaces: domains.{{domain_name}}"
        )

    # Load artifact
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"PROTOCOL VIOLATION: Bootstrap artifact not found.\n"
            f"Expected FQDN path: {artifact_path}\n"
            f"Artifact code: {artifact_code}\n"
            f"Namespace: {namespace}\n"
            f"Code: {code}"
        )

    with open(artifact_path, 'r') as f:
        return json.load(f)


def resolve_artifact(artifact_code: str, search_roots: List[Path]) -> Dict[str, Any]:
    """
    Resolves and loads a protocol artifact (e.g., WF, CC, IN, RB) from search roots.
    Strict protocol resolution: filename must match the FQDN (with :: replaced by _).

    Protocol: search_roots can be either:
    1. Layer roots (e.g., /pgs_governance) - resolution adds /compiled/artifacts/{type}/
    2. Complete artifact paths (e.g., /pgs_domains/domains/blockchain/compiled/artifacts/workflows) - resolution uses directly

    Detection rule (declared, not heuristic):
    - If root ends with artifact type directory name → use directly
    - Otherwise → add /compiled/artifacts/{type}/
    """
    artifact_type_dir = _get_artifact_type_dir(artifact_code)
    filename = artifact_code.replace('::', '_') + ".json"

    for root in search_roots:
        # Check if root already points to artifact type directory
        if root.name == artifact_type_dir:
            # Complete path provided - use directly
            potential_path = root / filename
        else:
            # Layer root provided - add subdirectories
            potential_path = root / "compiled" / "artifacts" / artifact_type_dir / filename

        if potential_path.exists():
            with open(potential_path, 'r') as f:
                artifact = json.load(f)

                # PROTOCOL ENFORCEMENT: All compiled artifacts MUST declare namespace
                # This catches artifacts that weren't properly compiled
                if "namespace" not in artifact:
                    raise ValueError(
                        f"PROTOCOL VIOLATION: Artifact {artifact_code} missing 'namespace' field.\n"
                        f"All compiled artifacts must declare namespace.\n"
                        f"Source: {potential_path}"
                    )

                return artifact

    searched = "\n  ".join(str(root) for root in search_roots)
    raise FileNotFoundError(
        f"Artifact not found: {artifact_code}\n"
        f"Expected path: {filename} in {artifact_type_dir}\n"
        f"Searched roots:\n  {searched}"
    )


def resolve_artifact_with_path(artifact_code: str, search_roots: List[Path]) -> Tuple[Dict[str, Any], Path]:
    """
    Resolves and loads a protocol artifact, returning both the artifact and its source path.
    Strict protocol resolution: filename must match the FQDN (with :: replaced by _).

    Protocol: search_roots can be either:
    1. Layer roots (e.g., /pgs_governance) - resolution adds /compiled/artifacts/{type}/
    2. Complete artifact paths (e.g., /pgs_domains/domains/blockchain/compiled/artifacts/workflows) - resolution uses directly

    Detection rule (declared, not heuristic):
    - If root ends with artifact type directory name → use directly
    - Otherwise → add /compiled/artifacts/{type}/
    """
    artifact_type_dir = _get_artifact_type_dir(artifact_code)
    filename = artifact_code.replace('::', '_') + ".json"

    for root in search_roots:
        # Check if root already points to artifact type directory
        if root.name == artifact_type_dir:
            # Complete path provided - use directly
            potential_path = root / filename
        else:
            # Layer root provided - add subdirectories
            potential_path = root / "compiled" / "artifacts" / artifact_type_dir / filename

        if potential_path.exists():
            with open(potential_path, 'r') as f:
                artifact = json.load(f)

                # PROTOCOL ENFORCEMENT: All compiled artifacts MUST declare namespace
                # This catches artifacts that weren't properly compiled
                if "namespace" not in artifact:
                    raise ValueError(
                        f"PROTOCOL VIOLATION: Artifact {artifact_code} missing 'namespace' field.\n"
                        f"All compiled artifacts must declare namespace.\n"
                        f"Source: {potential_path}"
                    )

                return artifact, potential_path

    searched = "\n  ".join(str(root) for root in search_roots)
    raise FileNotFoundError(
        f"Artifact not found: {artifact_code}\n"
        f"Expected path: {filename} in {artifact_type_dir}\n"
        f"Searched roots:\n  {searched}"
    )


def resolve_search_roots(structure_artifact: Dict[str, Any]) -> List[Path]:
    """
    Resolves the absolute paths for search roots defined in a STRUCTURE artifact.

    Protocol: Two schemas are supported (declared, never inferred):
    1. Explicit format: structure_artifact['artifact_discovery']['search_roots'] - list of {layer, subpath, artifact_type}
    2. Simple format: structure_artifact['artifact_discovery']['search_layers'] - list of layer names (expanded to roots)
    """
    # 1. Extract config from artifact_discovery (Protocol Truth for STRUCTURE)
    discovery = structure_artifact.get('artifact_discovery', {})

    # Fallback to 'frontmatter' if top-level missing (transitional for compiled artifacts)
    if not discovery:
        discovery = structure_artifact.get('frontmatter', {}).get('artifact_discovery', {})

    # Try explicit search_roots format first
    search_roots_config = discovery.get('search_roots', [])

    # If not found, try simple search_layers format
    if not search_roots_config:
        search_layers = discovery.get('search_layers', [])
        if search_layers:
            # Expand search_layers to search_roots format
            # Each layer gets expanded to: layer_root/registry and layer_root/compiled/artifacts
            search_roots_config = _expand_search_layers(search_layers)

    # Check for domain_discovery configuration (PROTOCOL: dynamic domain expansion)
    domain_discovery = discovery.get('domain_discovery', {})
    if domain_discovery and domain_discovery.get('enabled', False):
        # Expand domain_discovery into search_roots dynamically
        domain_roots = _expand_domain_discovery(domain_discovery)
        search_roots_config.extend(domain_roots)

    if not search_roots_config:
        artifact_code = structure_artifact.get('artifact_code') or structure_artifact.get('frontmatter', {}).get('structure_code')
        raise ValueError(
            f"STRUCTURE artifact {artifact_code} missing 'search_roots' or 'search_layers'. "
            "Must be declared in 'artifact_discovery' block."
        )

    resolved_roots = []
    resolver = LayerResolver()

    for root_config in search_roots_config:
        layer_code = root_config.get('layer')
        subpath = root_config.get('subpath', '')
        artifact_type = root_config.get('artifact_type')
        
        if not layer_code:
            continue # Protocol: Ignore invalid entries
        
        # 2. Resolve layer repository root (Constitutional)
        try:
            # We use resolve_layer_repo_root for discovery/bootstrap phase (Patch 7)
            repo_root = resolver.resolve_layer_repo_root(layer_code)
        except Exception:
            # Protocol: Ignore missing optional layers
            continue

        # 3. Construct absolute path
        # Convention: repo_root / [artifact_type] / subpath
        if artifact_type:
             resolved_path = repo_root / artifact_type / subpath
        else:
             resolved_path = repo_root / subpath
             
        if resolved_path.is_dir():
            resolved_roots.append(resolved_path.resolve())

    return resolved_roots


def _expand_search_layers(search_layers: List[str]) -> List[Dict[str, Any]]:
    """
    Expands simple search_layers format to explicit search_roots format.

    Protocol expansion rule (declared, not inferred):
    - Runtime resolution only needs compiled artifacts
    - Each layer expands to ONE root: {layer: LAYER, subpath: "artifacts", artifact_type: "compiled"}
    - Resolves to: layer_root/compiled/artifacts

    Args:
        search_layers: List of layer codes (e.g., ["GOVERNANCE", "REUSABLE_TRANSFORMS"])

    Returns:
        List of search_root configs in {layer, subpath, artifact_type} format
    """
    search_roots = []
    for layer_code in search_layers:
        # Compiled artifacts only (runtime resolution)
        search_roots.append({
            'layer': layer_code,
            'subpath': 'artifacts',
            'artifact_type': 'compiled'
        })
    return search_roots


def _expand_domain_discovery(domain_discovery: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expands domain_discovery configuration into explicit search_roots.

    PROTOCOL: Dynamic domain discovery eliminates hardcoded domain paths.
    Discovers domains at runtime and expands registry/compiled subdirectories.

    Args:
        domain_discovery: {
            'enabled': bool,
            'layer': str (e.g., 'DOMAINS'),
            'search_pattern': str (e.g., 'domains/*/'),
            'allowed_domains': list[str],
            'registry_subdirs': list[str],
            'compiled_subdirs': list[str],
            'discover_subregistries': bool,
            'subregistry_pattern': str (optional)
        }

    Returns:
        List of search_root configs dynamically expanded from discovered domains

    Example:
        Input: {
            'layer': 'DOMAINS',
            'allowed_domains': ['blockchain'],
            'registry_subdirs': ['workflows', 'intents'],
            'compiled_subdirs': ['workflows', 'intents']
        }

        Output: [
            {'layer': 'DOMAINS', 'subpath': 'domains/blockchain/registry/workflows'},
            {'layer': 'DOMAINS', 'subpath': 'domains/blockchain/registry/intents'},
            {'layer': 'DOMAINS', 'subpath': 'domains/blockchain/compiled/artifacts/workflows'},
            {'layer': 'DOMAINS', 'subpath': 'domains/blockchain/compiled/artifacts/intents'},
            # Plus any discovered subregistries (identity/, wallet/, etc.)
        ]
    """
    from pathlib import Path
    import os

    search_roots = []

    # Extract configuration
    layer_code = domain_discovery.get('layer', 'DOMAINS')
    allowed_domains = domain_discovery.get('allowed_domains', [])
    registry_subdirs = domain_discovery.get('registry_subdirs', [])
    compiled_subdirs = domain_discovery.get('compiled_subdirs', [])
    discover_subregistries = domain_discovery.get('discover_subregistries', False)

    # PROTOCOL: No domains declared → no expansion (explicit whitelist required)
    if not allowed_domains:
        return search_roots

    # Resolve DOMAINS layer repo root
    resolver = LayerResolver()
    try:
        domains_repo_root = resolver.resolve_layer_repo_root(layer_code)
    except Exception:
        # Layer not available → skip domain discovery
        return search_roots

    # For each allowed domain, expand paths
    for domain in allowed_domains:
        domain_base = f"domains/{domain}"

        # 1. Registry subdirectories (source artifacts)
        for subdir in registry_subdirs:
            search_roots.append({
                'layer': layer_code,
                'subpath': f"{domain_base}/registry/{subdir}"
            })

        # 2. Compiled artifact subdirectories
        for subdir in compiled_subdirs:
            search_roots.append({
                'layer': layer_code,
                'subpath': f"{domain_base}/compiled/artifacts/{subdir}"
            })

        # 3. Discover subregistries (e.g., blockchain/registry/identity/)
        if discover_subregistries:
            registry_path = domains_repo_root / domain_base / "registry"
            if registry_path.exists() and registry_path.is_dir():
                # Find subdirectories that are subregistries
                for item in registry_path.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        subreg_name = item.name
                        # Add subregistry paths for each artifact type
                        for subdir in registry_subdirs:
                            subreg_path = f"{domain_base}/registry/{subreg_name}/{subdir}"
                            search_roots.append({
                                'layer': layer_code,
                                'subpath': subreg_path
                            })

    return search_roots


def _get_artifact_type_dir(artifact_code: str) -> str:
    """
    Map artifact code prefix to directory name.
    Handles FQDNs strictly (namespace::CODE_V0).
    """
    # STRICT FQDN handling: namespace::CODE_V0
    if "::" in artifact_code:
        parts = artifact_code.split("::")
        # Protocol enforcement: FQDN must have exactly two parts
        assert len(parts) == 2, f"Invalid FQDN format: {artifact_code}. Expected 'namespace::artifact_code'."
        _, code = parts
    else:
        code = artifact_code

    # Protocol enforcement: artifact_code must contain an underscore for prefix extraction
    assert "_" in code, f"Invalid artifact_code format: {code}. Expected format like 'PREFIX_NAME_V0'."

    # Extract prefix (e.g., WF, RB) from the base artifact code
    prefix = code.split("_")[0]
    return _get_artifact_type_dir_from_prefix(prefix)


def _get_artifact_type_dir_from_prefix(prefix: str) -> str:
    """
    Map artifact type prefix to directory name.

    Args:
        prefix: Artifact type prefix (e.g., "WF", "CC", "IN", "TI")

    Returns:
        Directory name (e.g., "workflows", "capability_contracts", "intents")
    """
    # Single source of truth: the ArtifactKindRegistry (replaces the legacy hardcoded type_map).
    from compiler.governance_engine.artifact_kinds import REGISTRY
    return REGISTRY.directory(prefix)


# ============================================================================
# BOOTSTRAP LOADING (TRANSITIONAL)
# ============================================================================
# EXCEPTION: Bootstrap artifacts (STRUCTURE, WF, RB) need minimal hardcoded path
# to make the system self-describing. After bootstrap, ALL resolution uses STRUCTURE.
#
# This is the ONLY place where hardcoded paths are allowed.
# TRANSITIONAL: Long-term, STRUCTURE will bootstrap itself.
# ============================================================================
