"""
ASSERT_IN_WORKFLOW_BINDING_V0 Handler

Validates that:
1. Every IN artifact declares core.workflow pointing to a resolvable WF artifact
2. No two IN artifacts bind to the same workflow (one-to-one: IN → WF)

The binding is declared on the IN side: IN.core.workflow = WF FQDN.
WF node names (e.g. "entry") are structural graph labels, not IN artifact references.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from collections import defaultdict


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate IN artifact workflow bindings.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused; all data from artifacts)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []

    # Build index of declared WF artifact codes (bare code and FQDN)
    wf_artifact_codes: set[str] = set()
    wf_fqdn_ids: set[str] = set()
    for a in artifacts:
        if a.get("artifact_type") == "WF":
            code = a.get("artifact_code")
            fqdn = a.get("fqdn_id")
            if code:
                wf_artifact_codes.add(code)
            if fqdn:
                wf_fqdn_ids.add(fqdn)

    # workflow_ref → [in_codes] for uniqueness check
    wf_to_ins: dict[str, list[str]] = defaultdict(list)
    in_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "IN":
            continue

        in_code = artifact.get("artifact_code", "UNKNOWN")
        in_count += 1

        core = artifact.get("frontmatter", {}).get("core", {})
        wf_ref = core.get("workflow")

        if not wf_ref:
            violations.append({
                "assert": "ASSERT_IN_WORKFLOW_BINDING_V0",
                "artifact": in_code,
                "violation": "IN artifact must declare core.workflow binding",
                "fix": "Add core.workflow: <WF FQDN> to declare target workflow",
            })
            continue

        # Accept both bare code and FQDN references
        wf_to_ins[wf_ref].append(in_code)

        # Check resolution: accept bare code or full FQDN
        wf_bare = wf_ref.split("::")[-1] if "::" in wf_ref else wf_ref
        if wf_bare not in wf_artifact_codes and wf_ref not in wf_fqdn_ids:
            violations.append({
                "assert": "ASSERT_IN_WORKFLOW_BINDING_V0",
                "artifact": in_code,
                "workflow": wf_ref,
                "violation": f"IN core.workflow '{wf_ref}' does not resolve to a declared WF artifact",
                "fix": "Declare the target WF artifact or fix the FQDN reference",
            })

    # Uniqueness: each WF may be bound by at most one IN
    for wf_ref, in_list in wf_to_ins.items():
        if len(in_list) > 1:
            violations.append({
                "assert": "ASSERT_IN_WORKFLOW_BINDING_V0",
                "workflow": wf_ref,
                "in_artifacts": in_list,
                "violation": (
                    f"Workflow '{wf_ref}' is bound by {len(in_list)} IN artifacts: {in_list}. "
                    "Each workflow must have at most one IN binding."
                ),
                "fix": "Create separate workflows or consolidate IN artifacts",
            })

    return {
        "assert_count": in_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
