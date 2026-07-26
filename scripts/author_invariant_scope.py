"""Stage 1 — author concrete scope.applies_to on every invariant.

Establishes the single declared authority for invariant applicability. The vocabulary
is closed and every token is concrete: executable/instantiable kinds, platform-produced
governance/structural kinds, and honest non-artifact build scopes. There is no "all"
token — an invariant governing every kind enumerates them.

Applicability (domain vs platform) is DERIVED downstream by intersecting applies_to with
the domain-instantiated kind set; it is never declared here.

The scope of each invariant is the artifact kind(s) its handler actually inspects — the
subject of enforcement, not the invariant's name. Authored explicitly per invariant
because most handlers filter by NodeKind or typed iteration and cannot be read off
mechanically.

Usage:
    python scripts/author_invariant_scope.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / "platform" / "registry"

MACHINE = re.compile(
    r"(?P<head>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<tail>\n```)",
    re.MULTILINE | re.DOTALL,
)

# Closed scope vocabulary. No ALL_ARTIFACTS, no PLATFORM.
EXECUTABLE = {"WF", "CC", "CS", "CT", "RB", "AC", "IN", "EV", "TI", "TE"}
GOVERNANCE_STRUCTURAL = {"INVARIANT", "CONSTITUTION", "STRUCTURE", "SURFACE", "VOCAB", "SCHEMA"}
BUILD_SCOPE = {"COMPILER", "TEST_DATA", "SNAPSHOT"}
VOCAB = EXECUTABLE | GOVERNANCE_STRUCTURAL | BUILD_SCOPE

# Every artifact kind — for invariants that genuinely govern all of them (identity /
# reference / hash / vocabulary hygiene). Enumerated, not tokenized.
ALL_KINDS = sorted(EXECUTABLE | GOVERNANCE_STRUCTURAL)

# Explicit per-invariant scope. The subject each invariant's enforcement inspects.
SCOPE = {
    # --- authority: governs actors and execution authority ---
    "INVARIANT_ACTOR_AUTHORITY_SEPARATION_V0": ["AC"],
    "INVARIANT_AUTHORITY_STATE_WELL_FORMED_V0": ["AC"],
    "INVARIANT_IDENTITY_AUTHORITY_SEPARATION_V0": ["AC"],
    "INVARIANT_AUTHORITY_REQUIRED_FOR_EXECUTION_V0": ["WF", "CC"],
    "INVARIANT_NO_AMBIENT_AUTHORITY_V0": ["WF", "CC", "CT", "CS"],
    "INVARIANT_NO_RUNTIME_AUTHORIZATION_V0": ["WF", "CC"],
    "INVARIANT_NO_WORKFLOW_AUTHORIZATION_LOGIC_V0": ["WF"],
    "INVARIANT_TRACE_AUTHORITY_BINDING_REQUIRED_V0": ["WF"],
    # --- actor ---
    "INVARIANT_AC_DECLARATION_WELL_FORMED_V0": ["AC"],
    # --- capability transforms ---
    "INVARIANT_ATOM_OUTPUT_PURITY_V0": ["CT"],
    "INVARIANT_CT_OUTPUT_CONTRACT_MATCH_V0": ["CT"],
    "INVARIANT_CT_SURFACE_CLOSED_V1": ["CT"],
    "INVARIANT_CT_TEST_DATA_OUTCOME_DECLARED_V0": ["CT"],
    "INVARIANT_IMPLEMENTATION_ADMISSIBLE_V0": ["CT", "CS"],
    # --- capability side effects ---
    "INVARIANT_CS_ISOLATED_EXECUTION_V0": ["CS"],
    "INVARIANT_CS_SURFACE_CLOSED_V1": ["CS"],
    "INVARIANT_CS_TRACEABLE_V0": ["CS"],
    # --- capability contracts ---
    "INVARIANT_CC_CAPABILITY_BINDING_VALID_V0": ["CC"],
    "INVARIANT_CC_INPUTS_SATISFIED_V0": ["CC"],
    "INVARIANT_CC_NO_IMPLICIT_CHAINING_V0": ["CC"],
    "INVARIANT_CC_NO_MISSING_DEPENDENCIES_V0": ["CC"],
    "INVARIANT_CC_NO_UNUSED_OUTPUTS_V0": ["CC"],
    "INVARIANT_CC_STORAGE_OP_CONFORMANCE_V0": ["CC"],
    # --- runtime bindings ---
    "INVARIANT_BINDING_INTEGRITY_V0": ["RB"],
    "INVARIANT_BINDING_SURFACE_CLOSED_V0": ["RB"],
    "INVARIANT_RB_BINDING_POLICY_CONFORMANCE_V0": ["RB"],
    "INVARIANT_RB_CS_ONLY_V0": ["RB"],
    "INVARIANT_RB_NO_LOGIC_V0": ["RB"],
    # --- intents ---
    "INVARIANT_IN_NO_EXECUTION_LOGIC_V0": ["IN"],
    "INVARIANT_IN_SCHEMA_REQUIRED_V0": ["IN"],
    "INVARIANT_IN_WORKFLOW_BINDING_V0": ["IN", "WF"],
    # --- events ---
    "INVARIANT_EV_APPEND_ONLY_V0": ["EV"],
    "INVARIANT_EV_SCHEMA_REQUIRED_V0": ["EV"],
    # --- workflows ---
    "INVARIANT_WF_CC_ONLY_NODES_V0": ["WF"],
    "INVARIANT_WF_ENTRY_INTENT_V0": ["WF"],
    "INVARIANT_WF_EXECUTION_PATH_VALID_V0": ["WF"],
    "INVARIANT_WF_NODE_KEY_BINDING_UNIQUE_V0": ["WF"],
    # --- topology: governs the executable graph (WF/CC/CT/CS/RB) ---
    "INVARIANT_TOPOLOGY_ACYCLIC_V0": ["WF", "CC", "CT", "CS", "RB"],
    "INVARIANT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0": ["WF", "CC"],
    "INVARIANT_TOPOLOGY_CAPABILITY_REFERENCE_UNIQUE_V0": ["CC", "CT", "CS"],
    "INVARIANT_TOPOLOGY_CONTRACT_CLOSED_V0": ["CC", "CT", "CS"],
    "INVARIANT_TOPOLOGY_IMMUTABLE_AFTER_COMPILATION_V0": ["WF", "CC", "CT", "CS", "RB"],
    "INVARIANT_TOPOLOGY_INPUT_REFERENCE_DECLARED_V0": ["WF", "CC"],
    "INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V0": ["WF"],
    "INVARIANT_TOPOLOGY_STEP_DECLARED_V0": ["WF"],
    "INVARIANT_TOPOLOGY_STEP_ID_UNIQUE_V0": ["WF"],
    "INVARIANT_TOPOLOGY_SURFACE_CANONICAL_V0": ["CC", "CT", "CS"],
    "INVARIANT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0": ["WF", "TI", "TE"],
    "INVARIANT_NO_RUNTIME_TOPOLOGY_SYNTHESIS_V0": ["WF", "CC"],
    "INVARIANT_NO_SMART_EXECUTION_V0": ["WF", "CC", "CT", "CS"],
    "INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0": ["WF", "CC", "CT", "CS"],
    "INVARIANT_PROTOCOL_SURFACE_CLOSED_V0": ["WF", "CC", "CT", "CS", "RB"],
    # --- transport ---
    "INVARIANT_TRANSPORT_CANONICAL_NORMALIZATION_V0": ["TI", "TE"],
    "INVARIANT_TRANSPORT_NO_DYNAMIC_ROUTING_V0": ["TI", "TE"],
    "INVARIANT_TRANSPORT_NO_WORKFLOW_SEMANTICS_V0": ["TI", "TE"],
    "INVARIANT_TRANSPORT_TARGET_EXISTS_V0": ["TI", "TE", "WF"],
    # --- snapshot-scoped federation contracts (declared once per compiled snapshot) ---
    "INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V0": ["SNAPSHOT"],
    "INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0": ["SNAPSHOT"],
    "INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0": ["SNAPSHOT"],
    "INVARIANT_SECURITY_DOMAIN_DECLARED_V0": ["SNAPSHOT"],
    "INVARIANT_RUNTIME_INVARIANT_WIRED_V0": ["WF", "CC"],
    # --- conformance / test data ---
    "INVARIANT_CONFORMANCE_ASSERTION_MODE_VALID_V0": ["TEST_DATA"],
    "INVARIANT_TEST_DATA_MATCH_CT_OUTPUT_V0": ["TEST_DATA", "CT"],
    # --- identity / reference / vocabulary hygiene: genuinely every kind ---
    "INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0": ALL_KINDS,
    "INVARIANT_UNIQUE_ARTIFACT_ID_V0": ALL_KINDS,
    "INVARIANT_FQDN_ONLY_REFERENCES_V0": ALL_KINDS,
    "INVARIANT_NO_SHORT_NAME_REFERENCE_V0": ALL_KINDS,
    "INVARIANT_VOCABULARY_SYMBOLS_WELL_FORMED_V0": ALL_KINDS,
    "INVARIANT_SCHEMA_CONFORMANCE_V0": ["CT", "CS", "CC", "WF", "RB", "INVARIANT", "CONSTITUTION", "SURFACE"],
    # --- structural ---
    "INVARIANT_STRUCTURE_PATHS_WELL_FORMED_V0": ["STRUCTURE"],
    # --- compiler self-governance: platform-only by honest scope ---
    "INVARIANT_ARTIFACT_CONTENT_HASH_DECLARED_V0": ["COMPILER"],
    "INVARIANT_COMPILER_GOVERNANCE_DECLARED_V0": ["COMPILER"],
    "INVARIANT_COMPILER_NO_EXECUTION_V0": ["COMPILER"],
    "INVARIANT_HANDLER_REGISTRY_CLOSED_V0": ["COMPILER"],
    # --- governance-artifact invariants: subject a domain never natively carries ---
    "INVARIANT_ASSERT_NOT_RUNTIME_REFERENCED_V0": ["WF", "CC", "CS", "CT", "RB"],
    "INVARIANT_ASSERT_PARITY_V0": ["INVARIANT"],
    "INVARIANT_GOVERNANCE_DECLARATION_RESOLVES_V0": ["CONSTITUTION", "INVARIANT"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = {p.stem: p for p in REGISTRY.rglob("INVARIANT_*.md")}
    missing_file = [c for c in SCOPE if c not in files]
    uncovered = [s for s in files if s not in SCOPE]
    bad_tokens = {c: [t for t in ts if t not in VOCAB] for c, ts in SCOPE.items()}
    bad_tokens = {c: t for c, t in bad_tokens.items() if t}

    if missing_file or uncovered or bad_tokens:
        if missing_file:
            print("SCOPE names an invariant with no file:", missing_file)
        if uncovered:
            print("invariant files with no SCOPE entry:", uncovered)
        if bad_tokens:
            print("scope tokens outside the closed vocabulary:", bad_tokens)
        return 2

    domain_kinds = EXECUTABLE
    dom = plat = 0
    for code, applies in SCOPE.items():
        path = files[code]
        text = path.read_text(encoding="utf-8")
        m = MACHINE.search(text)
        data = yaml.safe_load(m.group("y").rstrip())
        proj = data.setdefault("assert_projection", {})
        scope = proj.setdefault("scope", {})
        scope["applies_to"] = list(applies)
        is_domain = bool(set(applies) & domain_kinds)
        dom += is_domain
        plat += not is_domain
        if not args.dry_run:
            body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                                  allow_unicode=True, width=100).rstrip()
            path.write_text(
                text[: m.start()] + m.group("head") + body + m.group("tail") + text[m.end():],
                encoding="utf-8",
            )

    verb = "would author" if args.dry_run else "authored"
    print(f"  {verb} scope on {len(SCOPE)} invariants")
    print(f"  domain-applicable: {dom}   platform-only: {plat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())