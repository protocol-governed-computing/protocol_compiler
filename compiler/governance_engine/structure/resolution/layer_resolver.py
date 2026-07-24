"""
layer_resolver.py — Federation-Boundary Layer Resolution (Constitutional)

Resolves layer paths using STRUCTURE_DISCOVERY_V0 and importlib.
Replaces STRUCTURE_LAYER_AUTHORITY_V0 (permanently deleted in Constitutional Federation refactor).

Core principle: Layer paths are derived from STRUCTURE_DISCOVERY_V0
registry_module entries via importlib — no hardcoded path mappings.

Resolution strategy:
  1. importlib.util.find_spec(registry_module)  — installed packages
  2. Sibling-repo fallback (development topology, project_root.parent / top_package)
"""

from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Any


# =============================================================================
# Domain-extension layer registry
# =============================================================================
# Additive layer definitions registered per-compile from a domain's build manifest
# (STRUCTURE_BUILD_<X>_CONFIG.layer_definitions). Merged with the IMMUTABLE platform
# STRUCTURE_DISCOVERY_V0 layers — the platform surface is never edited to add a domain.
_DOMAIN_LAYER_DEFS: dict[str, dict] = {}


def register_domain_layers(defs: dict) -> None:
    """Register a domain's additive layer definitions for the current compile."""
    if defs:
        _DOMAIN_LAYER_DEFS.update(defs)


def clear_domain_layers() -> None:
    """Clear registered domain layers (hygiene between compiles in one process)."""
    _DOMAIN_LAYER_DEFS.clear()


# =============================================================================
# LayerResolver
# =============================================================================

