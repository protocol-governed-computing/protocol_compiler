"""
ASSERT_PROTOCOL_SURFACE_CLOSED_V0 Handler

Validates all FQDN references resolve to existing artifacts.
"""

import re
from pathlib import Path
from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify all FQDN references resolve to existing artifacts.

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

    # Extract all FQDNs in compiled graph
    available_fqdns = set(artifacts_by_fqdn.keys())

    for artifact in artifacts:
        fqdn = artifact["fqdn_id"]

        # Extract all FQDN references from artifact
        references = _extract_fqdn_references(artifact)

        # Check each reference exists
        for ref_fqdn in references:
            if ref_fqdn not in available_fqdns:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.layers::INVARIANT_PROTOCOL_SURFACE_CLOSED_V0",
                    "message": f"Dangling FQDN reference (artifact not found): {ref_fqdn}",
                    "fix": f"Either: (1) Create missing artifact '{ref_fqdn}', OR (2) Remove reference from {fqdn}"
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


def _extract_fqdn_references(artifact: dict) -> set[str]:
    """
    Extract all FQDN references from artifact.

    Scans:
    - governed_by
    - structure
    - runtime_binding
    - pipeline transforms
    - Any FQDN-shaped string (layer::artifact pattern)
    """
    references = set()
    frontmatter = artifact.get("frontmatter", {})

    # Direct reference fields
    reference_fields = ["governed_by", "structure", "runtime_binding"]

    for field in reference_fields:
        value = frontmatter.get(field)
        if value is None:
            continue

        # Handle list or single value
        values = value if isinstance(value, list) else [value]

        for ref in values:
            if isinstance(ref, str) and "::" in ref:
                references.add(ref)

    # Pipeline transforms (for CC artifacts)
    if frontmatter.get("artifact_kind") == "CC":
        pipeline = frontmatter.get("pipeline", [])

        for step in pipeline:
            if not isinstance(step, dict):
                continue

            transform = step.get("transform")
            if transform and "::" in transform:
                references.add(transform)

    # Fallback: Scan for any FQDN-shaped strings
    # Pattern: word.word::WORD_WITH_UNDERSCORES_V0 (supports dotted namespaces)
    fqdn_pattern = r'\b([a-z._]+)::([A-Z_0-9]+_V\d+)\b'

    # Convert frontmatter to string for scanning
    import json
    artifact_str = json.dumps(frontmatter)

    for match in re.finditer(fqdn_pattern, artifact_str):
        fqdn_ref = f"{match.group(1)}::{match.group(2)}"
        references.add(fqdn_ref)

    return references
