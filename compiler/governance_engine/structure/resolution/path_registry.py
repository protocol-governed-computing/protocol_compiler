"""
Canonical path registry: Single source of truth for ALL filesystem paths.

Usage:
    from compiler.governance_engine.structure.resolution import bootstrap, paths

    bootstrap(root=Path("/path/to/project"))
    wf = paths.protocol.artifact("workflows", "wf_create_wallet_v0.json")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver, get_default_resolver

# =============================================================================
# Internal State
# =============================================================================

_PROJECT_ROOT: Path | None = None
_FQDN_TREE: dict | None = None
_BOOTSTRAPPED: bool = False
_LAYER_RESOLVER: LayerResolver | None = None
_MODULE_DATA_ROOTS: dict[str, str] | None = None
_LAYER_DIRECTORIES: dict[str, str] | None = None
_DIRECTORY_LIFECYCLE: dict[str, str] | None = None
_MODULE_DATA_ROOTS_LIFECYCLE: dict[str, str] | None = None


# =============================================================================
# Bootstrap
# =============================================================================

def _set_project_root(root: Path) -> None:
    """Set project root from explicit CLI parameter (STRUCTURE sovereignty)."""
    global _PROJECT_ROOT
    _PROJECT_ROOT = root


def _get_project_root() -> Path:
    """Get project root (must be set via bootstrap)."""
    if _PROJECT_ROOT is None:
        raise RuntimeError("Project root not set. Call bootstrap(root=...) first.")
    return _PROJECT_ROOT


def _parse_yaml_block(content: str, artifact_name: str = "artifact") -> dict:
    """
    Parse YAML block from markdown artifact.
    Extracts content between ```yaml and ```.
    """
    import re
    import yaml

    # Extract YAML block between ```yaml and ```
    match = re.search(r'```yaml\s*\n(.*?)```', content, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML block found in {artifact_name}")

    return yaml.safe_load(match.group(1))


def _parse_fqdn_yaml_block(content: str) -> dict:
    """
    Minimal inline parser for FQDN tree YAML block.
    Avoids import cycle with pgs_tooling.builder.structure_tree.
    """
    return _parse_yaml_block(content, "FQDN tree")


def bootstrap(root: Path | None = None, governance_layers_dir: Path | None = None) -> Path:
    """
    Initialize path registry from explicit root. Idempotent.

    STRUCTURE Sovereignty (pure architecture):
    - Root provided by CLI entrypoint (no discovery, no __file__, no importlib)
    - Governance location explicitly provided (no hardcoded paths)
    - All paths resolved from STRUCTURE artifacts

    Args:
        root: Explicit project root
              If None, uses Path.cwd()
        governance_layers_dir: Explicit registry structures directory
              If None, defaults to root/pgs_governance/registry/structures

    Returns:
        Project root Path

    Raises:
        FileNotFoundError: If STRUCTURE artifacts not found
        RuntimeError: If schemas/ not found or validation fails
    """
    global _BOOTSTRAPPED, _FQDN_TREE, _LAYER_RESOLVER
    global _MODULE_DATA_ROOTS, _LAYER_DIRECTORIES
    global _DIRECTORY_LIFECYCLE, _MODULE_DATA_ROOTS_LIFECYCLE

    if _BOOTSTRAPPED:
        return _get_project_root()

    if root is None:
        from compiler.governance_engine.platform_root import platform_root
        root = platform_root()
    _set_project_root(root)

    # Resolve registry root (<platform>/registry/)
    if governance_layers_dir is None:
        from compiler.governance_engine.platform_root import governance_registry_root
        governance_layers_dir = governance_registry_root() / "FB_CONSTITUTION" / "structures"

    if not governance_layers_dir.exists():
        raise FileNotFoundError(
            f"Governance structures directory not found: {governance_layers_dir}\n"
            f"STRUCTURE sovereignty requires explicit registry location."
        )

    # governance_root is always pgs_governance/registry/ (parent of FB_CONSTITUTION)
    governance_root = governance_layers_dir.parent.parent
    _set_governance_root(governance_root)

    def find_governance_artifact(artifact_code: str, subpath: str) -> Path:
        """Find artifact at known location (no discovery)."""
        artifact_path = governance_root / subpath / f"{artifact_code}.md"
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"STRUCTURE artifact {artifact_code} not found.\n"
                f"Expected: {artifact_path}\n"
                f"STRUCTURE sovereignty: all artifacts must exist at declared locations."
            )
        return artifact_path

    # Load FQDN tree
    fqdn_path = find_governance_artifact("STRUCTURE_FQDN_TREE_V0", "FB_CONSTITUTION/structures")
    _FQDN_TREE = _parse_fqdn_yaml_block(fqdn_path.read_text())

    # Load module data roots and layer directories
    data_roots_path = find_governance_artifact("STRUCTURE_MODULE_DATA_ROOTS_V0", "FB_CONSTITUTION/structures")
    structure_data = _parse_yaml_block(
        data_roots_path.read_text(),
        "STRUCTURE_MODULE_DATA_ROOTS_V0"
    )
    _LAYER_DIRECTORIES = structure_data.get("layer_directories", {})
    _MODULE_DATA_ROOTS = structure_data.get("module_data_roots", {})
    _DIRECTORY_LIFECYCLE = structure_data.get("directory_lifecycle", {})
    _MODULE_DATA_ROOTS_LIFECYCLE = structure_data.get("module_data_roots_lifecycle", {})

    # Initialize layer resolver
    _LAYER_RESOLVER = get_default_resolver(project_root=root)

    _BOOTSTRAPPED = True

    # Validate schemas exist (STRUCTURE-driven path).
    # PGC: schemas live under the platform root directly (root/registry/...), not under a
    # pgs_governance package subdir. schemas_subdir already includes the "registry/" prefix.
    schemas_subdir = _get_layer_directory("schemas_subdir", "registry/FB_CONSTITUTION/schemas")
    schemas = root / schemas_subdir
    if not schemas.exists():
        raise RuntimeError(
            f"Platform registry must define schemas at declared location.\n"
            f"Expected: {schemas}\n"
            f"Declared in: STRUCTURE_MODULE_DATA_ROOTS_V0 (schemas_subdir)"
        )

    # Validate structure layout
    validate_structure_layout()

    return root


def validate_structure_layout() -> None:
    """
    Validate that declared directory structure exists on filesystem.

    Validates human-managed directories only (compiler/runtime-managed are created on-demand).
    """
    if _MODULE_DATA_ROOTS and _MODULE_DATA_ROOTS_LIFECYCLE:
        root = _get_project_root()
        for module_name, data_root in _MODULE_DATA_ROOTS.items():
            lifecycle = _MODULE_DATA_ROOTS_LIFECYCLE.get(module_name, "human")
            if lifecycle != "human":
                continue

            root_path = root / data_root
            if not root_path.exists():
                raise ValueError(
                    f"STRUCTURE_LAYOUT_VIOLATION: Module '{module_name}' "
                    f"declares data_root '{data_root}' but directory does not exist: {root_path}\n"
                    f"Expected: {root_path}\n"
                    f"Declared in: STRUCTURE_MODULE_DATA_ROOTS_V0.md\n"
                    f"Lifecycle: {lifecycle} (human-managed, must exist before runtime)\n"
                    f"Action: Create the directory or update the registry artifact."
                )


def _require_bootstrap() -> None:
    if not _BOOTSTRAPPED:
        raise RuntimeError("Path registry not initialized. Call bootstrap() from an entry point.")


def _fqdn_tree() -> dict:
    _require_bootstrap()
    return _FQDN_TREE  # type: ignore


def _layer_resolver() -> LayerResolver:
    """Get layer resolver instance."""
    _require_bootstrap()
    return _LAYER_RESOLVER  # type: ignore


def _module_data_roots() -> dict[str, str]:
    """Get module data roots from STRUCTURE artifact."""
    _require_bootstrap()
    return _MODULE_DATA_ROOTS  # type: ignore


def _get_package_physical_root(package_name: str) -> str:
    """Get physical_root for a package from FQDN tree."""
    tree = _fqdn_tree()
    for pkg in tree.get("packages", []):
        if pkg.get("package") == package_name:
            return pkg.get("physical_root", ".")
    raise ValueError(f"Package '{package_name}' not found in FQDN tree")


def _get_package_info(package_name: str) -> dict:
    """Get full package definition from FQDN tree."""
    tree = _fqdn_tree()
    for pkg in tree.get("packages", []):
        if pkg.get("package") == package_name:
            return pkg
    raise ValueError(f"Package '{package_name}' not found in FQDN tree")


def _get_package_registries(package_name: str) -> list[dict]:
    """Get registry definitions for a package."""
    pkg = _get_package_info(package_name)
    return pkg.get("registries", [])


def _get_registry_path(package_name: str, artifact_type: str) -> Path:
    """
    Find registry path for artifact type in package.

    Queries FQDN tree to find which registry contains the artifact type.
    Returns absolute Path resolved from package physical_root + registry path.

    Registry paths in FQDN tree are relative to package physical_root.
    Resolution: {workspace}/{physical_root}/{registry_path}
    """
    pkg = _get_package_info(package_name)
    registries = pkg.get("registries", [])

    for reg in registries:
        if artifact_type in reg.get("artifact_types", []):
            # Get package physical root
            physical_root = pkg.get("physical_root", ".")
            clean_root = physical_root.lstrip("./")

            # Registry path is relative to physical_root
            registry_path = reg["path"]

            # Resolve absolute path
            workspace = _get_project_root()
            return workspace / clean_root / registry_path

    raise ValueError(
        f"No registry found for artifact_type '{artifact_type}' "
        f"in package '{package_name}'"
    )


def _get_first_registry_path(package_name: str) -> Path:
    """
    Get first registry path for a package.

    Used when package has multiple registries and we need the base registry location.
    Returns absolute Path resolved from package physical_root + first registry path.
    """
    pkg = _get_package_info(package_name)
    registries = pkg.get("registries", [])

    if not registries:
        raise ValueError(f"Package '{package_name}' has no registries")

    # Get package physical root
    physical_root = pkg.get("physical_root", ".")
    clean_root = physical_root.lstrip("./")

    # Get first registry path
    registry_path = registries[0]["path"]

    # Resolve absolute path
    workspace = _find_project_root_via_structure()
    return workspace / clean_root / registry_path


def _get_layer_directory(dir_key: str, default: str = "") -> str:
    """
    Get directory name from MODULE_DATA_ROOTS layer_directories.

    Args:
        dir_key: Key in layer_directories (e.g., "compiled_root", "vocabulary_subdir")
        default: Fallback value if key not found

    Returns:
        Directory name or path (e.g., "compiled", "vocabulary/reserved")
    """
    _require_bootstrap()
    if _LAYER_DIRECTORIES is None:
        return default
    return _LAYER_DIRECTORIES.get(dir_key, default)


# =============================================================================
# Platform Governance Authority Resolution
# =============================================================================


_GOVERNANCE_ROOT: Path | None = None


def _set_governance_root(gov_root: Path) -> None:
    """Set registry root from bootstrap."""
    global _GOVERNANCE_ROOT
    _GOVERNANCE_ROOT = gov_root


def _resolve_platform_governance_root() -> Path:
    """
    Resolve platform registry root (set during bootstrap).

    Returns:
        Path to registry module root
    """
    if _GOVERNANCE_ROOT is None:
        raise RuntimeError("Governance root not set. Call bootstrap() first.")
    return _GOVERNANCE_ROOT


# =============================================================================
# Concern Roots
# =============================================================================

class ConcernRoots:
    """Canonical roots for package architecture."""

    @property
    def project(self) -> Path:
        """Project root (set via bootstrap)."""
        return _get_project_root()

    def _package_root(self, package_name: str) -> Path:
        """
        Get package root from FQDN tree declarations.

        STRUCTURE-driven: No dynamic discovery, uses declared physical_root.
        """
        try:
            physical_root = _get_package_physical_root(package_name)
            clean_root = physical_root.lstrip("./")
            if not clean_root:
                return self.project
            return self.project / clean_root
        except ValueError:
            return self.project / package_name

    @property
    def common(self) -> Path:
        """Structure layer root."""
        return self.project / "pgs_structure" / "structure"

    @property
    def protocol(self) -> Path:
        """Protocol artifacts root (compiled artifacts)."""
        compiled_root = _LAYER_DIRECTORIES.get("compiled_root", "compiled")  # type: ignore
        governance_root = _resolve_platform_governance_root()
        return governance_root.parent / compiled_root

    @property
    def execution(self) -> Path:
        """Execution layer root."""
        return self.project / "pgs_execution" / "execution"

    @property
    def governance(self) -> Path:
        """Governance layer root."""
        return _resolve_platform_governance_root()

    @property
    def tooling(self) -> Path:
        """Developer tooling root."""
        return self.project / "pgs_tooling"

    @property
    def transport(self) -> Path:
        """Transport layer root."""
        return self.project / "pgs_transport" / "transport"

    @property
    def capability_transforms(self) -> Path:
        """Capability transforms root."""
        resolver = _layer_resolver()
        return resolver.resolve_layer_root("REUSABLE_TRANSFORMS")

    @property
    def capability_side_effects(self) -> Path:
        """Capability side effects root."""
        resolver = _layer_resolver()
        return resolver.resolve_layer_root("REUSABLE_SIDE_EFFECTS")


# =============================================================================
# Protocol Paths
# =============================================================================

# Artifact types that exist in protocol/artifacts/ and protocol/static_specs/
ArtifactType = Literal[
    "workflows",
    "intents",
    "capability_contracts",
    "events",
    "actors",
    "runtime_bindings",
    "security",
    "capability_transforms",
    "capability_side_effects",
]


class ProtocolPaths:
    """Paths for protocol artifacts and static specs (read-only, checked into git)."""

    def __init__(self, roots: ConcernRoots):
        self._roots = roots
        self._env: dict | None = None


    # --- Roots ---

    def artifacts_root(self) -> Path:
        """Central artifacts root (for shared/core artifacts)."""
        return self._roots.protocol / "artifacts"

    def static_specs_root(self) -> Path:
        return self._roots.protocol / "static_specs"

    # --- Federated (module-specific) artifacts ---

    def module_artifacts_root(self, module_name: str) -> Path:
        """Get protocol artifacts root for a specific module (federated package)."""
        # Query FQDN tree for package info
        try:
            pkg = _get_package_info(module_name)
            physical_root = pkg.get("physical_root", "")
            clean_root = physical_root.lstrip("./")

            # Get directory names from MODULE_DATA_ROOTS (no hardcoding)
            compiled_artifacts = _get_layer_directory("compiled_artifacts", "compiled/artifacts")

            workspace = self._roots.project
            return workspace / clean_root / compiled_artifacts
        except ValueError:
            # Fallback to legacy convention for unknown modules
            return self._roots._package_root_legacy(module_name) / "protocol" / "artifacts"

    def module_artifact(self, module_name: str, artifact_type: ArtifactType, filename: str) -> Path:
        """Get path to a specific artifact in a module's federated package."""
        return self.module_artifacts_root(module_name) / artifact_type / filename

    # --- Artifact directories ---

    def artifacts_dir(self, artifact_type: ArtifactType) -> Path:
        return self.artifacts_root() / artifact_type

    def static_specs_dir(self, artifact_type: ArtifactType) -> Path:
        return self.static_specs_root() / artifact_type

    # --- Single artifact files ---

    def artifact(self, artifact_type: ArtifactType, filename: str, *, template: bool = False) -> Path:
        root = self.static_specs_root() if template else self.artifacts_root()
        return root / artifact_type / filename

    # --- Capability transforms ---

    def capability_transforms_atoms_dir(self) -> Path:
        return self.artifacts_dir("capability_transforms") / "atoms"

    def capability_transforms_ir_dir(self) -> Path:
        return self.artifacts_dir("capability_transforms") / "ir"

    def capability_transforms_molecules_specs_dir(self) -> Path:
        return self.static_specs_dir("capability_transforms") / "molecules"

    def capability_transform_atom(self, atom_name: str) -> Path:
        return self.capability_transforms_atoms_dir() / f"{atom_name}.json"

    def capability_transform_ir(self, molecule_name: str) -> Path:
        return self.capability_transforms_ir_dir() / f"{molecule_name}.molecule.ir.json"

    # --- Capability side effects ---

    def capability_side_effect_spec(
        self,
        cs_type: Literal["persistent", "external", "ephemeral"],
        cs_name: str,
        spec_file: Literal["capability.json", "operations.json", "vocabulary.json"],
    ) -> Path:
        return self._roots.capability_side_effects / cs_type / cs_name / spec_file


