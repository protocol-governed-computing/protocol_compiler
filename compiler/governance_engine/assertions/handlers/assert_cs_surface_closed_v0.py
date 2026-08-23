"""
ASSERT_CS_SURFACE_CLOSED_V0 Handler

Validates CS surface closure:
1. All discovered CS are explicitly declared
2. All declared CS have runtime implementations
3. No excess declarations (declared but not discovered)
"""

from pathlib import Path
from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify CS surface is closed (declared == executable).

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains artifacts_by_fqdn, layer_resolver, assert_artifact

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []

    # Get layer category map from compilation context (STRUCTURE-driven)
    layer_category_map = compilation_context.get("layer_category_map", {})

    # Evaluate the rule FROM the artifact being asserted.
    # The compiler is a generic evaluator: it reads the allowed surface and the
    # scope from the current ASSERT artifact itself, never substituting another
    # (e.g. platform) artifact. This keeps every surface-closure ASSERT
    # authoritative — a domain ASSERT governs its own domain surface.
    current_assert = compilation_context.get("current_assert_artifact")
    if current_assert:
        assert_fm = current_assert.get("frontmatter", {})
    else:
        # Defensive fallback: locate this handler's platform assert by code.
        assert_fm = {}
        for artifact in artifacts:
            if artifact.get("frontmatter", {}).get("artifact_code") == "ASSERT_CS_SURFACE_CLOSED_V0":
                assert_fm = artifact.get("frontmatter", {})
                break

    allowed_cs = set(assert_fm.get("allowed_capability_side_effects", []))
    scope = set(assert_fm.get("scope", {}).get("applies_to", []))

    def _in_scope(cs_artifact: dict) -> bool:
        """A CS is governed by this ASSERT if its layer matches the ASSERT scope.

        Domain scope (e.g. BLOCKCHAIN) matches the CS's layer_code directly.
        PLATFORM scope matches any CS whose layer is a platform layer.
        """
        layer_code = cs_artifact.get("layer_code")
        if layer_code in scope:
            return True
        if "PLATFORM" in scope and layer_category_map.get(layer_code) == "platform":
            return True
        return False

    # Extract all discovered CS artifacts
    # Note: CS artifacts may have artifact_kind="capability_side_effect" OR cs_code field
    discovered_cs = set()
    cs_artifacts = []

    for artifact in artifacts:
        frontmatter = artifact.get("frontmatter", {})

        # CS identification by canonical artifact_kind (Kind Vocabulary) — the sole discriminator.
        is_cs = frontmatter.get("artifact_kind") == "CAPABILITY_SIDE_EFFECT"

        if is_cs:
            fqdn = artifact["fqdn_id"]
            discovered_cs.add(fqdn)
            cs_artifacts.append(artifact)

    # CHECK 1: No Undeclared CS (within this ASSERT's scope)
    # Every discovered CS governed by this ASSERT must be explicitly declared in
    # its allowed list. There is no intrinsic-by-existence exemption: closure is
    # enforced from the artifact, for platform and domain surfaces alike.
    assert_code = assert_fm.get("artifact_code", "the ASSERT artifact")
    for cs_artifact in cs_artifacts:
        if not _in_scope(cs_artifact):
            continue
        cs_fqdn = cs_artifact["fqdn_id"]
        if cs_fqdn not in allowed_cs:
            violations.append({
                "fqdn": cs_fqdn,
                "rule": "capability_side_effects::INVARIANT_CS_SURFACE_CLOSED_V1",
                "message": "Undeclared CS (exists in registry but not in allowed_capability_side_effects)",
                "fix": f"Add '{cs_fqdn}' to allowed_capability_side_effects in {assert_code}"
            })

    # CHECK 2: No Excess Declarations
    # Every declared CS must be discovered. Skipped only for a PLATFORM-scoped
    # ASSERT during a domain build, where platform CS are legitimately absent.
    is_domain_build = compilation_context.get("is_domain_build", False)
    skip_excess = is_domain_build and "PLATFORM" in scope

    if not skip_excess:
        for allowed_fqdn in allowed_cs:
            if allowed_fqdn not in discovered_cs:
                violations.append({
                    "fqdn": allowed_fqdn,
                    "rule": "capability_side_effects::INVARIANT_CS_SURFACE_CLOSED_V1",
                    "message": "Declared CS not found (in allowed list but not discovered in registry)",
                    "fix": f"Remove '{allowed_fqdn}' from allowed_capability_side_effects (CS no longer exists)"
                })

    # CHECK 3: No Missing Implementations
    # All discovered CS must have runtime implementation (either RB binding or runtime.py)

    # Extract all CS bindings from RB artifacts
    rb_bound_cs = _extract_rb_bindings(artifacts)

    for artifact in cs_artifacts:
        if not _in_scope(artifact):
            continue
        fqdn = artifact["fqdn_id"]
        # The CS code (identity) is carried by the artifact, not by a legacy cs_code machine-block
        # field; it equals the artifact_code. Used only for RB-binding / runtime resolution below.
        cs_code = artifact.get("artifact_code")

        # Check if CS is bound in an RB artifact (domain CS pattern)
        if cs_code in rb_bound_cs:
            # CS is bound in RB - valid (no need to check runtime.py)
            continue

        # Check if runtime implementation exists (platform CS pattern)
        runtime_exists, runtime_path = _check_runtime_exists(cs_code)

        if not runtime_exists:
            violations.append({
                "fqdn": fqdn,
                "rule": "capability_side_effects::INVARIANT_CS_SURFACE_CLOSED_V1",
                "message": f"Missing runtime implementation (not bound in RB and no runtime.py at {runtime_path})",
                "fix": f"Either: (1) Bind CS in RB artifact, OR (2) Implement runtime.py at {runtime_path}"
            })

    # Return result
    if violations:
        # Add debug info about discovered CS
        debug_info = {
            "discovered_cs_count": len(discovered_cs),
            "discovered_cs_fqdns": sorted(list(discovered_cs)),
            "allowed_cs_count": len(allowed_cs),
            "allowed_cs_fqdns": sorted(list(allowed_cs)),
            "rb_bound_cs_count": len(rb_bound_cs),
            "violation_breakdown": {}
        }

        # Breakdown violations by type
        for v in violations:
            violation_type = v["message"].split("(")[0].strip()
            debug_info["violation_breakdown"].setdefault(violation_type, 0)
            debug_info["violation_breakdown"][violation_type] += 1

        return {
            "assert_count": len(cs_artifacts),
            "violations": violations,
            "status": "FAILED",
            "debug": debug_info
        }

    return {
        "assert_count": len(cs_artifacts),
        "violations": [],
        "status": "PASSED"
    }


