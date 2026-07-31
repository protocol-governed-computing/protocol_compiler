"""
ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0 Handler

Validates that:
- Every TI_ artifact declares a non-empty input_contract (no passthrough)
- Every TE_ artifact declares an output_contract projection (no raw result passthrough)

CONSTITUTIONAL: Pure rule checker — reads artifact set from context.
"""


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
        # Transport-Standard block shape (flat): TI declares `input_contract` (by reference);
        # TE declares `output_contract` (the projection).
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

            # Ingress normalization is the declared input contract. PRESENCE is the
            # declaration; an EMPTY contract is a legal and meaningful one — it declares that
            # the operation admits no input at all, which is the strongest normalization
            # possible, not the absence of one. Treating `{}` as undeclared would force a
            # parameterless operation to invent a field it does not have in order to be
            # governed, which is how contracts start lying.
            if "input_contract" not in fm or fm.get("input_contract") is None:
                violations.append({
                    "assert": "ASSERT_TRANSPORT_CANONICAL_NORMALIZATION_V0",
                    "artifact": artifact_code,
                    "field": "input_contract",
                    "violation": "TI artifact must declare an input_contract — no passthrough payloads permitted",
                    "fix": "Add an input_contract; declare `{}` if the operation admits no input",
                })

        elif artifact_type == "TE":
            # Egress normalization is the declared output_contract (projection).
            has_projection = bool(fm.get("output_contract"))
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