# =============================================================================
# Execution Paths
# =============================================================================

class ExecutionPaths:
    """Paths for execution engine components."""

    def __init__(self, roots: ConcernRoots):
        self._roots = roots

    def machine(self) -> Path:
        # Get subdirectory from MODULE_DATA_ROOTS (no hardcoding)
        machine_subdir = _get_layer_directory("execution_machine_subdir", "machine")
        return self._roots.execution / machine_subdir

    def runtime(self) -> Path:
        # Get subdirectory from MODULE_DATA_ROOTS (no hardcoding)
        host_subdir = _get_layer_directory("execution_host_subdir", "host")
        return self._roots.execution / host_subdir

    def conformance(self) -> Path:
        # Get subdirectory from MODULE_DATA_ROOTS (no hardcoding)
        conformance_subdir = _get_layer_directory("execution_conformance_subdir", "conformance")
        return self._roots.execution / conformance_subdir


# =============================================================================
# Governance Paths
# =============================================================================

class GovernancePaths:
    """Paths for registry schemas, vocabulary, conformance tests, and registries."""

    def __init__(self, roots: ConcernRoots):
        self._roots = roots

    # --- Vocabulary ---

    def vocabulary_root(self) -> Path:
        return self._roots.governance / "vocabulary"

    def vocabulary_reserved_dir(self) -> Path:
        """Reserved vocabulary specs."""
        gov_root = self._roots.governance  # pgs_governance/registry
        vocab_reserved = _get_layer_directory("vocabulary_reserved_subdir", "FB_VOCABULARY/reserved")
        return gov_root / vocab_reserved

    def vocabulary_protocol_kinds(self) -> Path:
        """Canonical vocabulary: protocol ontology (node_types, artifact_kinds)."""
        return self.vocabulary_reserved_dir() / "VOCAB_PROTOCOL_KINDS_V0.md"

    def vocabulary_execution_states(self) -> Path:
        """Canonical vocabulary: execution semantics (result_status, exit_reasons)."""
        return self.vocabulary_reserved_dir() / "VOCAB_EXECUTION_STATES_V0.md"

    def vocabulary_language_constraints(self) -> Path:
        """Canonical vocabulary: authoring law (structural_keys, binding_verbs, reserved, forbidden)."""
        return self.vocabulary_reserved_dir() / "VOCAB_LANGUAGE_CONSTRAINTS_V0.md"

    def vocabulary_symbols(self) -> Path:
        return self.vocabulary_root() / "vocabulary_symbols.json"

    def vocabulary_semantic_index(self) -> Path:
        return self.vocabulary_root() / "vocabulary_semantic_index.json"

    # --- Conformance ---

    def conformance_root(self) -> Path:
        return self._roots.governance / "conformance"

    def conformance_test_artifacts_dir(self) -> Path:
        return self.conformance_test_artifacts_dir() / "test_artifacts"

    def conformance_test(self, workflow_code: str) -> Path:
        return self.conformance_test_artifacts_dir() / f"{workflow_code.lower()}.test.json"

    # --- Registry ---

    def registry(self) -> Path:
        """Protocol-level registry."""
        try:
            registry_path = _get_registry_path("registry", "registry")
            return registry_path.parent
        except ValueError:
            gov_root = self._roots.governance
            registry_subdir = _get_layer_directory("governance_subdir", "registry")
            return gov_root / registry_subdir

    def registry_shared(self) -> Path:
        """Shared cross-cutting concerns (CT, CS) in transforms/side_effects packages."""
        # Query FQDN tree for transforms registry (shared platform transforms)
        try:
            return _get_registry_path("transforms", "capability_transforms")
        except ValueError:
            # Fallback to legacy resolution
            return self._roots._package_root_legacy("reusable") / "registry" / "registry"

    def registry_blockchain(self) -> Path:
        """Blockchain domain-specific artifacts (federated package)."""
        # Query FQDN tree for blockchain registry
        # Blockchain has multiple registries (identity, wallet, transaction)
        # Return first one's parent as the base registry dir
        try:
            first_registry = _get_first_registry_path("blockchain")
            # Return parent of specific registry (identity -> base registry dir)
            return first_registry.parent
        except ValueError:
            # Fallback to legacy resolution
            return self._roots.project / "domains" / "blockchain" / "registry" / "registry"

    def registry_blockchain_subdomain(self, subdomain: str) -> Path:
        """Blockchain sub-domain registry (identity, wallet, transaction, etc.)."""
        # Query FQDN tree for specific subdomain registry
        # Try to find registry path containing the subdomain
        try:
            pkg = _get_package_info("blockchain")
            registries = pkg.get("registries", [])

            # Find registry path containing the subdomain
            for reg in registries:
                reg_path = reg["path"]
                if subdomain in reg_path:
                    # Resolve full path
                    physical_root = pkg.get("physical_root", ".")
                    clean_root = physical_root.lstrip("./")
                    workspace = _find_project_root_via_structure()
                    return workspace / clean_root / reg_path

            # If not found in registries, use base registry + subdomain
            return self.registry_blockchain() / subdomain
        except ValueError:
            # Fallback to base registry + subdomain
            return self.registry_blockchain() / subdomain

    # --- Shared (cross-cutting) ---

    def registry_capability_transforms(self) -> Path:
        return self.registry_shared() / "capability_transforms"

    def registry_capability_side_effects(self) -> Path:
        return self.registry_shared() / "capability_side_effects"

    # --- Blockchain domain ---

    def registry_capability_contracts(self) -> Path:
        return self.registry_blockchain() / "capability_contracts"

    def registry_intents(self) -> Path:
        return self.registry_blockchain() / "intents"

    def registry_workflows(self) -> Path:
        return self.registry_blockchain() / "workflows"

    def registry_events(self) -> Path:
        return self.registry_blockchain() / "events"

    def registry_actors(self) -> Path:
        return self.registry_blockchain() / "actors"

    def registry_runtime_bindings(self) -> Path:
        return self.registry_blockchain() / "runtime_bindings"

    # --- Constitution validator ---

    def constitution_validator(self) -> Path:
        return self._roots.governance / "constitution_validator"

    # --- Schemas ---

    def schemas_root(self) -> Path:
        """Schemas root (STRUCTURE-driven path)."""
        schemas_subdir = _get_layer_directory("schemas_subdir", "registry/FB_CONSTITUTION/schemas")
        gov_root = self._roots.governance
        # Resolve relative to governance parent (pgs_governance) since gov_root = pgs_governance/registry
        return gov_root.parent / schemas_subdir

    def schema(self, schema_name: str) -> Path:
        """Path to a specific JSON Schema file."""
        return self.schemas_root() / f"{schema_name}.json"

    def schema_index(self) -> Path:
        """Schema index mapping artifact kinds to schemas."""
        builder_subdir = _get_layer_directory("authoring_builder_subdir", "builder")
        return self._roots.authoring / builder_subdir / "schema_index_instance_v0.json"

    # --- System Registry (Sovereign Authority) ---

    def registry_system(self) -> Path:
        """System-level registry artifacts (constitutions, FQDN tree, schemas)."""
        return self.registry() / "FB_CONSTITUTION"

    def constitution(self, constitution_name: str) -> Path:
        """Path to a specific constitution."""
        return self.registry_system() / f"{constitution_name}.md"

    def fqdn_tree(self) -> Path:
        """Path to the FQDN tree registry artifact."""
        return self.registry_system() / "structures" / "STRUCTURE_FQDN_TREE_V0.md"


