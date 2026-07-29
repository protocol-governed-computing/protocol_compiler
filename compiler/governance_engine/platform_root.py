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


_SNAPSHOT_ENV = "PGC_SNAPSHOT_ROOT"


def snapshot_root() -> Path:
    """Single consolidated output root for the compiled PGC Platform Snapshot.

    All layers write here (no RI-0 federated scatter). Defaults to <platform>/snapshot;
    override with PGC_SNAPSHOT_ROOT. The snapshot is generated output — gitignored, and
    regenerable from the platform source at any time (warm reboot).
    """
    v = os.environ.get(_SNAPSHOT_ENV)
    p = Path(v).expanduser().resolve() if v else (platform_root() / "snapshot")
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
