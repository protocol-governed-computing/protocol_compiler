"""
ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0 Handler

Validates that:
- Every TI_ artifact declares an explicit admission_schema with at least one field
- No TI_ artifact uses passthrough mode
- Every TE_ artifact declares an explicit response_schema or projection declaration

CONSTITUTIONAL: Pure rule checker — reads artifact set from context.
"""

# Keys that indicate TE_ has a projection declaration
_TE_PROJECTION_KEYS = {"response_schema", "projection_schema", "projection"}

# Keys that indicate TI_ passthrough (forbidden)
_PASSTHROUGH_KEYS = {"passthrough"}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate TI_ and TE_ artifacts for canonical normalization declarations.

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
        # Accepted Transport-Standard block shape (flat): TI declares `input_contract` (by
        # reference); TE declares `output_contract` (the projection). Legacy `core.*` names retained.
        fm = artifact.get("frontmatter", {})

        if artifact_type == "TI":
            # Check for forbidden passthrough
            if fm.get("passthrough") is True:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "passthrough",
                    "violation": "TI artifact uses passthrough mode — raw payload forwarding is forbidden; an input_contract must be declared",
                    "fix": "Remove passthrough: true and declare an explicit input_contract",
                })

            # Ingress normalization is the declared input contract (by reference).
            input_contract = fm.get("input_contract")
            if not input_contract or (isinstance(input_contract, dict) and len(input_contract) == 0):
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "input_contract",
                    "violation": "TI artifact must declare a non-empty input_contract — no passthrough payloads permitted",
                    "fix": "Add an input_contract with at least one field declaration",
                })

        elif artifact_type == "TE":
            # Egress normalization is the declared output_contract (projection).
            has_projection = bool(fm.get("output_contract")) or any(fm.get(k) for k in _TE_PROJECTION_KEYS)
            if not has_projection:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "output_contract",
                    "violation": "TE artifact must declare a projection (output_contract) — raw execution result passthrough is forbidden",
                    "fix": "Add an output_contract projecting the exposed result fields",
                })

    return {
        "assert_count": transport_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
