"""
ASSERT_TOPOLOGY_CONTRACT_CLOSED_V0

Enforces INVARIANT_TOPOLOGY_CONTRACT_CLOSED_V0 at compile time.

Validates that the union of all status codes that can exit a CC execution
topology exactly matches result_status_contract.allowed. Two failure modes:

- Uncontracted exit: a code exits the topology but is not in allowed
- Unreachable code: a code is in allowed but no execution path exits with it

A code is reachable as a CC exit when ANY of the following hold:
1. A step routes it as 'exit' in on_result (and the code is in that step's result_surface)
2. The LAST step routes it as 'continue' (last-step continue exits the CC)
3. An evaluation block names it as on_true or on_false

Codes routed as 'continue' in non-last steps remain in-pipeline — they do not
exit the CC. Codes routed to an evaluation target (e.g. SUCCESS: evaluate_cap)
exit via the evaluation's on_true/on_false outcomes, not directly.

Validation scope: CC-level contract closure.
Execution topology validation is structural, not semantic.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    cc_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue

        cc_count += 1
        fqdn = artifact.get("fqdn_id", "unknown")
        core = artifact.get("frontmatter", {}).get("core", {})
        pipeline = core.get("pipeline", [])
        result_contract = core.get("result_status_contract", {})
        allowed = set(result_contract.get("allowed", []))

        if not isinstance(pipeline, list):
            continue

        reachable: set[str] = set()

        # Collect evaluation outcomes — these are always CC exits
        evaluations = core.get("evaluation", {})
        if isinstance(evaluations, dict):
            for eval_def in evaluations.values():
                if isinstance(eval_def, dict):
                    if on_true := eval_def.get("on_true"):
                        reachable.add(on_true)
                    if on_false := eval_def.get("on_false"):
                        reachable.add(on_false)

        # Walk pipeline to determine per-step exit contributions
        all_steps = [s for s in pipeline if isinstance(s, dict)]
        last_step = all_steps[-1] if all_steps else None

        for step in all_steps:
            is_last = step is last_step
            surface = set(step.get("result_surface", []))
            on_result = step.get("on_result") or {}
            if not isinstance(on_result, dict):
                continue

            for code in surface:
                routing = on_result.get(code)
                if routing == "exit":
                    reachable.add(code)
                elif is_last and routing == "continue":
                    # Last-step continue exits the CC with this code
                    reachable.add(code)
                # routing to an evaluation target: exits captured above via evaluation.on_true/on_false
                # routing == "continue" in non-last step: stays in pipeline, does not exit

        # Uncontracted exits: reachable but not in allowed
        uncontracted = reachable - allowed
        for code in sorted(uncontracted):
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.invariants::INVARIANT_TOPOLOGY_CONTRACT_CLOSED_V0",
                "message": (
                    f"Topology can exit with '{code}' but '{code}' is not declared in "
                    "result_status_contract.allowed — uncontracted exit"
                ),
                "fix": (
                    f"Add '{code}' to result_status_contract.allowed, "
                    "or fix the routing so this code does not exit the CC"
                ),
            })

        # Unreachable contract codes: in allowed but no execution path exits with them
        unreachable = allowed - reachable
        for code in sorted(unreachable):
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.invariants::INVARIANT_TOPOLOGY_CONTRACT_CLOSED_V0",
                "message": (
                    f"Contract declares '{code}' in result_status_contract.allowed but "
                    "no execution path exits the CC with this code — unreachable contract code"
                ),
                "fix": (
                    f"Remove '{code}' from result_status_contract.allowed, "
                    "or add an exit route for it in the topology"
                ),
            })

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