def _extract_rb_bindings(artifacts: list[dict]) -> set[str]:
    """
    Extract all CS bindings from RB artifacts.

    Returns:
        Set of CS codes that are bound in RB artifacts
    """
    rb_bound_cs = set()

    for artifact in artifacts:
        # Check if this is an RB artifact
        # Use artifact_type (normalized) instead of artifact_kind
        artifact_type = artifact.get("artifact_type")

        if artifact_type != "RB":
            continue

        # Extract bindings from RB artifact
        frontmatter = artifact.get("frontmatter", {})
        core = frontmatter.get("core", {})
        bindings = core.get("bindings", {})

        # Add all bound CS codes
        # CS artifacts are identified by FQDN or code pattern: namespace::CS_*_V0 or CS_*_V0
        for bound_key in bindings.keys():
            if not isinstance(bound_key, str):
                continue

            # Extract CS code from FQDN (namespace::CS_X_V0 -> CS_X_V0)
            if "::" in bound_key:
                # FQDN format - extract the code part
                cs_code_part = bound_key.split("::")[-1]
                if cs_code_part.startswith("CS_"):
                    rb_bound_cs.add(cs_code_part)
            elif bound_key.startswith("CS_"):
                # Short code format
                rb_bound_cs.add(bound_key)

    return rb_bound_cs


def _get_side_effects_implementation_root() -> Path:
    """
    Get side effects implementation root using LayerResolver (STRUCTURE_DISCOVERY_V0).

    REUSABLE_SIDE_EFFECTS registry_module resolves to pgs_side_effects/registry/.
    Implementation lives at the sibling path: pgs_side_effects/implementation/side_effects/.
    """
    from compiler.governance_engine.platform_root import cs_implementation_root
    return cs_implementation_root()


def _check_runtime_exists(cs_code: str) -> tuple[bool, Path]:
    """
    Check if runtime implementation exists for CS.

    Expected pattern:
        CS_X_V0 → pgs_side_effects/implementation/side_effects/{persistent,internal,external}/CS_X_V0/runtime.py

    Returns:
        (exists: bool, expected_path: Path)
    """
    # PGC flat layout: capability_side_effects/implementation/CS_X/runtime.py
    runtime_path = _get_side_effects_implementation_root() / cs_code / "runtime.py"
    return runtime_path.exists(), runtime_path
