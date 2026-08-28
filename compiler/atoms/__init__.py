"""
Atoms: Pure functions with no side effects.

Design:
- Single responsibility
- Explicit inputs/outputs
- No I/O, no state
- Independently testable
- Reusable across phases
"""

from compiler.atoms.error_codes import ErrorCode, ERROR_SUGGESTIONS
from compiler.atoms.errors import CompilerError, Severity
from compiler.atoms.fqdn import FQDN, parse_fqdn, build_fqdn, to_fqdn
from compiler.atoms.invariants import require, require_not_none, require_exists
from compiler.atoms.phase import PhaseResult, PhaseStatus, PhaseMetrics
from compiler.atoms.pipeline import strip_transient_pipeline_fields
from compiler.atoms.sorting import (
    ensure_deterministic_output,
    sort_artifacts_by_fqdn,
    sort_by_fqdn,
    sort_dict_keys,
)
from compiler.atoms.snapshot_gate import assert_snapshot_valid

__all__ = [
    # Error model
    "CompilerError",
    "ErrorCode",
    "ERROR_SUGGESTIONS",
    "Severity",
    # FQDN identity
    "FQDN",
    "parse_fqdn",
    "build_fqdn",
    "to_fqdn",
    # Phase results
    "PhaseResult",
    "PhaseStatus",
    "PhaseMetrics",
    # Invariant enforcement
    "require",
    "require_not_none",
    "require_exists",
    # Pipeline metadata
    "strip_transient_pipeline_fields",
    # Deterministic ordering
    "ensure_deterministic_output",
    "sort_artifacts_by_fqdn",
    "sort_by_fqdn",
    "sort_dict_keys",
    # Snapshot admission control
    "assert_snapshot_valid",
]
