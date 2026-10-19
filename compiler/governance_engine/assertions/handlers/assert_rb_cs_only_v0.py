"""
ASSERT_RB_CS_ONLY_V0 Handler

Validates that every binding key in an RB artifact's core.bindings map references
a CS artifact (artifact code starting with CS_).

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all RB binding keys reference CS artifacts only.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    rb_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "RB":
            continue

        rb_code = artifact.get("artifact_code", "UNKNOWN")
        rb_count += 1

        bindings = artifact.get("frontmatter", {}).get("core", {}).get("bindings", {})

        if not isinstance(bindings, dict):
            continue

        for binding_key in bindings:
            # Extract artifact code from FQDN (last segment after ::)
            # e.g., "capability_side_effects::CS_REGISTRY_V0" → "CS_REGISTRY_V0"
            if "::" in binding_key:
                artifact_code_part = binding_key.split("::")[-1]
            else:
                artifact_code_part = binding_key

            if not artifact_code_part.startswith("CS_"):
                violations.append({
                    "assert": "ASSERT_RB_CS_ONLY_V0",
                    "artifact": rb_code,
                    "binding_key": binding_key,
                    "violation": (
                        f"RB binding key '{binding_key}' does not reference a CS artifact "
                        f"(artifact code '{artifact_code_part}' must start with 'CS_')"
                    ),
                    "fix": (
                        f"RB artifacts bind CS capabilities only. "
                        f"Remove binding for '{binding_key}' or replace with a CS artifact FQDN."
                    ),
                })

    return {
        "assert_count": rb_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
