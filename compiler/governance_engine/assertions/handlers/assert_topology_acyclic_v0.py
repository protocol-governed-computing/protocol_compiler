"""
ASSERT_TOPOLOGY_ACYCLIC_V0 Handler

Validates that the compiled semantic topology graph contains no
dependency cycles. Reads pre-computed cycle analysis from compiler.

CONSTITUTIONAL: Governed topology is always a DAG. Cycles are
structurally inadmissible.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate topology acyclicity via pre-computed cycle analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed topology_cycle_analysis

    Returns:
        Standardized result dict with assert_count, violations, status
    """
    violations = []

    cycle_analysis = compilation_context.get("topology_cycle_analysis")

    if cycle_analysis is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "fb.topology::ASSERT_TOPOLOGY_ACYCLIC_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing topology_cycle_analysis",
                "fix": "Compiler must pre-compute cycle analysis before assert phase"
            }],
            "status": "FAILED"
        }

    if cycle_analysis.get("has_cycle"):
        violations.append({
            "fqdn": "fb.topology::ASSERT_TOPOLOGY_ACYCLIC_V0",
            "rule": "fb.topology::INVARIANT_TOPOLOGY_ACYCLIC_V0",
            "message": "Circular dependency detected in compiled topology graph",
            "fix": "Remove circular dependency between artifacts"
        })

    node_count = cycle_analysis.get("node_count", 0)

    return {
        "assert_count": node_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED"
    }
