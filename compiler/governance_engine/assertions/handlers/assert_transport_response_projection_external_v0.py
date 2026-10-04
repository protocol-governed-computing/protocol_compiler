"""ASSERT_TRANSPORT_RESPONSE_PROJECTION_EXTERNAL_V0 Handler

Mapping a governed Result Class to an external representation (HTTP status, RPC error, CLI
exit code) is adapter-owned and MUST NOT appear in a TE. A TE that declares any such
projection key collapses the transport/adapter separation. Pure rule checker.
"""

# Keys that would embed external-protocol response projection into a TE (forbidden).
_PROTOCOL_PROJECTION_KEYS = {
    "http", "http_status", "status_code", "status_map",
    "exit_code", "rpc_error", "response_projection", "protocol_projection",
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
        present = _PROTOCOL_PROJECTION_KEYS & set(fm.keys())
        if present:
            violations.append({
                "assert": "ASSERT_TRANSPORT_RESPONSE_PROJECTION_EXTERNAL_V0",
                "artifact": code,
                "violation": (f"TE declares external-protocol response projection {sorted(present)} — "
                              f"projection is adapter-owned, never in a TE"),
                "fix": "Remove protocol projection from the TE; map Result Class to a representation in the adapter",
            })

    return {
        "assert_count": te_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
