"""
ASSERT_WF_EXECUTION_PATH_VALID_V0 Handler

Validates WF execution graph structure (DAG-based):
1. Valid start_node (exists and is type IN or TI)
2. All nodes reachable from start_node
3. No cycles (DAG constraint)
4. All node.next references valid
5. EXIT nodes are terminal
6. All CC nodes reference existing CC artifacts

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all WF execution graphs against pre-computed structural analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed wf_execution_graphs

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],  # Standardized schema
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    wf_count = 0

    # STRICT INVERSION OF CONTROL: Compiler must provide complete context
    wf_graphs = compilation_context.get("wf_execution_graphs")

    if wf_graphs is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "fb.workflow::ASSERT_WF_EXECUTION_PATH_VALID_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing wf_execution_graphs",
                "fix": "Compiler must pre-compute WF execution graphs before assert phase"
            }],
            "status": "FAILED"
        }

    # Check rules against pre-computed structure
    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_count += 1
        fqdn = artifact["fqdn_id"]
        graph_result = wf_graphs.get(fqdn)

        if not graph_result:
            violations.append({
                "fqdn": fqdn,
                "rule": "fb.workflow::INVARIANT_WF_EXECUTION_PATH_VALID_V0",
                "message": "Missing execution graph analysis for WF artifact",
                "fix": "Compiler must analyze all WF artifacts"
            })
            continue

        # Translate structural violations to standardized rule violations
        if graph_result.get("status") == "FAILED":
            for structural_violation in graph_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "fb.workflow::INVARIANT_WF_EXECUTION_PATH_VALID_V0",
                    "message": structural_violation.get("violation", "Unknown WF structural violation"),
                    "fix": structural_violation.get("fix", "Fix WF execution graph structure")
                })

    # Return standardized result
    if violations:
        return {
            "assert_count": wf_count,
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": wf_count,
        "violations": [],
        "status": "PASSED"
    }
