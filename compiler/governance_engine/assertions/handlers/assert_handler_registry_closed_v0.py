"""
ASSERT_HANDLER_REGISTRY_CLOSED_V0 Handler

Verifies every ASSERT artifact in the compiled set has its implementation handler
registered in the static HANDLER_REGISTRY.

CIRCULAR IMPORT NOTE: HANDLER_REGISTRY is imported lazily inside execute() because
this module is itself imported by __init__.py which defines HANDLER_REGISTRY. A
module-level import would create a circular dependency. By the time execute() is
called, all modules are fully loaded and the lazy import is safe.
"""

from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify every ASSERT artifact has a registered handler.

    Args:
        artifacts: All compiled artifacts
        compilation_context: Not used

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": str
        }
    """
    # Lazy import to avoid circular dependency with __init__.py
    from compiler.governance_engine.assertions.handlers import HANDLER_REGISTRY

    violations = []
    assert_artifacts = [a for a in artifacts if a.get("artifact_type") == "ASSERT"]

    for artifact in assert_artifacts:
        fqdn_id = artifact.get("fqdn_id", "<unknown>")
        artifact_code = artifact.get("artifact_code", "<unknown>")
        frontmatter = artifact.get("frontmatter", {})
        implementation = frontmatter.get("implementation", {})
        module = implementation.get("module", "")

        if not module:
            violations.append({
                "fqdn": fqdn_id,
                "artifact_code": artifact_code,
                "rule": "compiler::INVARIANT_HANDLER_REGISTRY_CLOSED_V0",
                "message": "ASSERT artifact has no implementation.module declared",
                "fix": "Declare implementation.module in the ASSERT artifact's machine block",
            })
            continue

        if module not in HANDLER_REGISTRY:
            violations.append({
                "fqdn": fqdn_id,
                "artifact_code": artifact_code,
                "module": module,
                "rule": "compiler::INVARIANT_HANDLER_REGISTRY_CLOSED_V0",
                "message": f"Handler not registered: {module}",
                "fix": "Add handler import and HANDLER_REGISTRY entry in handlers/__init__.py",
            })

    if violations:
        return {
            "assert_count": len(assert_artifacts),
            "violations": violations,
            "status": "FAILED",
        }

    return {
        "assert_count": len(assert_artifacts),
        "violations": [],
        "status": "PASSED",
    }
