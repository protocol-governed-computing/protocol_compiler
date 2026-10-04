"""
platform_root.py — PGC source resolution.

The normative surface (registry + structural schemas) lives in the PGC `platform`
repository, not in any `pgs_*` package. This module is the single place that resolves it,
from an explicit environment anchor — replacing RI-0's `pgs_governance.__file__` package
location. Fail-hard, cwd-independent, zero inference.

  PGC_PLATFORM_ROOT  — absolute path to the platform repo (dir containing `registry/`).
  PGC_BUILD_ROOT     — absolute path for compiled output (keeps `platform` read-only).
                       Defaults to <PGC_PLATFORM_ROOT>/../_build if unset.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

_PLATFORM_ENV = "PGC_PLATFORM_ROOT"
_BUILD_ENV = "PGC_BUILD_ROOT"


def platform_root() -> Path:
    """Absolute path to the PGC platform repo. Fail-hard if unset or invalid."""
    v = os.environ.get(_PLATFORM_ENV)
    if not v:
        raise RuntimeError(
            f"{_PLATFORM_ENV} is not set. The PGC compiler resolves the normative surface "
            f"from the platform repo — set {_PLATFORM_ENV} to the platform repo root "
            f"(the directory containing registry/)."
        )
    p = Path(v).expanduser().resolve()
    if not (p / "registry").is_dir():
        raise RuntimeError(
            f"{_PLATFORM_ENV}={p} is not a PGC platform repo (no registry/ directory found)."
        )
    return p


def governance_registry_root() -> Path:
    """<platform>/registry — the governance federation-boundary registry root."""
    return platform_root() / "registry"


_DOMAIN_ENV = "PGC_DOMAIN_ROOTS"


def domain_root() -> Path:
    """Absolute path to the domain being compiled. Fail-hard if unset or invalid.

    A domain (workload or business domain) is self-describing and lives in its OWN repo —
    it is not a subdirectory of the platform surface. Its build manifest declares layer
    sources as `domain_subpath`, resolved here. Only the first PGC_DOMAIN_ROOTS entry is
    a compile target; the rest are import surface.
    """
    v = os.environ.get(_DOMAIN_ENV, "").split(os.pathsep)[0]
    if not v:
        raise RuntimeError(
            f"{_DOMAIN_ENV} is not set. A domain layer declared `domain_subpath`, which "
            f"resolves under the domain repo root — set {_DOMAIN_ENV} to the domain root "
            f"(the directory containing registry/)."
        )
    p = Path(v).expanduser().resolve()
    if not (p / "registry").is_dir():
        raise RuntimeError(
            f"{_DOMAIN_ENV}={p} is not a PGC domain root (no registry/ directory found)."
        )
    return p


def output_root(structure: dict) -> Path:
    """Where a build writes: `output_configuration.root`, under the repository declaring the build.

    The root is declared by the build configuration, never supplied by the invocation. Two
    compositions from one surface were once written wherever `PGC_SNAPSHOT_ROOT` pointed, and
    nothing refused one written over the other: both builds succeeded, and the directory named for
    one held the other. A root the configuration declares is checkable, so two in-force
    configurations of one repository naming the same root are refused here.

    It resolves against the repository declaring the configuration — the directory holding its
    `registry/` — so a platform build and a domain build each write inside their own repository.
    """
    from compiler.atoms.force import in_force
    from compiler.structure_loader import (
        extract_yaml_from_machine_section,
        get_bootstrap_search_roots,
        locate_structure_artifact,
    )

    code = structure.get("structure_artifact_code")
    if not code:
        raise RuntimeError("output_root needs the build configuration's structure_artifact_code")
    declared = (structure.get("output_configuration") or {}).get("root")
    if not isinstance(declared, str) or not declared:
        raise RuntimeError(
            f"{code} declares no output_configuration.root. A build writes only where its "
            f"configuration says, so a configuration naming no root cannot be built."
        )
    if Path(declared).is_absolute() or ".." in Path(declared).parts:
        raise RuntimeError(f"{code} declares output root {declared!r}; it must be a path inside "
                           f"the repository declaring the configuration.")

    source = locate_structure_artifact(code, get_bootstrap_search_roots())
    registry = next((p for p in source.parents if p.name == "registry"), None)
    if registry is None:
        raise RuntimeError(f"{code} is not declared under a registry/ directory: {source}")
    repo = registry.parent

    for other in sorted(registry.rglob("STRUCTURE_BUILD_*_CONFIG_*.md")):
        if other == source:
            continue
        try:
            block = yaml.safe_load(extract_yaml_from_machine_section(other.read_text(encoding="utf-8")))
        except (ValueError, yaml.YAMLError):
            continue
        if not isinstance(block, dict) or not in_force(block):
            continue
        if (block.get("output_configuration") or {}).get("root") == declared:
            raise RuntimeError(
                f"{code} and {other.stem} both declare output root {declared!r} in {repo}. Two "
                f"compositions written to one root overwrite each other; each declares its own."
            )

    p = repo / declared
    p.mkdir(parents=True, exist_ok=True)
    return p


def ct_implementation_root() -> Path:
    """<platform>/capability_transforms/implementation — flat CT reference impls (ct_x.py)."""
    return platform_root() / "capability_transforms" / "implementation"


def cs_implementation_root() -> Path:
    """<platform>/capability_side_effects/implementation — CS reference impls (CS_X/runtime.py)."""
    return platform_root() / "capability_side_effects" / "implementation"


def build_root() -> Path:
    """Absolute output root for compiled artifacts. Never writes into `platform`."""
    v = os.environ.get(_BUILD_ENV)
    p = Path(v).expanduser().resolve() if v else (platform_root().parent / "_build")
    p.mkdir(parents=True, exist_ok=True)
    return p
