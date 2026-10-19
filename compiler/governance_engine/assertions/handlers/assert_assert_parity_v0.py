"""
ASSERT_ASSERT_PARITY_V0 Handler

Meta-registry validation: Ensures every INVARIANT has matching ASSERT (and vice versa).

Validation Rules:
1. Every INVARIANT_X_V0 must have matching ASSERT_X_V0
2. Every ASSERT_X_V0 must have matching INVARIANT_X_V0
3. Names must match exactly (excluding prefix)

Enforcement Levels:
- WARNING: Allows dev iteration (violations don't block build)
- ERROR: Strict enforcement (violations block build) - used in CI

This is meta-validation - registry validating itself.
Must run BEFORE artifact validation.
"""

from typing import Any
import os
import re


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate registry parity: INVARIANT ↔ ASSERT symmetry.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation metadata

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    invariants = {}
    asserts = {}

    # Collect INVARIANT and ASSERT artifacts
    # Use artifact_code prefix (not artifact_type) because INVARIANT nodes
    # are mapped to NodeKind.GOVERNANCE in the compiler graph and their
    # projected artifact_type is "GOVERNANCE", not "INVARIANT".
    for artifact in artifacts:
        artifact_code = artifact.get("artifact_code", "")
        fqdn = artifact.get("fqdn_id", "")

        if artifact_code.startswith("INVARIANT_"):
            # An invariant enforced by a NON-COMPILER mechanism has no same-named ASSERT, and is
            # exempt from INVARIANT<->ASSERT parity:
            #   runtime_outcome         — bound to a CC violation outcome and WF routing; verified
            #                             by ASSERT_RUNTIME_INVARIANT_WIRED_V0
            #   composition_conformance — evaluated by the assembler over the ASSEMBLED snapshot;
            #                             admitted by its own `composition_check` declaration
            # A compile-time handler for a composition-scoped rule could only ever see one domain
            # build, which is the opposite of the scope such a rule is about — the platform build
            # legitimately contains none of the artifacts the composition must carry.
            core = artifact.get("frontmatter", {}).get("core", {})
            stages = core.get("enforcement_stage", []) or []
            if {"runtime_outcome", "composition_conformance"} & set(stages):
                continue
            invariants[artifact_code] = fqdn
        elif artifact_code.startswith("ASSERT_"):
            asserts[artifact_code] = fqdn

    # Extract base names (remove INVARIANT_/ASSERT_ prefix)
    invariant_names = {}
    for code in invariants.keys():
        # Pattern: INVARIANT_{NAME}_V{N}
        match = re.match(r"INVARIANT_(.+)_(V\d+)$", code)
        if match:
            base_name = f"{match.group(1)}_{match.group(2)}"
            invariant_names[base_name] = code

    assert_names = {}
    for code in asserts.keys():
        # Pattern: ASSERT_{NAME}_V{N}
        match = re.match(r"ASSERT_(.+)_(V\d+)$", code)
        if match:
            base_name = f"{match.group(1)}_{match.group(2)}"
            assert_names[base_name] = code

    violations = []

    # Check for orphaned invariants (missing asserts)
    orphaned_invariants = set(invariant_names.keys()) - set(assert_names.keys())
    for base_name in sorted(orphaned_invariants):
        invariant_code = invariant_names[base_name]
        violations.append({
            "fqdn": invariants[invariant_code],
            "rule": "conformance::INVARIANT_ASSERT_PARITY_V0",
            "message": f"Orphaned INVARIANT (no matching ASSERT): {invariant_code}",
            "fix": f"Create matching ASSERT_{base_name}.md file with handler implementation"
        })

    # Check for orphaned asserts (missing invariants)
    orphaned_asserts = set(assert_names.keys()) - set(invariant_names.keys())
    for base_name in sorted(orphaned_asserts):
        assert_code = assert_names[base_name]
        violations.append({
            "fqdn": asserts[assert_code],
            "rule": "conformance::INVARIANT_ASSERT_PARITY_V0",
            "message": f"Orphaned ASSERT (no matching INVARIANT): {assert_code}",
            "fix": f"Create matching INVARIANT_{base_name}.md file or delete orphaned ASSERT"
        })

    # Determine enforcement level
    # Check for CI environment (CI=true or CI=1)
    is_ci = os.getenv("CI", "").lower() in ("true", "1")

    # Get assertion artifact to read enforcement level
    assert_artifact = compilation_context.get("current_assert_artifact")
    default_level = "WARNING"  # Default to dev-friendly mode

    if assert_artifact:
        enforcement = assert_artifact.get("frontmatter", {}).get("enforcement", {})
        ci_override = assert_artifact.get("frontmatter", {}).get("ci_override", {})

        if is_ci and "level" in ci_override:
            level = ci_override["level"]  # CI override takes precedence
        else:
            level = enforcement.get("level", default_level)
    else:
        level = default_level

    # Return result
    total_pairs = len(invariant_names) + len(assert_names)

    if violations:
        if level == "WARNING":
            # Dev mode: Warn but don't fail build
            return {
                "assert_count": total_pairs,
                "warnings": violations,
                "violations": [],
                "status": "PASSED_WITH_WARNINGS",
                "summary": {
                    "invariants": len(invariants),
                    "asserts": len(asserts),
                    "orphaned_invariants": len(orphaned_invariants),
                    "orphaned_asserts": len(orphaned_asserts)
                }
            }
        else:
            # CI/production mode: Hard fail
            return {
                "assert_count": total_pairs,
                "violations": violations,
                "status": "FAILED",
                "summary": {
                    "invariants": len(invariants),
                    "asserts": len(asserts),
                    "orphaned_invariants": len(orphaned_invariants),
                    "orphaned_asserts": len(orphaned_asserts)
                }
            }

    return {
        "assert_count": total_pairs,
        "violations": [],
        "status": "PASSED",
        "summary": {
            "invariants": len(invariants),
            "asserts": len(asserts),
            "matched_pairs": len(invariant_names)
        }
    }
