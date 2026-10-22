"""
ASSERT_ADMISSION_COVERS_BINDINGS_V0 Handler

A workflow whose start node is an IN gate may bind, as `$.payload.<field>`, only fields the gate's
`core.inputs` declares. A field bound and not declared is admitted unchecked and then cannot be
resolved, so the gap surfaces at run time instead of as a refusal at the boundary.

A declared field that no node binds is not a violation: a gate may require a field for its own
determination or for accountability.

CONSTITUTIONAL: Pure rule checker over the build's own artifacts.
"""

import json
import re

RULE = "transport::INVARIANT_ADMISSION_COVERS_BINDINGS_V0"

PAYLOAD_REF = re.compile(r"\$\.payload\.([a-zA-Z_][a-zA-Z0-9_]*)")


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []
    gates = {a.get("fqdn_id"): a for a in artifacts if a.get("artifact_type") == "IN"}
    workflows = [a for a in artifacts if a.get("artifact_type") == "WF"]

    for wf in workflows:
        fqdn = wf.get("fqdn_id", "unknown")
        core = (wf.get("frontmatter", {}) or {}).get("core", {}) or {}
        nodes = core.get("nodes", {}) or {}
        start = nodes.get(core.get("start_node"), {}) or {}
        if start.get("type") != "IN":
            continue
        code = start.get("code") or core.get("start_node")
        gate = gates.get(start.get("fqdn_id")) or gates.get(f"{fqdn.split('::')[0]}::{code}")
        if gate is None:
            continue  # an unresolved gate is INVARIANT_IN_WORKFLOW_BINDING_V0's finding
        declared = set(((gate.get("frontmatter", {}) or {}).get("core", {}) or {}).get("inputs") or {})
        bound = set(PAYLOAD_REF.findall(json.dumps(nodes)))
        for field in sorted(bound - declared):
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
                "message": f"binds $.payload.{field}, which its gate {gate.get('fqdn_id')} does not declare",
                "fix": f"Declare '{field}' in {gate.get('fqdn_id')} core.inputs, or stop binding it",
            })

    return {
        "assert_count": len(workflows),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
