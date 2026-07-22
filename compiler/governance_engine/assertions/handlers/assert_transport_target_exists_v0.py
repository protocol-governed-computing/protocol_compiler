"""
ASSERT_TRANSPORT_TARGET_EXISTS_V0 Handler

Validates that every TI_ artifact declares an explicit workflow binding
and that the declared workflow exists in the compiled artifact set.

CONSTITUTIONAL: Pure rule checker — reads artifact set from context.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate TI_ artifact workflow target bindings.

    For every TI_ artifact:
    - core.workflow must be declared
    - The declared workflow (bare code or FQDN) must resolve to a WF artifact

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

    # Build index of declared WF artifact codes and FQDNs
    wf_codes: set[str] = set()
    wf_fqdns: set[str] = set()
    for a in artifacts:
        if a.get("artifact_type") == "WF":
            code = a.get("artifact_code")
            fqdn = a.get("fqdn_id")
            if code:
                wf_codes.add(code)
            if fqdn:
                wf_fqdns.add(fqdn)

    ti_count = 0
    for artifact in artifacts:
        if artifact.get("artifact_type") != "TI":
            continue

        ti_code = artifact.get("artifact_code", "UNKNOWN")
        ti_count += 1
        core = artifact.get("frontmatter", {}).get("core", {})
        wf_ref = core.get("workflow")

        if not wf_ref:
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "violation": "TI artifact must declare core.workflow binding",
                "fix": "Add core.workflow: <WF FQDN> to declare explicit target workflow",
            })
            continue

        # Reject dynamic references ($ prefix)
        if isinstance(wf_ref, str) and wf_ref.startswith("$"):
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "workflow": wf_ref,
                "violation": "TI core.workflow must be a static FQDN — dynamic references are forbidden",
                "fix": "Replace dynamic reference with explicit WF FQDN",
            })
            continue

        # Resolve: accept bare code or full FQDN
        wf_bare = wf_ref.split("::")[-1] if "::" in wf_ref else wf_ref
        if wf_bare not in wf_codes and wf_ref not in wf_fqdns:
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "workflow": wf_ref,
                "violation": f"TI core.workflow '{wf_ref}' does not resolve to a declared WF artifact",
                "fix": "Declare the target WF artifact or correct the FQDN reference",
            })

    return {
        "assert_count": ti_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