# =============================================================================
# Runtime Paths (Execution Outputs)
# =============================================================================

class RuntimePaths:
    """Paths for host outputs: traces, registries, event logs (gitignored, generated)."""

    def __init__(self, roots: ConcernRoots):
        self._roots = roots
        self._env: dict | None = None


    # --- Module resolution ---


    def module_root(self, module_name: str) -> Path:
        """Get module data root from STRUCTURE declarations."""
        roots = _module_data_roots()
        if module_name not in roots:
            raise ValueError(f"Unknown module '{module_name}'. Add to STRUCTURE_MODULE_DATA_ROOTS_V0")
        return _get_project_root() / roots[module_name]

    # --- Trace files ---

    def trace_dir(self, module_name: str, trace_id: str) -> Path:
        return self.module_root(module_name) / trace_id

    def trace_file(self, module_name: str, trace_id: str) -> Path:
        return self.trace_dir(module_name, trace_id) / f"{trace_id}.jsonl"

    def trace_png(self, module_name: str, trace_id: str) -> Path:
        return self.trace_dir(module_name, trace_id) / f"{trace_id}.png"

    def trace_svg(self, module_name: str, trace_id: str) -> Path:
        return self.trace_dir(module_name, trace_id) / f"{trace_id}.svg"

    # --- Registry and event logs ---

    def registry_file(self, module_name: str, name: str) -> Path:
        return self.module_root(module_name) / f"{name}.json"

    def event_log(self, module_name: str, name: str) -> Path:
        return self.module_root(module_name) / f"{name}_events.jsonl"


