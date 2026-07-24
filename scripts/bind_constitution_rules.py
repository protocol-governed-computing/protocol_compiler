"""Phase 2 migration — bind constitution rules to their enforcing invariants.

Two corrections, both explicit and reviewable:

  MODEL_FIX   A constitution declaring `compiler_enforced` while carrying rules that
              are genuinely process- or runtime-scoped. The rule is not wrong; the
              constitution's declared enforcement model is. Corrected to
              `process_and_compiler_enforced`.

  BINDINGS    A rule whose enforcing INVARIANT exists but was referenced by a bare
              ASSERT_ code, a stage name, or `TBD`. Bound to the invariant's FQDN.

Rules left unbound are the real enforcement deficit: a constitution declares them
and no invariant enforces them. They are deliberately not papered over with a
sentinel — the closed schema reports each one.

Usage:
    python scripts/bind_constitution_rules.py [--dry-run]
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
RULE_STATEMENT = re.compile(
    r"^## Rule Statement\s*\n+```yaml\s*\n(?P<y>.*?)\n```", re.MULTILINE | re.DOTALL
)

# Constitutions whose declared model understates their actual mix of enforcement.
MODEL_FIX = {
    "CONSTITUTION_GOVERNANCE_V0": "process_and_compiler_enforced",
    "CONSTITUTION_CRYPTOGRAPHIC_TRUST_V0": "process_and_compiler_enforced",
    "CONSTITUTION_EXECUTION_PLACEMENT_V0": "process_and_compiler_enforced",
    "CONSTITUTION_EXECUTION_SCHEDULING_V0": "process_and_compiler_enforced",
    "CONSTITUTION_SECURITY_DOMAIN_V0": "process_and_compiler_enforced",
}

# rule_id -> enforcing INVARIANT FQDN, or a non-compiler sentinel.
BINDINGS = {
    # Snapshot-contract declarations: one invariant per federation boundary.
    "TRUST_MODE_MUST_BE_DECLARED": "fb.cryptographic_trust::INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V0",
    "PLACEMENT_MUST_BE_DECLARED": "fb.execution_placement::INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0",
    "PLACEMENT_IMMUTABLE_AFTER_COMPILE": "fb.execution_placement::INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0",
    "REMOTE_EXECUTION_REQUIRES_CONTRACT": "fb.execution_placement::INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0",
    "SCHEDULING_MUST_BE_DECLARED": "fb.execution_scheduling::INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0",
    "PARALLEL_REQUIRES_EXPLICIT_AUTHORIZATION": "fb.execution_scheduling::INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0",
    "NON_BLOCKING_REQUIRES_EXPLICIT_AUTHORIZATION": "fb.execution_scheduling::INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0",
    "SECURITY_DOMAIN_MUST_BE_DECLARED": "fb.security_domain::INVARIANT_SECURITY_DOMAIN_DECLARED_V0",
    "CROSS_DOMAIN_FLOW_REQUIRES_AUTHORIZATION": "fb.security_domain::INVARIANT_SECURITY_DOMAIN_DECLARED_V0",
    # Capability surfaces: the _V0 codes these referenced were superseded by _V1.
    "CS_EXPLICIT_DECLARATION": "fb.topology::INVARIANT_CS_SURFACE_CLOSED_V1",
    "CS_IMPLEMENTATION_DECLARED": "fb.topology::INVARIANT_IMPLEMENTATION_ADMISSIBLE_V0",
    "CT_IMPLEMENTATION_DECLARED": "fb.topology::INVARIANT_IMPLEMENTATION_ADMISSIBLE_V0",
    "CT_EXPLICIT_IO": "fb.topology::INVARIANT_CT_SURFACE_CLOSED_V1",
    "CT_PURITY": "fb.topology::INVARIANT_ATOM_OUTPUT_PURITY_V0",
    "CT_NO_SIDE_EFFECTS": "fb.topology::INVARIANT_ATOM_OUTPUT_PURITY_V0",
    # Actor identity: only the authority-separation rule has an enforcing invariant.
    "AC_NO_AUTHORITY_SEMANTICS": "fb.authority::INVARIANT_ACTOR_AUTHORITY_SEPARATION_V0",
    # Invariant governance.
    "INVARIANT_MANDATORY_ENFORCEMENT": "fb.conformance::INVARIANT_ASSERT_PARITY_V0",
    # Trace rules are enforced by the runtime, not the compiler.
    "TRACE_OBLIGATED": "RUNTIME_ENFORCED",
    "TRACE_EXECUTION_PURITY": "RUNTIME_ENFORCED",
    "TRACE_EGRESS_SOLE_IO": "RUNTIME_ENFORCED",
    "TRACE_PATH_FROM_STRUCTURE": "RUNTIME_ENFORCED",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bound = models = 0
    unbound: list[tuple[str, str, str]] = []

    for path in sorted(REGISTRY.rglob("CONSTITUTION_*.md")):
        text = path.read_text(encoding="utf-8")
        m = MACHINE.search(text)
        if not m:
            continue
        data = yaml.safe_load(m.group("y").rstrip())
        if not isinstance(data, dict):
            continue

        notes = RULE_STATEMENT.search(text)
        statements = (yaml.safe_load(notes.group("y").rstrip()) or {}).get("rules", []) if notes else []

        core = data.setdefault("core", {})
        if path.stem in MODEL_FIX and core.get("enforcement_model") != MODEL_FIX[path.stem]:
            core["enforcement_model"] = MODEL_FIX[path.stem]
            models += 1

        for i, rule in enumerate(data.get("rules") or []):
            rid = statements[i].get("rule_id") if i < len(statements) else None
            if rid in BINDINGS:
                rule["enforced_by"] = BINDINGS[rid]
                bound += 1
            elif str(rule.get("enforced_by", "")) in ("TBD", "compiler_validation", "None") \
                    or rule.get("enforced_by") is None \
                    or str(rule.get("enforced_by", "")).startswith("ASSERT_"):
                unbound.append((path.stem, str(rid), str(rule.get("enforced_by"))))

        if not args.dry_run:
            body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                                  allow_unicode=True, width=100).rstrip()
            path.write_text(
                text[: m.start()] + m.group("head") + body + m.group("tail") + text[m.end():],
                encoding="utf-8",
            )

    verb = "would bind" if args.dry_run else "bound"
    print(f"  {verb} {bound} rules   corrected {models} enforcement models")
    print(f"  remaining unenforced: {len(unbound)}")
    by_con: dict[str, int] = {}
    for con, _rid, _eb in unbound:
        by_con[con] = by_con.get(con, 0) + 1
    for con, n in sorted(by_con.items(), key=lambda x: -x[1]):
        print(f"     {n:>3}  {con}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())