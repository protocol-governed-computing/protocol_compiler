"""
ASSERT_CT_TEST_DATA_OUTCOME_DECLARED_V0 Handler

Enforces INVARIANT_CT_TEST_DATA_OUTCOME_DECLARED_V0 at compile time.

Validates that every test case in every TEST_DATA artifact declares an explicit
expected_outcome field. The expected_outcome is the behavioral contract between
the test author and the CT implementation — it states whether the CT is expected
to succeed (SUCCESS) or raise a VIOLATION.

Omitting expected_outcome is a compile-time violation. The compiler must never
silently default an absent value to SUCCESS: that masks VIOLATION test cases and
produces conformance tests that never exercise the failure path.

Valid expected_outcome values: SUCCESS, VIOLATION.
"""

import re
from typing import Any

import yaml

_CASE_BLOCK_PATTERN = re.compile(
    r"### Case \d+: (\w+).*?```yaml\n(.*?)```",
    re.DOTALL,
)

_VALID_OUTCOMES = frozenset({"SUCCESS", "VIOLATION"})


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify every TEST_DATA case declares an explicit expected_outcome.

    Args:
        artifacts:           All validated artifacts from the graph.
        compilation_context: Compilation context (unused here).

    Returns:
        {"assert_count": int, "violations": list[dict], "status": str}
    """
    violations = []
    td_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "TEST_DATA":
            continue

        td_count += 1
        td_fqdn = artifact.get("fqdn_id", "unknown")
        content = artifact.get("content", "")

        if not content:
            continue

        case_blocks = _CASE_BLOCK_PATTERN.findall(content)
        if not case_blocks:
            continue

        for case_id, case_yaml_str in case_blocks:
            try:
                case_dict = yaml.safe_load(case_yaml_str)
            except Exception as e:
                violations.append({
                    "fqdn": td_fqdn,
                    "rule": "capability_transforms::INVARIANT_CT_TEST_DATA_OUTCOME_DECLARED_V0",
                    "message": (
                        f"TEST_DATA '{td_fqdn}' case '{case_id}' has unparseable yaml: {e}"
                    ),
                    "fix": f"Fix the yaml syntax in case '{case_id}'.",
                })
                continue

            if not isinstance(case_dict, dict):
                continue

            outcome = case_dict.get("expected_outcome")

            if outcome is None:
                violations.append({
                    "fqdn": td_fqdn,
                    "rule": "capability_transforms::INVARIANT_CT_TEST_DATA_OUTCOME_DECLARED_V0",
                    "message": (
                        f"TEST_DATA '{td_fqdn}' case '{case_id}' is missing "
                        f"expected_outcome. Every test case must explicitly declare "
                        f"whether the CT is expected to succeed or raise a VIOLATION."
                    ),
                    "fix": (
                        f"Add 'expected_outcome: SUCCESS' or 'expected_outcome: VIOLATION' "
                        f"to case '{case_id}' in '{td_fqdn}'."
                    ),
                })
            elif outcome not in _VALID_OUTCOMES:
                violations.append({
                    "fqdn": td_fqdn,
                    "rule": "capability_transforms::INVARIANT_CT_TEST_DATA_OUTCOME_DECLARED_V0",
                    "message": (
                        f"TEST_DATA '{td_fqdn}' case '{case_id}' declares "
                        f"expected_outcome '{outcome}' which is not a valid value. "
                        f"Valid values are: {sorted(_VALID_OUTCOMES)}."
                    ),
                    "fix": (
                        f"Change expected_outcome in case '{case_id}' to one of: "
                        f"{sorted(_VALID_OUTCOMES)}."
                    ),
                })

    return {
        "assert_count": td_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