# =============================================================================
# Authoring Paths
# =============================================================================

class AuthoringPaths:
    """Paths for authoring tools: testbed, dag visualization, compilers, validators."""

    def __init__(self, roots: ConcernRoots):
        self._roots = roots
        self._env: dict | None = None


    # --- Testbed (federated per-package) ---

    def testbed_root(self) -> Path:
        """Legacy: central testbed root for backward compatibility."""
        # Get subdirectory from MODULE_DATA_ROOTS (no hardcoding)
        testbed_subdir = _get_layer_directory("authoring_testbed_subdir", "testbed")
        return self._roots.authoring / testbed_subdir

    def testbed_module(self, module_name: str) -> Path:
        """
        Get testbed root for a module.

        Convention: <module_root>/testbed
        """
        python_module = self._map_module_identifier_to_python_path(module_name)
        return self._roots._package_root(python_module) / "testbed"

    def _map_module_identifier_to_python_path(self, module_id: str) -> str:
        """Map module identifier to Python module path."""
        roots = _module_data_roots()
        if module_id not in roots:
            return module_id

        path = roots[module_id]
        parts = path.split("/")

        if parts[0] == "domains" and len(parts) >= 2:
            return f"domains.{parts[1]}"
        elif parts[0] == "pgs_governance" and len(parts) >= 2:
            return parts[1]
        else:
            return module_id

    def testbed_payloads(self, module_name: str) -> Path:
        return self.testbed_module(module_name) / "test_payloads"

    def testbed_data(self, module_name: str) -> Path:
        return self.testbed_module(module_name) / "data"


    # --- Compilers ---

    def compiler_root(self) -> Path:
        return self._roots.authoring / "compiler"

    def compiler_dir(self, compiler_name: str) -> Path:
        return self.compiler_root() / compiler_name

    def compiler_schema(self, compiler_name: str, schema_file: str) -> Path:
        return self.compiler_dir(compiler_name) / schema_file

    # --- Conformance ---

    def conformance_root(self) -> Path:
        return self._roots.authoring / "conformance"

    def conformance_executor_script(self) -> Path:
        return self.conformance_root() / "workflow_conformance_executor.py"


