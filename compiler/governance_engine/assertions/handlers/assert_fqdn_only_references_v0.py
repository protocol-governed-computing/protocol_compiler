"""
ASSERT_FQDN_ONLY_REFERENCES_V0 Handler

Validates all artifact references use FQDN format (layer::artifact_code).
"""

import re
from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify all artifact references use FQDN format.

    Args:
        artifacts: All validated artifacts
        compilation_context: Not used

    Returns:
        {
            "assert_count": int,
            "violations": list[dict]
        }
    """
    violations = []

    # Reference fields to check
    reference_fields = [
        "governed_by",
        "structure",
        "runtime_binding",
    ]

    for artifact in artifacts:
        fqdn = artifact["fqdn_id"]
        frontmatter = artifact.get("frontmatter", {})

        # Check top-level reference fields
        for field in reference_fields:
            value = frontmatter.get(field)

            if value is None:
                continue

            # Handle list or single value
            values = value if isinstance(value, list) else [value]

            for ref in values:
                if not isinstance(ref, str):
                    continue

                # Check if FQDN format (contains ::)
                if "::" not in ref:
                    violations.append({
                        "fqdn": fqdn,
                        "rule": "fb.artifact::INVARIANT_FQDN_ONLY_REFERENCES_V0",
                        "message": f"Field '{field}' uses short name '{ref}' (missing layer prefix)",
                        "fix": f"Change '{ref}' to FQDN format: layer::{ref}"
                    })

        # Check pipeline transforms (for CC artifacts)
        if frontmatter.get("artifact_kind") == "CAPABILITY_CONTRACT":
            pipeline = (frontmatter.get("core") or {}).get("pipeline", [])

            for idx, step in enumerate(pipeline):
                if not isinstance(step, dict):
                    continue

                transform = step.get("transform")
                if transform and "::" not in transform:
                    violations.append({
                        "fqdn": fqdn,
                        "rule": "fb.artifact::INVARIANT_FQDN_ONLY_REFERENCES_V0",
                        "message": f"Pipeline step {idx} uses short name '{transform}' (missing layer prefix)",
                        "fix": f"Change '{transform}' to FQDN format: layer::{transform}"
                    })

    if violations:
        return {
            "assert_count": len(artifacts),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(artifacts),
        "violations": [],
        "status": "PASSED"
    }
