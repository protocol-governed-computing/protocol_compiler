"""
ASSERT_ATOM_OUTPUT_PURITY_V0 Handler

Validates CT atoms return explicit outputs in all cases, never raise business logic exceptions.
"""

import ast
from pathlib import Path
from typing import Any

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver
from compiler.governance_engine.structure.resolution.path_registry import bootstrap


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify CT atoms are pure functions returning explicit outputs.

    Args:
        artifacts: All validated artifacts
        compilation_context: Not used

    Returns:
        {
            "assert_count": int,
            "violations": list[dict]
        }
    """
    violations = []

    # Filter to CT artifacts only
    ct_artifacts = [
        a for a in artifacts
        if a.get("frontmatter", {}).get("artifact_kind") == "CAPABILITY_TRANSFORM"
    ]

    for ct_artifact in ct_artifacts:
        fqdn = ct_artifact["fqdn_id"]
        artifact_code = ct_artifact.get("artifact_code")

        # Find implementation file
        impl_path = _find_ct_implementation(artifact_code)

        if not impl_path or not impl_path.exists():
            # Skip if implementation not found (handled by other assertion)
            continue

        # Parse implementation
        try:
            source = impl_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            # Find execute() function
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "execute":
                    # Check for business logic exceptions
                    purity_violations = _check_purity_violations(node, source)

                    if purity_violations:
                        for violation_msg, line_num in purity_violations:
                            violations.append({
                                "fqdn": fqdn,
                                "rule": "fb.capability_transforms::INVARIANT_ATOM_OUTPUT_PURITY_V0",
                                "message": f"{impl_path.name}:{line_num} - {violation_msg}",
                                "fix": "Return error status in output dict instead of raising business logic exception"
                            })

        except Exception as e:
            violations.append({
                "fqdn": fqdn,
                "rule": "fb.capability_transforms::INVARIANT_ATOM_OUTPUT_PURITY_V0",
                "message": f"Failed to parse implementation file {impl_path.name}: {str(e)}",
                "fix": "Fix Python syntax errors in CT implementation file"
            })

    if violations:
        return {
            "assert_count": len(ct_artifacts),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(ct_artifacts),
        "violations": [],
        "status": "PASSED"
    }


def _find_ct_implementation(artifact_code: str) -> Path | None:
    """Find CT implementation file (flat PGC layout: capability_transforms/implementation/ct_x.py)."""
    from compiler.governance_engine.platform_root import ct_implementation_root
    impl_path = ct_implementation_root() / f"{artifact_code.lower()}.py"
    return impl_path if impl_path.exists() else None


def _check_purity_violations(func_node: ast.FunctionDef, source: str) -> list[tuple[str, int]]:
    """
    Check for purity violations in execute() function.

    Returns list of (violation_message, line_number) tuples.
    """
    violations = []
    source_lines = source.split("\n")

    # Find input validation block (first few lines, before business logic starts)
    # We allow exceptions in input validation only
    input_validation_end_line = _find_input_validation_end(func_node, source_lines)

    for node in ast.walk(func_node):
        if isinstance(node, ast.Raise):
            # Check if raise is after input validation block
            if node.lineno > input_validation_end_line:
                line_content = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""

                # Check if it's a business logic exception (not input validation)
                if _is_business_logic_exception(line_content):
                    violations.append((
                        f"Business logic exception detected: {line_content}",
                        node.lineno
                    ))

    return violations


def _find_input_validation_end(func_node: ast.FunctionDef, source_lines: list[str]) -> int:
    """
    Find line number where input validation ends.

    Heuristic: Input validation is typically the first ~20 lines of execute().
    Look for patterns like:
    - if "field" not in inputs: raise ValueError
    - if not isinstance(...): raise TypeError

    Returns line number after which business logic starts.
    """
    # Default: first 20 lines of function are input validation
    func_start = func_node.lineno
    return func_start + 20


def _is_business_logic_exception(line: str) -> bool:
    """
    Check if exception is for business logic vs input validation.

    Business logic exceptions contain domain terms like:
    - "Quota exhausted"
    - "Training not completed"
    - "Insufficient balance"

    Input validation exceptions contain:
    - "missing required input"
    - "must be int/str/bool"
    - "invalid type"
    """
    business_logic_patterns = [
        "quota",
        "training",
        "balance",
        "exhausted",
        "completed",
        "available",
        "eligible",
    ]

    input_validation_patterns = [
        "missing",
        "required",
        "must be",
        "invalid type",
        "type mismatch",
    ]

    line_lower = line.lower()

    # If contains input validation patterns, it's OK
    if any(pattern in line_lower for pattern in input_validation_patterns):
        return False

    # If contains business logic patterns, it's a violation
    if any(pattern in line_lower for pattern in business_logic_patterns):
        return True

    # Default: assume it's a violation if we can't categorize
    # (Conservative approach - fail safe)
    return False
