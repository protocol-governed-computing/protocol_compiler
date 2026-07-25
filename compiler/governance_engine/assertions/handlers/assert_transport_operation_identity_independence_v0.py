"""ASSERT_TRANSPORT_OPERATION_IDENTITY_INDEPENDENCE_V0 Handler

Every TI declares a stable Operation Identity that MUST exist and MUST NOT equal a workflow
identity (nor its own bound invocation target). The public operation name is re-pointable;
the target is not. Pure rule checker — reads the artifact set from context.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []

    wf_ids: set[str] = set()
    for a in artifacts:
        if a.get("artifact_type") == "WF":
            if a.get("artifact_code"):
                wf_ids.add(a["artifact_code"])
            if a.get("fqdn_id"):
                wf_ids.add(a["fqdn_id"])

    ti_count = 0
    for artifact in artifacts:
        if artifact.get("artifact_type") != "TI":
            continue
        ti_count += 1
        code = artifact.get("artifact_code", "UNKNOWN")
        fm = artifact.get("frontmatter", {})
        operation = fm.get("operation")
        if not operation:
            violations.append({
                "assert": "ASSERT_TRANSPORT_OPERATION_IDENTITY_INDEPENDENCE_V0",
                "artifact": code,
                "violation": "TI artifact must declare a stable Operation Identity (operation)",
                "fix": "Add operation: <stable public identity>",
            })
            continue
        if operation in wf_ids:
            violations.append({
                "assert": "ASSERT_TRANSPORT_OPERATION_IDENTITY_INDEPENDENCE_V0",
                "artifact": code,
                "violation": f"Operation Identity {operation!r} MUST NOT equal a workflow identity",
                "fix": "Use a protocol-neutral operation name distinct from any WF identity",
            })
        target = (fm.get("handler") or {}).get("workflow")
        if target and operation == target:
            violations.append({
                "assert": "ASSERT_TRANSPORT_OPERATION_IDENTITY_INDEPENDENCE_V0",
                "artifact": code,
                "violation": f"Operation Identity {operation!r} MUST NOT equal its invocation target",
                "fix": "The operation name is public and stable; the target is re-pointable — keep them distinct",
            })

    return {
        "assert_count": ti_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
