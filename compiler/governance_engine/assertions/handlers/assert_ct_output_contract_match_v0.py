"""
ASSERT_CT_OUTPUT_CONTRACT_MATCH_V0 Handler

Validates CT output keys match CC contract declarations.
"""

import ast
import re
from pathlib import Path
from typing import Any

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver
from compiler.governance_engine.structure.resolution.path_registry import bootstrap


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify CT outputs match CC contracts.

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

    # Filter to CT artifacts only
    ct_artifacts = [
        a for a in artifacts
        if a.get("frontmatter", {}).get("artifact_kind") == "CT"
    ]

    for ct_artifact in ct_artifacts:
        fqdn = ct_artifact["fqdn_id"]
        frontmatter = ct_artifact.get("frontmatter", {})
        governed_by_list = frontmatter.get("governed_by", [])

        # CT must have governed_by
        if not governed_by_list:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_CT_OUTPUT_CONTRACT_MATCH_V0",
                "message": "CT artifact missing governed_by field",
                "fix": "Add governed_by field specifying the governing CC FQDN"
            })
            continue

        # Extract CC FQDN (first governed_by)
        cc_fqdn = governed_by_list[0]
        if cc_fqdn not in artifacts_by_fqdn:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_CT_OUTPUT_CONTRACT_MATCH_V0",
                "message": f"Governing CC artifact not found in compilation graph: {cc_fqdn}",
                "fix": f"Ensure CC artifact '{cc_fqdn}' exists and is included in build"
            })
            continue

        # Load CC artifact
        cc_artifact = artifacts_by_fqdn[cc_fqdn]
        cc_frontmatter = cc_artifact.get("frontmatter", {})
        cc_output = cc_frontmatter.get("output", {})

        if not cc_output:
            # CC has no output declaration - skip check
            continue

        # Expected output keys from CC
        expected_keys = set(cc_output.keys())

        # Find CT implementation file
        artifact_code = frontmatter.get("artifact_code")
        ct_impl_path = _find_ct_implementation(artifact_code)

        if not ct_impl_path or not ct_impl_path.exists():
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_CT_OUTPUT_CONTRACT_MATCH_V0",
                "message": f"CT implementation file not found for {artifact_code}",
                "fix": f"Create implementation file for CT '{artifact_code}' in transforms layer atoms/ or molecules/"
            })
            continue

        # Parse return keys from implementation
        actual_keys = _extract_return_keys(ct_impl_path)

        if actual_keys is None:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_CT_OUTPUT_CONTRACT_MATCH_V0",
                "message": f"No return statement found in CT implementation {ct_impl_path.name}",
                "fix": "Add return statement with dict output in execute() function"
            })
            continue

        # Check for mismatch
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
                "rule": "governance.layers::INVARIANT_CT_OUTPUT_CONTRACT_MATCH_V0",
                "message": f"CT output doesn't match CC contract ({', '.join(msg_parts)})",
                "fix": f"Update CT implementation to return exact keys from CC '{cc_fqdn}' output contract: {sorted(expected_keys)}"
            })

    if violations:
        return {
            "assert_count": len(ct_artifacts),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(ct_artifacts),
        "violations": [],
        "status": "PASSED"
    }


def _find_ct_implementation(artifact_code: str) -> Path | None:
    """Find CT implementation file (flat PGC layout: capability_transforms/implementation/ct_x.py)."""
    from compiler.governance_engine.platform_root import ct_implementation_root
    impl_path = ct_implementation_root() / f"{artifact_code.lower()}.py"
    return impl_path if impl_path.exists() else None


def _extract_return_keys(impl_path: Path) -> set[str] | None:
    """Extract keys from return dict in execute() function."""
    try:
        source = impl_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Find execute() function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "execute":
                # Find all return statements
                return_keys = set()

                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.Return) and sub_node.value:
                        # Return value should be dict
                        if isinstance(sub_node.value, ast.Dict):
                            for key in sub_node.value.keys:
                                if isinstance(key, ast.Constant):
                                    return_keys.add(key.value)

                if return_keys:
                    return return_keys

        return None

    except Exception:
        return None
