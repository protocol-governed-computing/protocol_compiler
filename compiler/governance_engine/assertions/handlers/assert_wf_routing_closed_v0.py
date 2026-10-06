"""
ASSERT_WF_ROUTING_CLOSED_V0

Enforces INVARIANT_WF_ROUTING_CLOSED_V0 at compile time (`4a` GC-15).

A workflow node that execution can reach must answer every outcome the thing it runs declares:
a contract node every code in its contract's `result_status_contract.allowed`, an intent node every
outcome its intent declares. Routing and endings are both declared in a node's `next`, so an
outcome absent from `next` has neither, and execution would refuse there (`3a` EX-5). Construction
refuses it first, so that a sealed workflow cannot present itself as complete while it carries the
gap.

Reach and what each node runs are precomputed by the compiler from S2's resolution (`wf_routing`);
this handler only checks. A superseded workflow is not in force and has no dispatch entry (`4e`
SU-7), so execution cannot reach any of its nodes and it is not checked. A node whose contract or
intent this build cannot see is left to the reference checks.
"""

from compiler.atoms.force import in_force

RULE = "workflow::INVARIANT_WF_ROUTING_CLOSED_V0"


def _frontmatter(fqdn: str, compilation_context: dict) -> dict | None:
    local = compilation_context.get("artifacts_by_fqdn", {}) or {}
    if fqdn in local:
        return local[fqdn].get("frontmatter", {}) or {}
    return (compilation_context.get("imported_frontmatter", {}) or {}).get(fqdn)


def _declared(node: dict, compilation_context: dict) -> set[str] | None:
    """The outcomes of what a node runs, read from the artifact S2 resolved it to."""
    runs = node.get("runs")
    fm = _frontmatter(runs, compilation_context) if runs else None
    if fm is None:
        return None
    core = fm.get("core", {}) or {}
    if node.get("type") == "CC":
        return set((core.get("result_status_contract", {}) or {}).get("allowed", []) or [])
    if node.get("type") == "IN":
        outcomes = core.get("outcomes")
        return set(outcomes) if isinstance(outcomes, dict) and outcomes else None
    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    # A pure rule checker: what each node runs and which nodes execution can reach are resolved
    # by the compiler (`wf_routing`, from S2's resolver), never again here.
    wf_routing = compilation_context.get("wf_routing")
    if wf_routing is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "workflow::ASSERT_WF_ROUTING_CLOSED_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing wf_routing",
                "fix": "Compiler must pre-compute workflow routing before the assert phase",
            }],
            "status": "FAILED",
        }

    violations = []
    wf_count = 0
    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue
        if not in_force(artifact.get("frontmatter", {}) or {}):
            continue
        wf_count += 1
        fqdn = artifact.get("fqdn_id", "unknown")
        routing = wf_routing.get(fqdn) or {"nodes": {}, "reachable": []}
        for key in routing["reachable"]:
            node = routing["nodes"][key]
            declared = _declared(node, compilation_context)
            if not declared:
                continue
            for code in sorted(declared - set(node["next"])):
                violations.append({
                    "fqdn": fqdn,
                    "rule": RULE,
                    "message": (
                        f"Node '{key}' is reachable and runs {node['runs']}, which can end with "
                        f"'{code}'; the node declares neither a route nor an ending for it (4a GC-15)"
                    ),
                    "fix": f"Add '{code}: <node or EXIT_*>' to node '{key}' next",
                })

    return {
        "assert_count": wf_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