class LayerResolver:
    """
    Layer-centric resolution engine.

    Loads layer paths from STRUCTURE_DISCOVERY_V0 via importlib.
    No STRUCTURE_LAYER_AUTHORITY_V0 — that artifact is deleted.

    Usage:
        from compiler.governance_engine.structure.resolution import LayerResolver

        resolver = LayerResolver()
        path = resolver.resolve_layer_root("GOVERNANCE")
        transforms_root = resolver.resolve_layer_root("REUSABLE_TRANSFORMS")
    """

    def __init__(self, environment: str = "development_monolithic", project_root: Path | None = None):
        """
        Initialize layer resolver.

        Args:
            environment: Environment name (kept for API compatibility)
            project_root: Explicit project root (if None, resolves from installed
                          pgs_governance package location — CWD-independent)
        """
        if project_root is None:
            from compiler.governance_engine.platform_root import platform_root
            project_root = platform_root()
        self._environment = environment
        self._project_root = project_root
        self._layer_paths: dict[str, Path] = {}
        self._layer_configs: dict[str, dict] = {}
        self._layer_directories: dict[str, str] = {}
        self._loaded = False

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    def _parse_yaml_block(self, content: str) -> dict:
        """Extract YAML block from markdown code fence."""
        match = re.search(r'```yaml\s*\n(.*?)```', content, re.DOTALL)
        if not match:
            raise ValueError("No YAML block found in artifact")
        return yaml.safe_load(match.group(1))

    # PGC B2 topology map — RI-0 registry_module names → subdirs of the platform repo.
    # STRUCTURE_DISCOVERY_V0 is kept verbatim (faithful harvest); this map overrides its
    # importlib resolution so layers resolve inside `platform` with no pgs_* dependency.
    # Layers absent here (domain/RI: blockchain, ai_governance, runtime, ingress, …) are
    # not part of the platform surface and resolve to None by design.
    _PGC_MODULE_MAP: dict[str, tuple[str, ...]] = {
        "pgs_governance.registry": ("registry",),
        "pgs_transforms.registry": ("capability_transforms", "registry"),
        "pgs_side_effects.registry": ("capability_side_effects", "registry"),
    }

    def _resolve_module_to_path(self, registry_module: str) -> Path | None:
        """
        Resolve a STRUCTURE_DISCOVERY_V0 registry_module to a filesystem path (PGC B2).

        Maps the RI-0 package name to a subdir of PGC_PLATFORM_ROOT. Domain/RI layers not
        present in the platform surface return None (they are absent from the platform
        compile scope, by design — no importlib, no sibling-repo fallback, no pgs_* dep).
        """
        from compiler.governance_engine.platform_root import platform_root

        subpath = self._PGC_MODULE_MAP.get(registry_module)
        if subpath is None:
            return None
        return platform_root().joinpath(*subpath)

    def _layer_root_from_config(self, layer_config: dict) -> Path | None:
        """
        Resolve a layer's filesystem root under PGC_PLATFORM_ROOT — data-driven.

        Preference (protocol-declared, zero compiler-side per-domain knowledge):
          1. platform_subpath — the layer declares its own subdir of the platform repo.
             This is the DOMAIN-EXTENSION path: a new domain/workload registers its source
             purely in the protocol (STRUCTURE_DISCOVERY_V0), with NO compiler edits.
          2. registry_module — RI-0 harvest package names, mapped via _PGC_MODULE_MAP
             (the platform surface layers; kept for backward compatibility).
        """
        from compiler.governance_engine.platform_root import platform_root

        subpath = layer_config.get("platform_subpath")
        if subpath:
            parts = str(subpath).strip("/").split("/")
            return platform_root().joinpath(*parts)

        registry_module = layer_config.get("registry_module")
        if registry_module:
            return self._resolve_module_to_path(registry_module)

        return None

    def _load_layer_paths_from_discovery(self) -> None:
        """
        Load layer paths from STRUCTURE_DISCOVERY_V0.

        CONSTITUTIONAL: STRUCTURE_DISCOVERY_V0 is the single source of truth for
        layer-to-module mappings. Located at:
            pgs_governance/registry/FB_CONSTITUTION/structures/
        """
        from compiler.governance_engine.platform_root import governance_registry_root
        discovery_path = (
            governance_registry_root() /
            "declaration" / "structure" / "structures" / "STRUCTURE_DISCOVERY_V0.md"
        )

        if not discovery_path.exists():
            raise FileNotFoundError(
                f"STRUCTURE_DISCOVERY_V0 not found at: {discovery_path}\n"
                f"CONSTITUTIONAL VIOLATION: discovery artifact is required."
            )

        content = discovery_path.read_text(encoding="utf-8")
        data = self._parse_yaml_block(content)
        layers = data.get("discovery", {}).get("layers", {})

        for layer_code, layer_config in layers.items():
            self._layer_configs[layer_code] = layer_config or {}
            path = self._layer_root_from_config(layer_config or {})
            if path is not None:
                self._layer_paths[layer_code] = path

        # Domain-extension layers (additive; the immutable platform discovery above is untouched).
        for layer_code, layer_config in _DOMAIN_LAYER_DEFS.items():
            self._layer_configs[layer_code] = layer_config or {}
            path = self._layer_root_from_config(layer_config or {})
            if path is not None:
                self._layer_paths[layer_code] = path

    def _load_artifacts(self) -> None:
        """Load all structural artifacts from STRUCTURE_DISCOVERY_V0."""
        if self._loaded:
            return

        self._load_layer_paths_from_discovery()
        self._load_module_data_roots()

        self._loaded = True

    def _load_module_data_roots(self) -> None:
        """Load STRUCTURE_MODULE_DATA_ROOTS_V0 artifact."""
        from compiler.governance_engine.platform_root import governance_registry_root
        path = (
            governance_registry_root() /
            "declaration" / "structure" / "structures" / "STRUCTURE_MODULE_DATA_ROOTS_V0.md"
        )

        if not path.exists():
            self._layer_directories = {}
            return

        content = path.read_text(encoding="utf-8")
        data = self._parse_yaml_block(content)
        self._layer_directories = data.get("layer_directories", {})

    def _get_layer_directory(self, dir_key: str, default: str = "") -> str:
        """
        Get directory name from MODULE_DATA_ROOTS layer_directories.

        Args:
            dir_key: Directory key (e.g., "compiled_root", "runtime_root")
            default: Default value if key not found
        """
        return self._layer_directories.get(dir_key, default)

    def _resolve_layer_path(self, layer_code: str) -> Path:
        """
        Get module root path for a layer.

        Args:
            layer_code: Layer code from STRUCTURE_DISCOVERY_V0 (e.g., "GOVERNANCE")

        Returns:
            Absolute Path to layer module root

        Raises:
            ValueError: If layer code not found in STRUCTURE_DISCOVERY_V0
        """
        self._load_artifacts()
        if layer_code not in self._layer_paths:
            raise ValueError(
                f"Layer '{layer_code}' not found in STRUCTURE_DISCOVERY_V0. "
                f"Available: {list(self._layer_paths.keys())}"
            )
        return self._layer_paths[layer_code]

    def _get_domain_federation_config(self, layer: str) -> dict:
        """
        Read domain federation configuration from STRUCTURE artifact.

        Searches registry/FB_*/ rglob for STRUCTURE_BUILD_{LAYER}_CONFIG_V0.md.

        Returns:
            Federation config dict or {} if not found or not enabled
        """
        from compiler.governance_engine.platform_root import governance_registry_root
        federation_root = governance_registry_root()
        config_artifact_code = f"STRUCTURE_BUILD_{layer}_CONFIG_V0"

        artifact_path = None
        for candidate in federation_root.rglob(f"{config_artifact_code}.md"):
            artifact_path = candidate
            break

        if artifact_path is None:
            return {}

        try:
            content = artifact_path.read_text(encoding="utf-8")
            match = re.search(r'```yaml\s*\n(.*?)```', content, re.DOTALL)
            if not match:
                return {}

            artifact_data = yaml.safe_load(match.group(1))
            output_config = artifact_data.get("output_configuration", {})
            domain_federation = output_config.get("domain_federation", {})
            output_rules = output_config.get("output_rules", {})

            if not domain_federation.get("enabled"):
                return {}

            return {
                "enabled": domain_federation.get("enabled"),
                "pattern": domain_federation.get("pattern"),
                "output_rules": output_rules,
            }
        except (yaml.YAMLError, OSError):
            return {}

    # -------------------------------------------------------------------------
    # Public Query API
    # -------------------------------------------------------------------------

    def resolve_layer_artifact_path(self, layer: str, artifact_type: str, subpath: str = "") -> Path:
        """
        Resolve physical path for a layer-relative artifact.

        Args:
            layer: Layer code (e.g., "GOVERNANCE")
            artifact_type: Artifact type (e.g., "registry", "protocol")
            subpath: Optional subpath within artifact type directory

        Returns:
            Absolute Path to artifact
        """
        layer_root = self._resolve_layer_path(layer)
        base_path = layer_root
        if artifact_type:
            base_path = base_path / artifact_type
        if subpath:
            base_path = base_path / subpath
        return base_path

    def resolve_output_path(
        self,
        output_type: str,
        layer: str,
        structure: dict,
        domain: str = None
    ) -> Path:
        """
        Resolve output path from STRUCTURE registry.

        CONSTITUTIONAL: Zero hardcoded paths, fail-fast on undeclared outputs.

        Args:
            output_type: Output type key ("artifacts", "conformance", "layer_outputs")
            layer: Target layer code ("GOVERNANCE", "BLOCKCHAIN", etc.)
            structure: STRUCTURE artifact dict (e.g., STRUCTURE_BUILD_PLATFORM_CONFIG_V0)
            domain: Optional domain name (for legacy DOMAINS layer federation)

        Returns:
            Absolute Path to output location

        Raises:
            RuntimeError: If STRUCTURE missing output_configuration
            RuntimeError: If output_type not declared in STRUCTURE
            RuntimeError: If layer not declared in layer_outputs

        Governed By:
            INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0
            STRUCTURE_BUILD_PLATFORM_CONFIG_V0
        """
        if "output_configuration" not in structure:
            raise RuntimeError(
                f"STRUCTURE missing output_configuration. "
                f"Add to STRUCTURE artifact before using. "
                f"STRUCTURE keys: {list(structure.keys())}"
            )

        output_config = structure["output_configuration"]

        # Domain federation path (DOMAINS synthetic layer)
        if domain and layer == "DOMAINS":
            domain_federation = output_config.get("domain_federation", {})
            if not domain_federation.get("enabled"):
                raise RuntimeError(
                    "STRUCTURE violation: domain provided but domain_federation not enabled"
                )
            pattern = domain_federation.get("pattern")
            base_layer = domain_federation.get("layer")
            if not pattern or not base_layer:
                raise RuntimeError(
                    "STRUCTURE violation: domain_federation missing pattern or layer"
                )
            try:
                base_path = self._resolve_layer_path(base_layer)
            except ValueError as e:
                raise RuntimeError(
                    f"Unknown layer: {base_layer}. "
                    f"Layer must be declared in STRUCTURE_DISCOVERY_V0. "
                    f"Original error: {e}"
                )
            layer_root = base_path.parent
            output_rules = output_config.get("output_rules", {})
            artifacts_config = output_rules.get("artifacts", {})
            artifacts_subpath = artifacts_config.get("subpath", "compiled/artifacts")
            federated_subpath = pattern.format(domain=domain, subpath=artifacts_subpath)
            return layer_root / federated_subpath

        if output_type not in output_config:
            raise RuntimeError(
                f"Undeclared output type: '{output_type}'. "
                f"Available in STRUCTURE: {list(output_config.keys())}. "
                f"Add to STRUCTURE output_configuration before using."
            )

        if output_type == "layer_outputs":
            layer_configs = output_config["layer_outputs"]
            if layer not in layer_configs:
                raise RuntimeError(
                    f"Layer '{layer}' not declared in layer_outputs. "
                    f"Available layers: {list(layer_configs.keys())}. "
                    f"Add to STRUCTURE_BUILD_PLATFORM_CONFIG_V0 layer_outputs."
                )
            config = layer_configs[layer]
        else:
            config = output_config[output_type]

        target_layer = config["layer"]
        subpath = config["subpath"]

        if ".." in subpath:
            raise RuntimeError(
                f"Path escape detected in output_type '{output_type}': {subpath}. "
                f"STRUCTURE artifacts must not use '..' traversals."
            )

        # PGC: consolidate every layer's output into one snapshot root — no RI-0 federated
        # scatter. Output location is single; discovery/govern already validated layers.
        from compiler.governance_engine.platform_root import snapshot_root
        return snapshot_root() / subpath

    def resolve_artifact_output_path(
        self,
        layer: str,
        output_type: str,
        domain: str = None,
    ) -> Path:
        """
        Resolve output path for artifact with domain federation support.

        INVARIANT O1 (Output Determinism):
        All artifact output paths MUST be derived from STRUCTURE declarations.

        Args:
            layer: Layer code (e.g., "GOVERNANCE", "BLOCKCHAIN")
            output_type: Output type (e.g., "artifacts", "conformance")
            domain: Optional domain name (e.g., "identity", "transaction")

        Returns:
            Absolute Path to output location
        """
        # PGC: single consolidated snapshot root (no federated scatter).
        from compiler.governance_engine.platform_root import snapshot_root
        repo_root = snapshot_root()
        compiled_root = self._get_layer_directory("compiled_root", "compiled")

        federation_config = self._get_domain_federation_config(layer)

        if domain and federation_config:
            output_rules = federation_config.get("output_rules", {})
            output_rule = output_rules.get(output_type, {})
            if output_rule.get("per_domain", False):
                pattern = federation_config.get("pattern", "domains/{domain}/{subpath}")
                subpath = output_rule.get("subpath", f"{compiled_root}/{output_type}")
                path_str = pattern.replace("{domain}", domain).replace("{subpath}", subpath)
                return repo_root / path_str

        return repo_root / compiled_root / output_type

    def resolve_layer_root(self, layer: str, domain: str = None) -> Path:
        """
        Resolve physical root for a layer in current environment.

        Args:
            layer: Layer code from STRUCTURE_DISCOVERY_V0
            domain: Optional subdomain (e.g., "identity" for BLOCKCHAIN layer)

        Returns:
            Absolute Path to layer module root, or module root / domain if domain given

        Raises:
            ValueError: If layer not found in STRUCTURE_DISCOVERY_V0

        Governed By:
            INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0
            STRUCTURE_DISCOVERY_V0
        """
        self._load_artifacts()

        base_path = self._resolve_layer_path(layer)

        if domain:
            return base_path / domain

        return base_path

    def resolve_layer_repo_root(self, layer: str) -> Path:
        """
        Resolve repository root for a layer (BOOTSTRAP/DISCOVERY ONLY).

        EXPLICIT BOOTSTRAP BOUNDARY
        This method should ONLY be used during:
        - Domain discovery (ct_scan_artifacts._discover_domains)
        - Protocol loader bootstrap (protocol_loader discovery phase)

        DO NOT USE for runtime path resolution — use resolve_layer_root() instead.

        Args:
            layer: Layer code from STRUCTURE_DISCOVERY_V0

        Returns:
            Absolute Path to repository root (parent of module root)

        Governed By:
            INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0
        """
        module_root = self._resolve_layer_path(layer)
        return module_root.parent

    def resolve_layer_implementation_namespace(self, layer: str) -> str:
        """
        Resolve the physical implementation namespace for a layer (STRUCTURE_DISCOVERY_V0).

        The intra-package layout of capability implementations (e.g. "capability_transforms.atoms"
        for domain layers, "transforms.atoms" for REUSABLE_TRANSFORMS) is governed metadata — the
        single authoritative source for module-path materialization. Consumers append this to
        "{package}.implementation." to form a fully-qualified module path, with zero embedded
        knowledge of package organization.

        Raises:
            ValueError: If the layer is unknown, or declares no implementation_namespace.
        """
        self._load_artifacts()
        if layer not in self._layer_configs:
            raise ValueError(
                f"Layer '{layer}' not found in STRUCTURE_DISCOVERY_V0. "
                f"Available: {list(self._layer_configs.keys())}"
            )
        namespace = self._layer_configs[layer].get("implementation_namespace")
        if not namespace:
            raise ValueError(
                f"Layer '{layer}' declares no implementation_namespace in STRUCTURE_DISCOVERY_V0. "
                f"Add it to the layer's discovery config."
            )
        return namespace

    def list_layers(self) -> list[str]:
        """List all defined layer codes (from STRUCTURE_DISCOVERY_V0)."""
        self._load_artifacts()
        return list(self._layer_paths.keys())


# =============================================================================
# Singleton Instance (for backward compatibility)
# =============================================================================

_default_resolver: LayerResolver | None = None


def get_default_resolver(environment: str = "development_monolithic", project_root: Path | None = None) -> LayerResolver:
    """Get singleton default resolver instance."""
    global _default_resolver

    if _default_resolver is None:
        _default_resolver = LayerResolver(environment=environment, project_root=project_root)

    return _default_resolver


__all__ = [
    "LayerResolver",
    "get_default_resolver",
]


# =============================================================================
# Direct Execution Guard
# =============================================================================

if __name__ == "__main__":
    resolver = LayerResolver()

    print("=== Layer Paths (from STRUCTURE_DISCOVERY_V0) ===")
    for layer_code in resolver.list_layers():
        path = resolver._resolve_layer_path(layer_code)
        print(f"{layer_code}: {path}")

    print("\n=== Path Resolution ===")
    gov_path = resolver.resolve_layer_artifact_path("GOVERNANCE", "registry", "concerns")
    print(f"GOVERNANCE registry/concerns: {gov_path}")

    exec_path = resolver.resolve_layer_root("EXECUTION")
    print(f"EXECUTION root: {exec_path}")
