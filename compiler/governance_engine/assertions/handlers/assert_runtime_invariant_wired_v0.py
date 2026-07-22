"""
ASSERT_RUNTIME_INVARIANT_WIRED_V0 Handler

Verifies that every runtime-enforced business INVARIANT — one whose
`core.enforcement_stage` contains "runtime_outcome" — is bound to a real
enforcement point in the protocol, so that the declaration is authoritative
rather than decorative.

PGS enforces runtime business invariants through the EXISTING capability-contract
outcome-routing mechanism: a CC emits a non-SUCCESS outcome which the workflow DAG
routes to a terminal node, and the trace examiner classifies the run as a
BUSINESS_VIOLATION. The runtime stays generic — it is not changed by this design.
This compile-time assertion only proves, from artifact data alone, that each
declared runtime invariant is wired to that mechanism:

  1. the enforcing CC exists and declares the violation outcome in its result_surface;
  2. the enforcing WF contains that CC as a node and routes the violation outcome
     to the declared terminal node;
  3. the terminal node exists in that WF.

It reads only projected artifacts (WF/CC frontmatter); it requires no compiler
change. This is the runtime-side analogue of the surface-closure assertions:
meaning lives in the INVARIANT artifact, the mechanism is generic, the compiler
verifies the binding.
"""

from typing import Any

RUNTIME_STAGE = "runtime_outcome"
RULE = "fb.topology::INVARIANT_RUNTIME_INVARIANT_WIRED_V0"


def _code(fqdn: str) -> str:
    """Bare artifact/node code from an FQDN (namespace::CODE -> CODE)."""
    return fqdn.split("::")[-1] if fqdn else ""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []

    # Index artifacts by FQDN and by bare code for resolution.
    by_fqdn: dict[str, dict] = {}
    by_code: dict[str, dict] = {}
    for a in artifacts:
        fq = a.get("fqdn_id", "")
        if fq:
            by_fqdn[fq] = a
            by_code[_code(fq)] = a

    # Discover runtime-enforced invariants (enforcement_stage contains runtime_outcome).
    runtime_invariants = [
        a for a in artifacts
        if RUNTIME_STAGE in (a.get("frontmatter", {}).get("core", {}).get("enforcement_stage", []) or [])
    ]

    for inv in runtime_invariants:
        inv_fqdn = inv.get("fqdn_id") or inv.get("artifact_code") or "unknown"
        core = inv.get("frontmatter", {}).get("core", {})
        rb = core.get("runtime_binding", {}) or {}

        cc_ref = rb.get("enforced_by", "")
        wf_ref = rb.get("enforcing_workflow", "")
        outcome = rb.get("violation_outcome", "")
        terminal = _code(rb.get("terminal_node", ""))
        store = rb.get("over_store", "")

        # CHECK 0: binding completeness
        missing = [
            k for k, v in (
                ("enforced_by", cc_ref),
                ("enforcing_workflow", wf_ref),
                ("violation_outcome", outcome),
                ("terminal_node", terminal),
                ("over_store", store),
            ) if not v
        ]
        if missing:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"Runtime invariant missing binding field(s): {', '.join(missing)}",
                "fix": "Declare core.runtime_binding.{enforced_by, enforcing_workflow, "
                       "violation_outcome, terminal_node, over_store}",
            })
            continue

        # CHECK 1: enforcing CC exists and declares the violation outcome
        cc = by_fqdn.get(cc_ref) or by_code.get(_code(cc_ref))
        if not cc:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"Enforcing CC not found: {cc_ref}",
                "fix": f"Declare runtime_binding.enforced_by as an existing CC FQDN",
            })
            continue

        cc_outcomes: set[str] = set()
        for step in cc.get("frontmatter", {}).get("core", {}).get("pipeline", []):
            cc_outcomes.update(step.get("result_surface", []))
        if outcome not in cc_outcomes:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"Enforcing CC {_code(cc_ref)} does not declare violation_outcome "
                           f"'{outcome}' in its result_surface",
                "fix": f"Add '{outcome}' to a result_surface in {_code(cc_ref)}, or correct "
                       f"runtime_binding.violation_outcome",
            })

        # CHECK 2: enforcing WF exists, contains the CC, and routes the outcome to the terminal
        wf = by_fqdn.get(wf_ref) or by_code.get(_code(wf_ref))
        if not wf:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"Enforcing workflow not found: {wf_ref}",
                "fix": "Declare runtime_binding.enforcing_workflow as an existing WF FQDN",
            })
            continue

        nodes = wf.get("frontmatter", {}).get("core", {}).get("nodes", {})
        cc_node = nodes.get(_code(cc_ref))
        if not cc_node:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"Enforcing CC {_code(cc_ref)} is not a node in {_code(wf_ref)}",
                "fix": f"Add {_code(cc_ref)} to {_code(wf_ref)}, or correct the binding",
            })
            continue

        routed = cc_node.get("next", {}).get(outcome)
        if routed != terminal:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"{_code(wf_ref)} routes {_code(cc_ref)} on '{outcome}' to "
                           f"'{routed}', but the invariant declares terminal_node '{terminal}'",
                "fix": "Align runtime_binding.terminal_node with the WF routing for this outcome",
            })

        # CHECK 3: terminal node exists in the WF
        if terminal not in nodes:
            violations.append({
                "fqdn": inv_fqdn,
                "rule": RULE,
                "message": f"Terminal node '{terminal}' is not declared in {_code(wf_ref)}",
                "fix": f"Declare terminal node '{terminal}' in {_code(wf_ref)}",
            })

    if violations:
        return {
            "assert_count": len(runtime_invariants),
            "violations": violations,
            "status": "FAILED",
        }

    return {
        "assert_count": len(runtime_invariants),
        "violations": [],
        "status": "PASSED",
    }
