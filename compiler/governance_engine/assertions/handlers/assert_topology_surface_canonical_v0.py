"""
ASSERT_TOPOLOGY_SURFACE_CANONICAL_V0

Enforces INVARIANT_TOPOLOGY_SURFACE_CANONICAL_V0 at compile time.

Validates that every CC pipeline step's result_surface exactly matches the
canonical_surface declared in the governing SURFACE_CONTRACT artifact for that
step's {capability_id, op} combination.

Lookup strategy (in order):
1. Exact match: {capability_id, op} → SURFACE_CONTRACT
2. Prefix match: capability_id starts with capability_id_prefix + op matches

Steps whose capability has no governing contract are silently skipped — this
assertion is opt-in per capability family, not a blanket requirement.

Capability extraction:
- Steps with `side_effect:` field → capability_id from FQDN (after ::), op from `op:` field
- Steps with `transform:` field → capability_id from FQDN (after ::), op = "TRANSFORM"

Skipped steps:
- Steps with `transform:` AND `on_ct_result:` → these use explicit CT-to-CC result remapping;
  their result_surface is CC-level domain codes, not the CT's canonical surface. Canonical
  surface validation does not apply to remapped steps.

Validation scope: semantic surface legitimacy.
Structural routing coverage is enforced by ASSERT_TOPOLOGY_ROUTING_COMPLETE_V0.
"""


def _extract_capability_id(fqdn: str) -> str:
    """Extract bare capability_id from FQDN (everything after ::)."""
    if "::" in fqdn:
        return fqdn.split("::")[-1].strip()
    return fqdn.strip()


def _build_contract_lookup(artifacts: list[dict]) -> tuple[dict, list]:
    """
    Build lookup tables from SURFACE_CONTRACT artifacts.

    Returns:
        exact_lookup: {(capability_id, op): (canonical_surface_set, contract_code)}
        prefix_lookup: [(prefix, op, canonical_surface_set, contract_code)]
    """
    exact_lookup = {}
    prefix_lookup = []

    for artifact in artifacts:
        if artifact.get("artifact_type") != "SURFACE":
            continue

        fm = artifact.get("frontmatter", {})
        op = fm.get("op", "")
        canonical_surface = set(fm.get("canonical_surface", []))
        contract_code = fm.get("surface_contract_code", artifact.get("artifact_code", "unknown"))

        # Exact matches via governs list
        for cap_id in fm.get("governs", []):
            exact_lookup[(cap_id, op)] = (canonical_surface, contract_code)

        # Prefix match
        if prefix := fm.get("capability_id_prefix"):
            prefix_lookup.append((prefix, op, canonical_surface, contract_code))

    return exact_lookup, prefix_lookup


def _lookup_contract(
    capability_id: str,
    op: str,
    exact_lookup: dict,
    prefix_lookup: list,
) -> tuple[set, str] | None:
    """
    Look up canonical surface for a given (capability_id, op).

    Returns (canonical_surface_set, contract_code) or None if no contract governs this pair.
    """
    # Exact match first
    if result := exact_lookup.get((capability_id, op)):
        return result

    # Prefix match fallback
    for prefix, contract_op, canonical_surface, contract_code in prefix_lookup:
        if op == contract_op and capability_id.startswith(prefix):
            return (canonical_surface, contract_code)

    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    cc_count = 0
    governed_steps = 0

    exact_lookup, prefix_lookup = _build_contract_lookup(artifacts)

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue

        cc_count += 1
        fqdn = artifact.get("fqdn_id", "unknown")
        core = artifact.get("frontmatter", {}).get("core", {})
        pipeline = core.get("pipeline", [])

        if not isinstance(pipeline, list):
            continue

        for step in pipeline:
            if not isinstance(step, dict):
                continue

            step_id = step.get("step") or "unknown"

            # Determine capability_id and op from step
            if side_effect := step.get("side_effect"):
                capability_id = _extract_capability_id(str(side_effect))
                op = str(step.get("op", ""))
            elif transform := step.get("transform"):
                # Steps with on_ct_result use explicit CT-to-CC result remapping.
                # Their result_surface is CC-level domain codes, not the CT canonical surface.
                # Skip canonical surface validation for these steps.
                if step.get("on_ct_result"):
                    continue
                capability_id = _extract_capability_id(str(transform))
                op = "TRANSFORM"
            else:
                # No capability binding — TOPOLOGY_CAPABILITY_REFERENCE_UNIQUE governs this
                continue

            # Look up governing contract
            contract_result = _lookup_contract(capability_id, op, exact_lookup, prefix_lookup)
            if contract_result is None:
                # No contract governs this capability+op — skip silently
                continue

            canonical_surface, contract_code = contract_result
            governed_steps += 1

            declared_surface = set(step.get("result_surface", []))

            # Missing codes: in canonical but absent from declared
            missing = canonical_surface - declared_surface
            for code in sorted(missing):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "execution_topology::INVARIANT_TOPOLOGY_SURFACE_CANONICAL_V0",
                    "contract": contract_code,
                    "message": (
                        f"Step '{step_id}' result_surface missing '{code}' "
                        f"— required by {contract_code} for {capability_id} {op}"
                    ),
                    "fix": f"Add '{code}' to step '{step_id}' result_surface",
                })

            # Extra codes: declared but not in canonical
            extra = declared_surface - canonical_surface
            for code in sorted(extra):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "execution_topology::INVARIANT_TOPOLOGY_SURFACE_CANONICAL_V0",
                    "contract": contract_code,
                    "message": (
                        f"Step '{step_id}' result_surface declares '{code}' "
                        f"— not in canonical surface of {contract_code} for {capability_id} {op}"
                    ),
                    "fix": (
                        f"Remove '{code}' from step '{step_id}' result_surface, "
                        f"or update {contract_code} if the capability genuinely produces this code"
                    ),
                })

    return {
        "assert_count": cc_count,
        "governed_steps": governed_steps,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
