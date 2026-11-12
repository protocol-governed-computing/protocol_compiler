"""
ASSERT_TRANSPORT_NO_WORKFLOW_SEMANTICS_V0 Handler

Validates that TI_ and TE_ artifacts do not contain execution orchestration
semantics: no CC/CT/CS references, no pipeline steps, no side effect declarations,
no retry logic targeting execution.

CONSTITUTIONAL: Pure rule checker — reads artifact set from context.
"""

import re

# Artifact code prefixes that belong to execution, not transport
_EXECUTION_PREFIXES = ("CC_", "CT_", "CS_")

# Keys that indicate pipeline/orchestration declarations
_PIPELINE_KEYS = {"pipeline", "steps", "chain", "pre_validate", "post_validate", "side_effects"}

# Keys indicating retry semantics targeting execution
_RETRY_KEYS = {"retry", "retry_policy", "resubmit", "re_admission", "backoff"}

# Regex to detect FQDN-style references to CC/CT/CS artifacts
_EXECUTION_REF_PATTERN = re.compile(r"\b(CC|CT|CS)_[A-Z0-9_]+")


def _scan_for_execution_refs(value, path: str, artifact_code: str, violations: list, assert_name: str) -> None:
    """Recursively scan for CC/CT/CS artifact references in any string value."""
    if isinstance(value, str):
        match = _EXECUTION_REF_PATTERN.search(value)
        if match:
            violations.append({
                "assert": assert_name,
                "artifact": artifact_code,
                "field": path,
                "value": value,
                "violation": f"Transport artifact references execution artifact '{match.group()}' — transport must not participate in execution semantics",
                "fix": "Remove all CC/CT/CS references from transport artifacts; move orchestration logic to workflow artifacts",
            })
    elif isinstance(value, dict):
        for k, v in value.items():
            full_path = f"{path}.{k}"
            # Check for forbidden orchestration keys
            if k in _PIPELINE_KEYS:
                violations.append({
                    "assert": assert_name,
                    "artifact": artifact_code,
                    "field": full_path,
                    "key": k,
                    "violation": f"Transport artifact declares forbidden orchestration key '{k}'",
                    "fix": "Remove pipeline/step/chain declarations from transport artifacts",
                })
            elif k in _RETRY_KEYS:
                violations.append({
                    "assert": assert_name,
                    "artifact": artifact_code,
                    "field": full_path,
                    "key": k,
                    "violation": f"Transport artifact declares forbidden retry/re-admission key '{k}' — transport may retry delivery but not execution",
                    "fix": "Remove execution-targeting retry semantics from transport artifacts",
                })
            _scan_for_execution_refs(v, full_path, artifact_code, violations, assert_name)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_for_execution_refs(item, f"{path}[{i}]", artifact_code, violations, assert_name)


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate TI_ and TE_ artifacts for absence of execution semantics.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    transport_count = 0

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in ("TI", "TE"):
            continue

        artifact_code = artifact.get("artifact_code", "UNKNOWN")
        transport_count += 1
        frontmatter = artifact.get("frontmatter", {})

        _scan_for_execution_refs(
            frontmatter,
            "frontmatter",
            artifact_code,
            violations,
            "ASSERT_TRANSPORT_NO_WORKFLOW_SEMANTICS_V0",
        )

    return {
        "assert_count": transport_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
