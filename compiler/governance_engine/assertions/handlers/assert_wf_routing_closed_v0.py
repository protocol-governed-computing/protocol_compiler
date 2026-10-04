"""
ASSERT_WF_ROUTING_CLOSED_V0

Enforces INVARIANT_WF_ROUTING_CLOSED_V0 at compile time (`4a` GC-15).

A workflow node that execution can reach must answer every outcome the thing it runs declares:
a contract node every code in its contract's `result_status_contract.allowed`, an intent node every
outcome its intent declares. Routing and endings are both declared in a node's `next`, so an
outcome absent from `next` has neither, and execution would refuse there (`3a` EX-5). Construction
refuses it first, so that a sealed workflow cannot present itself as complete while it carries the
gap.

Reach is traversal from `start_node` over `next`. A superseded workflow is not in force and has no
dispatch entry (`4e` SU-7), so execution cannot reach any of its nodes and it is not checked. A
node whose contract or intent this build cannot see is left to the reference checks.
"""

from compiler.atoms.force import in_force

RULE = "workflow::INVARIANT_WF_ROUTING_CLOSED_V0"


def _frontmatter(fqdn: str, compilation_context: dict) -> dict | None:
    local = compilation_context.get("artifacts_by_fqdn", {}) or {}
    if fqdn in local:
        return local[fqdn].get("frontmatter", {}) or {}
    return (compilation_context.get("imported_frontmatter", {}) or {}).get(fqdn)


def _reachable(nodes: dict, start: str) -> list[str]:
    seen: list[str] = []
    queue = [start]
    while queue:
        key = queue.pop(0)
        if key in seen or key not in nodes:
            continue
        seen.append(key)
        nxt = nodes[key].get("next", {}) if isinstance(nodes[key], dict) else {}
        queue.extend(v for v in (nxt or {}).values() if isinstance(v, str))
    return seen


def _declared(node: dict, namespace: str, compilation_context: dict) -> set[str] | None:
    code = node.get("code")
    if not isinstance(code, str):
        return None
    fqdn = code if "::" in code else f"{namespace}::{code}"
    fm = _frontmatter(fqdn, compilation_context)
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
    violations = []
    wf_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue
        frontmatter = artifact.get("frontmatter", {}) or {}
        if not in_force(frontmatter):
            continue
        wf_count += 1
        fqdn = artifact.get("fqdn_id", "unknown")
        namespace = artifact.get("namespace") or fqdn.split("::")[0]
        core = frontmatter.get("core", {}) or {}
        nodes = core.get("nodes", {}) or {}
        start = core.get("start_node")
        if not isinstance(nodes, dict) or not isinstance(start, str):
            continue

        for key in _reachable(nodes, start):
            node = nodes[key]
            declared = _declared(node, namespace, compilation_context)
            if not declared:
                continue
            routed = set((node.get("next", {}) or {}).keys())
            for code in sorted(declared - routed):
                violations.append({
                    "fqdn": fqdn,
                    "rule": RULE,
                    "message": (
                        f"Node '{key}' is reachable and runs {node.get('code')}, which can end with "
                        f"'{code}'; the node declares neither a route nor an ending for it (4a GC-15)"
                    ),
                    "fix": f"Add '{code}: <node or EXIT_*>' to node '{key}' next",
                })

    return {
        "assert_count": wf_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
