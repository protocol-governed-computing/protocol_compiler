"""
ASSERT_TRANSPORT_NO_DYNAMIC_ROUTING_V0 Handler

Validates that no TI_ or TE_ artifact contains conditional routing logic,
dynamic target resolution, or runtime dispatch declarations.

CONSTITUTIONAL: Pure rule checker — reads artifact set from context.
"""

import re

# Patterns indicating dynamic or conditional routing
_DYNAMIC_REF_PREFIX = "$"
_CONDITIONAL_KEYS = {"if", "if_field", "match", "switch", "when", "route_by", "dispatch"}
_WILDCARD_PATTERNS = [
    (re.compile(r"\*"), "wildcard routing pattern"),
    (re.compile(r"\?"), "conditional routing pattern"),
]


def _contains_conditional_keys(value, path: str, artifact_code: str, violations: list, assert_name: str) -> None:
    """Recursively check for forbidden routing keys in a dict structure."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k in _CONDITIONAL_KEYS:
                violations.append({
                    "assert": assert_name,
                    "artifact": artifact_code,
                    "field": path,
                    "key": k,
                    "violation": f"Forbidden conditional routing key '{k}' — transport routing must be static",
                    "fix": "Remove conditional routing logic; declare one explicit target",
                })
            _contains_conditional_keys(v, f"{path}.{k}", artifact_code, violations, assert_name)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _contains_conditional_keys(item, f"{path}[{i}]", artifact_code, violations, assert_name)


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate TI_ and TE_ artifacts for absence of dynamic routing.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    transport_count = 0

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in ("TI", "TE"):
            continue

        artifact_code = artifact.get("artifact_code", "UNKNOWN")
        transport_count += 1
        frontmatter = artifact.get("frontmatter", {})

        # Check for dynamic workflow reference in TI
        if artifact_type == "TI":
            wf_ref = frontmatter.get("core", {}).get("workflow", "")
            if isinstance(wf_ref, str) and wf_ref.startswith(_DYNAMIC_REF_PREFIX):
                violations.append({
                    "assert": "ASSERT_TRANSPORT_NO_DYNAMIC_ROUTING_V0",
                    "artifact": artifact_code,
                    "field": "core.workflow",
                    "value": wf_ref,
                    "violation": "TI core.workflow is a dynamic reference — static FQDN required",
                    "fix": "Replace with an explicit workflow FQDN",
                })

        # Check for conditional routing keys anywhere in frontmatter
        _contains_conditional_keys(
            frontmatter,
            "frontmatter",
            artifact_code,
            violations,
            "ASSERT_TRANSPORT_NO_DYNAMIC_ROUTING_V0",
        )

    return {
        "assert_count": transport_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