# =============================================================================
# Transport Paths
# =============================================================================

class TransportPaths:
    """Paths for transport layer: CLI, HTTP server, static assets."""

    def __init__(self, roots: ConcernRoots):
        self._roots = roots

    def env_facts(self) -> Path:
        return self._roots.common / "env_facts" / "default.json"

    def command_line(self) -> Path:
        # Get subdirectory from MODULE_DATA_ROOTS (no hardcoding)
        cli_subdir = _get_layer_directory("transport_command_line_subdir", "command_line")
        return self._roots.transport / cli_subdir

    def http_rest(self) -> Path:
        # Get subdirectory from MODULE_DATA_ROOTS (no hardcoding)
        http_subdir = _get_layer_directory("transport_http_rest_subdir", "http_rest")
        return self._roots.transport / http_subdir

    def governance_registry(self) -> Path:
        """Transport registry registry root."""
        # Query FQDN tree for transport registry path
        try:
            # Transport has registry at registry/registry/http_gateway
            # Return parent of http_gateway as the base registry registry
            gateway_registry = _get_registry_path("transport", "ingress_intents")
            return gateway_registry.parent
        except ValueError:
            # Fallback to convention-based path
            return self._roots.transport / "registry" / "registry"

    def registry_http_gateway(self) -> Path:
        """HTTP gateway domain artifacts."""
        # Query FQDN tree for transport http_gateway registry
        try:
            return _get_registry_path("transport", "ingress_intents")
        except ValueError:
            # Fallback to governance_registry + http_gateway
            return self.governance_registry() / "http_gateway"



