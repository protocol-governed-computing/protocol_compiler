"""
ASSERT_TOPOLOGY_CONTRACT_CLOSED_V1

Enforces INVARIANT_TOPOLOGY_CONTRACT_CLOSED_V1 at compile time.

Routing is a lookup with two answers, and a decision is a capability's. V0 admitted a third answer,
an evaluation target, and counted its `on_true`/`on_false` as exits. Nothing ran it: execution read
the answer as going on, so a contract routing to one ended with its last step's outcome whatever the
condition said. The Collatz gate could not fail that way.

For every CC in force:

- every value in a step's `on_result` is `continue` or `exit`, or the build is refused by contract,
  step and answer;
- the CC declares no `evaluation` block;
- the codes that can exit the topology equal `result_status_contract.allowed` exactly. A code exits
  when a step routes it as `exit`, or when the last step routes it as `continue`.

A CC not in force (`INVARIANT_SUPERSEDED_NOT_IN_FORCE_V0`) is not checked. It runs nowhere, and it
stays in the record as it was sealed — a stood-down contract may still carry the condition its
successor replaced.
"""

from compiler.atoms.force import in_force

RULE = "execution_topology::INVARIANT_TOPOLOGY_CONTRACT_CLOSED_V1"
ROUTING_ANSWERS = ("continue", "exit")


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    cc_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue
        frontmatter = artifact.get("frontmatter", {}) or {}
        if not in_force(frontmatter):
            continue

        cc_count += 1
        fqdn = artifact.get("fqdn_id", "unknown")
        core = frontmatter.get("core", {}) or {}
        pipeline = core.get("pipeline", [])
        allowed = set((core.get("result_status_contract", {}) or {}).get("allowed", []))

        if core.get("evaluation"):
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
                "message": (
                    f"declares an evaluation block ({', '.join(sorted(core['evaluation']))}) — a "
                    "condition over a step's result is run by nothing; routing is a lookup"
                ),
                "fix": "Make the decision with a capability, a step whose outcome is routed",
            })

        if not isinstance(pipeline, list):
            continue

        steps = [s for s in pipeline if isinstance(s, dict)]
        last = steps[-1] if steps else None
        reachable: set[str] = set()

        for step in steps:
            on_result = step.get("on_result") or {}
            if not isinstance(on_result, dict):
                continue
            for code, answer in on_result.items():
                if answer not in ROUTING_ANSWERS:
                    violations.append({
                        "fqdn": fqdn,
                        "rule": RULE,
                        "message": (
                            f"step '{step.get('step')}' routes '{code}' to '{answer}' — a routing "
                            "answer is continue or exit, and anything else is performed by nothing"
                        ),
                        "fix": "Route the outcome to continue or exit; make any decision a capability's",
                    })
            for code in step.get("result_surface", []) or []:
                answer = on_result.get(code)
                if answer == "exit" or (step is last and answer == "continue"):
                    reachable.add(code)

        for code in sorted(reachable - allowed):
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
                "message": (
                    f"Topology can exit with '{code}' but '{code}' is not declared in "
                    "result_status_contract.allowed — uncontracted exit"
                ),
                "fix": (
                    f"Add '{code}' to result_status_contract.allowed, "
                    "or fix the routing so this code does not exit the CC"
                ),
            })

        for code in sorted(allowed - reachable):
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
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
