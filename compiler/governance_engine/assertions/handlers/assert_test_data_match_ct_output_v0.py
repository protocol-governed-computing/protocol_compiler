"""
ASSERT_TEST_DATA_MATCH_CT_OUTPUT_V0 Handler

Validates TEST_DATA expected outputs match target CT output contract.
"""

from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify TEST_DATA expected keys match CT output contracts.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains artifacts_by_fqdn mapping

    Returns:
        {
            "assert_count": int,
            "violations": list[dict]
        }
    """
    violations = []
    artifacts_by_fqdn = compilation_context["artifacts_by_fqdn"]

    # Filter to TEST_DATA artifacts only
    test_data_artifacts = [
        a for a in artifacts
        if a.get("frontmatter", {}).get("artifact_kind") == "TEST_DATA"
    ]

    for td_artifact in test_data_artifacts:
        fqdn = td_artifact["fqdn_id"]
        frontmatter = td_artifact.get("frontmatter", {})

        # Extract test_target (CT FQDN)
        test_target = frontmatter.get("test_target")
        if not test_target:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0",
                "message": "TEST_DATA artifact missing test_target field",
                "fix": "Add test_target field specifying the CT FQDN being tested"
            })
            continue

        # Load CT artifact
        if test_target not in artifacts_by_fqdn:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0",
                "message": f"Test target CT not found in compilation graph: {test_target}",
                "fix": f"Ensure CT artifact '{test_target}' exists and is included in build"
            })
            continue

        ct_artifact = artifacts_by_fqdn[test_target]
        ct_governed_by = ct_artifact.get("frontmatter", {}).get("governed_by", [])

        if not ct_governed_by:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0",
                "message": f"Target CT missing governed_by field: {test_target}",
                "fix": f"Add governed_by field to CT artifact '{test_target}'"
            })
            continue

        # Load CC artifact
        cc_fqdn = ct_governed_by[0]
        if cc_fqdn not in artifacts_by_fqdn:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0",
                "message": f"CT's governing CC not found in compilation graph: {cc_fqdn}",
                "fix": f"Ensure CC artifact '{cc_fqdn}' exists and is included in build"
            })
            continue

        cc_artifact = artifacts_by_fqdn[cc_fqdn]
        cc_output = cc_artifact.get("frontmatter", {}).get("output", {})

        if not cc_output:
            # CC has no output declaration - skip check
            continue

        # Expected keys from CC
        expected_keys = set(cc_output.keys())

        # Check test cases
        test_cases = frontmatter.get("test_cases", [])
        for idx, test_case in enumerate(test_cases):
            expected_output = test_case.get("expected", {})

            if not expected_output:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.layers::INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0",
                    "message": f"Test case {idx} missing expected output field",
                    "fix": f"Add 'expected' field to test case {idx} with expected output values"
                })
                continue

            actual_keys = set(expected_output.keys())
            missing_keys = expected_keys - actual_keys
            extra_keys = actual_keys - expected_keys

            if missing_keys or extra_keys:
                msg_parts = []
                if missing_keys:
                    msg_parts.append(f"missing keys: {sorted(missing_keys)}")
                if extra_keys:
                    msg_parts.append(f"extra keys: {sorted(extra_keys)}")

                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.layers::INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0",
                    "message": f"Test case {idx}: expected output keys don't match CC contract ({', '.join(msg_parts)})",
                    "fix": f"Update test case {idx} expected output to match CC '{cc_fqdn}' output contract: {sorted(expected_keys)}"
                })

    if violations:
        return {
            "assert_count": len(test_data_artifacts),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(test_data_artifacts),
        "violations": [],
        "status": "PASSED"
    }
