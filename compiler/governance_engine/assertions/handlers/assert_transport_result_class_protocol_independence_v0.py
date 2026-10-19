"""ASSERT_TRANSPORT_RESULT_CLASS_PROTOCOL_INDEPENDENCE_V0 Handler

Every Result Class a TE emits (via result_classification + default_result_class) MUST be a
governed, protocol-neutral class — never an HTTP status, RPC error code, or other external
representation. Pure rule checker — reads the artifact set from context.
"""

# CONSTITUTION_TRANSPORT_EGRESS_V0. NOT_FOUND (the admitted request whose SUBJECT is absent) and
# OPERATION_NOT_FOUND (an identity resolving to no registered TI/TE) are deliberately distinct.
_GOVERNED_RESULT_CLASSES = {
    "SUCCESS", "VIOLATION", "UNAUTHORIZED", "NOT_FOUND", "OPERATION_NOT_FOUND",
    "EXECUTION_FAILURE",
}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    te_count = 0
    for artifact in artifacts:
        if artifact.get("artifact_type") != "TE":
            continue
        te_count += 1
        code = artifact.get("artifact_code", "UNKNOWN")
        fm = artifact.get("frontmatter", {})

        declared: set[str] = set()
        classification = fm.get("result_classification") or {}
        if isinstance(classification, dict):
            declared.update(str(v) for v in classification.values())
        default_class = fm.get("default_result_class")
        if default_class:
            declared.add(str(default_class))

        foreign = declared - _GOVERNED_RESULT_CLASSES
        if foreign:
            violations.append({
                "assert": "ASSERT_TRANSPORT_RESULT_CLASS_PROTOCOL_INDEPENDENCE_V0",
                "artifact": code,
                "violation": (f"TE declares result classes carrying non-governed/protocol semantics: "
                              f"{sorted(foreign)}"),
                "fix": f"Map outcomes only to governed classes: {sorted(_GOVERNED_RESULT_CLASSES)}",
            })

    return {
        "assert_count": te_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
