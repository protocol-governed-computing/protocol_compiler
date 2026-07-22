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
        core = artifact.get("frontmatter", {}).get("core", {})

        if artifact_type == "TI":
            # Check for forbidden passthrough
            if core.get("passthrough") is True:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "core.passthrough",
                    "violation": "TI artifact uses passthrough mode — raw payload forwarding is forbidden; admission_schema must be declared",
                    "fix": "Remove passthrough: true and declare an explicit core.admission_schema",
                })

            # Check for admission_schema
            admission_schema = core.get("admission_schema")
            if not admission_schema:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "core.admission_schema",
                    "violation": "TI artifact must declare core.admission_schema — no passthrough payloads permitted",
                    "fix": "Add core.admission_schema with at least one field declaration",
                })
            elif not isinstance(admission_schema, dict) or len(admission_schema) == 0:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "core.admission_schema",
                    "violation": "TI core.admission_schema must contain at least one field declaration",
                    "fix": "Declare at least one field in core.admission_schema",
                })

        elif artifact_type == "TE":
            # Check for any projection declaration
            has_projection = any(core.get(k) for k in _TE_PROJECTION_KEYS)
            if not has_projection:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "core",
                    "violation": "TE artifact must declare a projection schema (response_schema, projection_schema, or projection) — raw execution result passthrough is forbidden",
                    "fix": "Add core.response_schema with at least status and body field declarations",
                })

    return {
        "assert_count": transport_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