# =============================================================================
# Unified Registry
# =============================================================================

class PathRegistry:
    """
    Unified path registry (STRUCTURE sovereignty).

    ALL output paths resolved via resolve_output_path() from STRUCTURE declarations.
    No hardcoded paths, no conventions, no discovery.
    """

    def __init__(self):
        self.roots = ConcernRoots()
        self.protocol = ProtocolPaths(self.roots)
        self.execution = ExecutionPaths(self.roots)
        self.governance = GovernancePaths(self.roots)
        self.runtime = RuntimePaths(self.roots)
        self.authoring = AuthoringPaths(self.roots)
        self.transport = TransportPaths(self.roots)

    def layer_resolver(self) -> LayerResolver:
        """Get layer resolver for layer-centric path resolution."""
        return _layer_resolver()

    def resolve_layer_path(self, layer: str, subpath: str = "") -> Path:
        """
        Resolve layer-relative path.

        Args:
            layer: Layer code (e.g., "GOVERNANCE", "EXECUTION")
            subpath: Optional subpath within layer root

        Returns:
            Absolute Path
        """
        resolver = _layer_resolver()
        return resolver.resolve_layer_root(layer) / subpath if subpath else resolver.resolve_layer_root(layer)

    def resolve_output_path(
        self,
        output_kind: str,
        structure_artifact: dict,
        domain: str | None = None
    ) -> Path:
        """
        Resolve output path from STRUCTURE declaration.

        STRUCTURE sovereignty: ALL output paths must be declared in STRUCTURE artifacts.

        Args:
            output_kind: Output type key (e.g., "testbed_output_path")
            structure_artifact: STRUCTURE artifact dict
            domain: Domain name (REQUIRED for DOMAINS layer and {domain} templates)

        Returns:
            Absolute Path to output directory

        Raises:
            ValueError: If output_kind not declared or subpath contains ".."
            RuntimeError: If domain required but not provided
        """
        output_config = structure_artifact.get("output_configuration")
        if not output_config:
            output_config = structure_artifact.get("frontmatter", {}).get("output_configuration")

        if not output_config:
            structure_code = structure_artifact.get("structure_code") or structure_artifact.get("frontmatter", {}).get("structure_code", "UNKNOWN")
            raise ValueError(
                f"PROTOCOL_INCOMPLETE: STRUCTURE '{structure_code}' missing 'output_configuration'."
            )

        if output_kind not in output_config:
            structure_code = structure_artifact.get("structure_code") or structure_artifact.get("frontmatter", {}).get("structure_code", "UNKNOWN")
            available = list(output_config.keys())
            raise ValueError(
                f"PROTOCOL_INCOMPLETE: STRUCTURE '{structure_code}' does not declare '{output_kind}'. "
                f"Declared outputs: {available or 'NONE'}."
            )

        path_config = output_config[output_kind]

        if "layer" not in path_config:
            from compiler.governance_engine.structure.exceptions import ProtocolIncompleteError
            structure_code = structure_artifact.get("structure_code") or structure_artifact.get("frontmatter", {}).get("structure_code", "UNKNOWN")
            raise ProtocolIncompleteError(
                message=f"STRUCTURE '{structure_code}' output '{output_kind}' missing 'layer' field.",
                artifact=structure_code,
                location=f"output_configuration.{output_kind}",
                details={"config": path_config}
            )

        layer_code = path_config["layer"]
        subpath_template = path_config.get("subpath", "")

        if layer_code == "DOMAINS" and not domain:
            from compiler.governance_engine.structure.exceptions import DomainResolutionError
            raise DomainResolutionError(
                message=f"DOMAINS layer requires domain parameter for '{output_kind}'.",
                details={"output_kind": output_kind, "layer": layer_code}
            )

        if '{domain}' in subpath_template and not domain:
            from compiler.governance_engine.structure.exceptions import ProtocolIncompleteError
            raise ProtocolIncompleteError(
                message=f"Template '{subpath_template}' requires {{domain}} but not provided.",
                details={"template": subpath_template, "output_kind": output_kind}
            )

        if domain and '{domain}' in subpath_template:
            subpath = subpath_template.replace('{domain}', domain)
        else:
            subpath = subpath_template

        if layer_code == "DOMAINS" and not subpath.startswith("domains/"):
            from compiler.governance_engine.structure.exceptions import ProtocolIncompleteError
            raise ProtocolIncompleteError(
                message=f"DOMAINS layer subpath must start with 'domains/', got: {subpath}",
                details={"output_kind": output_kind, "subpath": subpath}
            )

        if ".." in subpath:
            from compiler.governance_engine.structure.exceptions import StructuredError
            raise StructuredError(
                code="CONSTITUTIONAL_VIOLATION",
                message=f"Subpath '{output_kind}' contains '..' escape (layer isolation violation).",
                details={"output_kind": output_kind, "subpath": subpath}
            )

        # Normalize coordinate system: detect repo-relative vs domain-relative paths
        is_repo_relative = subpath.startswith("domains/")

        if is_repo_relative:
            parts = subpath.split("/", 2)

            if len(parts) < 3:
                from compiler.governance_engine.structure.exceptions import StructuredError
                raise StructuredError(
                    code="INVALID_SUBPATH",
                    message=f"Repo-relative subpath '{subpath}' incomplete. Expected 'domains/{{domain}}/{{path}}'.",
                    details={"output_kind": output_kind, "subpath": subpath}
                )

            extracted_domain = parts[1]
            relative_subpath = parts[2]

            if domain and extracted_domain != domain:
                from compiler.governance_engine.structure.exceptions import StructuredError
                raise StructuredError(
                    code="DOMAIN_MISMATCH",
                    message=f"Subpath domain '{extracted_domain}' != artifact domain '{domain}'.",
                    details={"output_kind": output_kind, "subpath": subpath}
                )

            normalized_domain = domain or extracted_domain
            normalized_subpath = relative_subpath
        else:
            normalized_domain = domain
            normalized_subpath = subpath

        resolver = _layer_resolver()
        layer_root = resolver.resolve_layer_root(layer_code, domain=normalized_domain)

        return layer_root / normalized_subpath if normalized_subpath else layer_root


paths = PathRegistry()

__all__ = ["bootstrap", "paths"]


# =============================================================================
# Direct Execution Guard
# =============================================================================

if __name__ == "__main__":
    raise RuntimeError("path_registry is infrastructure. Call bootstrap() from an entry point.")
