"""Phase 1 migration — close the governance machine-block contract.

Rewrites INVARIANT, CONSTITUTION and SURFACE_CONTRACT artifacts so their
``## Machine`` blocks contain only fields the compiler consumes, and relocates
every explanatory field below the fence under a ``## Rule Statement`` heading.
Nothing is discarded: relocated content is preserved verbatim in the document.

Normalizations applied:
  * enforcement_stage    compiler_assert -> compiler_assertion; non-enum stages dropped;
                         absent -> [compiler_assertion]
  * violation_response   FAIL_COMPILE -> FAIL_IMMEDIATELY; absent -> FAIL_IMMEDIATELY
  * enforced_by          bare ASSERT_X_Vn -> <ns>::INVARIANT_X_Vn when that invariant exists;
                         process/runtime markers -> PROCESS_ENFORCED / RUNTIME_ENFORCED.
                         TBD and unresolvable codes are left as authored so the closed
                         schema reports them — that incompleteness is the finding, not a
                         thing to paper over.

Usage:
    python scripts/migrate_machine_closure.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / "software_governance" / "registry"

MACHINE = re.compile(
    r"(?P<head>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<tail>\n```)",
    re.MULTILINE | re.DOTALL,
)

STAGE_ALIASES = {"compiler_assert": "compiler_assertion"}
STAGE_ENUM = {
    "compiler_discovery", "compiler_validation", "compiler_assertion",
    "compiler_meta_validation", "runtime_outcome",
}
RESPONSE_ALIASES = {"FAIL_COMPILE": "FAIL_IMMEDIATELY"}
RESPONSE_ENUM = {"FAIL_IMMEDIATELY", "WARN", "BUSINESS_VIOLATION"}

# Fields lifted out of the Machine block and preserved below the fence.
INVARIANT_RELOCATE_CORE = [
    "description", "rule", "summary", "anti_patterns", "clarification", "file_path_cs_types",
]
INVARIANT_RELOCATE_TOP = ["examples", "extensions"]
INVARIANT_DROP_TOP = ["invariant_code", "artifact_code", "artifact_type", "fqdn"]
INVARIANT_DROP_CORE = ["scope"]

CONSTITUTION_RELOCATE_CORE = ["description", "summary", "derivation"]
CONSTITUTION_RELOCATE_TOP = ["doctrine"]
CONSTITUTION_RELOCATE_EXTRA = ["field_constraints", "required_fields"]
CONSTITUTION_DROP_TOP = ["constitution_code", "fqdn"]
CONSTITUTION_DROP_CORE = ["scope"]

SURFACE_RELOCATE_TOP = ["capability_family"]

# assert_projection.enforcement keys the schema admits; anything else is relocated.
ENFORCEMENT_KEYS = {"level", "order", "phase", "scope"}


def namespace_of(path: Path) -> str:
    fb = next(p for p in path.parts if p.startswith("FB_"))
    return "fb." + fb[len("FB_"):].lower()


def load_all() -> dict[Path, dict]:
    out: dict[Path, dict] = {}
    for md in sorted(REGISTRY.rglob("*.md")):
        m = MACHINE.search(md.read_text(encoding="utf-8"))
        if not m:
            continue
        data = yaml.safe_load(m.group("y").rstrip())
        if isinstance(data, dict):
            out[md] = data
    return out


def invariant_index(all_artifacts: dict[Path, dict]) -> dict[str, str]:
    """INVARIANT_CODE -> FQDN, for migrating bare ASSERT_ references."""
    return {
        md.stem: f"{namespace_of(md)}::{md.stem}"
        for md, d in all_artifacts.items()
        if d.get("artifact_kind") == "INVARIANT"
    }


def pop_many(src: dict, keys: list[str]) -> dict:
    return {k: src.pop(k) for k in keys if k in src}


def migrate_invariant(data: dict) -> tuple[dict, dict]:
    relocated: dict[str, Any] = {}
    for k in INVARIANT_DROP_TOP:
        data.pop(k, None)
    relocated.update(pop_many(data, INVARIANT_RELOCATE_TOP))

    core = data.setdefault("core", {})
    for k in INVARIANT_DROP_CORE:
        core.pop(k, None)
    core_moved = pop_many(core, INVARIANT_RELOCATE_CORE)
    if core_moved:
        relocated["core"] = core_moved

    stages = core.get("enforcement_stage") or []
    if isinstance(stages, str):
        stages = [stages]
    stages = [STAGE_ALIASES.get(s, s) for s in stages]
    dropped = [s for s in stages if s not in STAGE_ENUM]
    stages = [s for s in stages if s in STAGE_ENUM] or ["compiler_assertion"]
    if dropped:
        relocated["non_enum_enforcement_stages"] = dropped
    core["enforcement_stage"] = stages

    resp = core.get("violation_response") or "FAIL_IMMEDIATELY"
    resp = RESPONSE_ALIASES.get(resp, resp)
    core["violation_response"] = resp if resp in RESPONSE_ENUM else "FAIL_IMMEDIATELY"

    proj = data.get("assert_projection")
    if isinstance(proj, dict):
        enf = proj.get("enforcement")
        if isinstance(enf, dict):
            extra = {k: enf.pop(k) for k in list(enf) if k not in ENFORCEMENT_KEYS}
            if extra:
                relocated.setdefault("assert_projection", {})["enforcement"] = extra

    # Canonical key order: identity, then governance, then projection.
    ordered = {k: data[k] for k in ("artifact_kind", "version", "governed_by") if k in data}
    ordered["core"] = {
        k: core[k] for k in ("enforcement_stage", "violation_response", "runtime_binding")
        if k in core
    }
    ordered["core"].update({k: v for k, v in core.items() if k not in ordered["core"]})
    if "assert_projection" in data:
        ordered["assert_projection"] = data["assert_projection"]
    return ordered, relocated


def migrate_constitution(data: dict, inv_index: dict[str, str]) -> tuple[dict, dict]:
    relocated: dict[str, Any] = {}
    for k in CONSTITUTION_DROP_TOP:
        data.pop(k, None)
    relocated.update(pop_many(data, CONSTITUTION_RELOCATE_TOP + CONSTITUTION_RELOCATE_EXTRA))

    core = data.setdefault("core", {})
    for k in CONSTITUTION_DROP_CORE:
        core.pop(k, None)
    core_moved = pop_many(core, CONSTITUTION_RELOCATE_CORE)
    if core_moved:
        relocated["core"] = core_moved

    constraints = []
    new_rules = []
    for rule in data.get("rules") or []:
        rid = rule.pop("rule_id", None)
        constraint = rule.pop("constraint", None)
        if constraint is not None:
            constraints.append({"rule_id": rid, "constraint": constraint} if rid
                               else {"constraint": constraint})
        eb = rule.get("enforced_by")
        if isinstance(eb, str):
            if eb.startswith("ASSERT_"):
                cand = "INVARIANT_" + eb[len("ASSERT_"):]
                rule["enforced_by"] = inv_index.get(cand, eb)
            elif eb.lower() == "process_enforced":
                rule["enforced_by"] = "PROCESS_ENFORCED"
            elif eb.lower() in ("runtime_enforced", "runtime_outcome"):
                rule["enforced_by"] = "RUNTIME_ENFORCED"
        new_rules.append({k: rule[k] for k in ("applies_to", "enforced_by") if k in rule})
    if constraints:
        relocated["rules"] = constraints

    ordered = {k: data[k] for k in ("artifact_kind", "version", "governed_by") if k in data}
    ordered["core"] = {k: core[k] for k in ("enforcement_model", "governs") if k in core}
    ordered["core"].update({k: v for k, v in core.items() if k not in ordered["core"]})
    ordered["rules"] = new_rules
    return ordered, relocated


def migrate_surface(data: dict) -> tuple[dict, dict]:
    relocated = pop_many(data, SURFACE_RELOCATE_TOP)
    order = ["artifact_kind", "version", "governed_by", "surface_contract_code",
             "governs", "op", "canonical_surface", "capability_id_prefix"]
    ordered = {k: data[k] for k in order if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    return ordered, relocated


def render(path: Path, machine: dict, relocated: dict) -> str:
    text = path.read_text(encoding="utf-8")
    m = MACHINE.search(text)
    body = yaml.safe_dump(machine, sort_keys=False, default_flow_style=False,
                          allow_unicode=True, width=100).rstrip()
    out = text[: m.start()] + m.group("head") + body + m.group("tail") + text[m.end():]
    if relocated:
        block = yaml.safe_dump(relocated, sort_keys=False, default_flow_style=False,
                               allow_unicode=True, width=100).rstrip()
        out = out.rstrip() + "\n\n---\n\n## Rule Statement\n\n```yaml\n" + block + "\n```\n"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    all_artifacts = load_all()
    inv_index = invariant_index(all_artifacts)
    counts = {"INVARIANT": 0, "CONSTITUTION": 0, "SURFACE_CONTRACT": 0}

    for path, data in all_artifacts.items():
        # Key on the artifact-code prefix, matching how S4 selects the schema. Keying on the
        # authored artifact_kind field would skip artifacts that never declared one — exactly
        # the artifacts most in need of migration.
        prefix = path.stem.split("_")[0]
        kind = {"INVARIANT": "INVARIANT", "CONSTITUTION": "CONSTITUTION",
                "SURFACE": "SURFACE_CONTRACT"}.get(prefix)
        if kind is None:
            continue
        data["artifact_kind"] = kind
        if "version" in data and not isinstance(data["version"], str):
            data["version"] = f"V{data['version']}"
        if kind == "INVARIANT":
            machine, relocated = migrate_invariant(data)
        elif kind == "CONSTITUTION":
            machine, relocated = migrate_constitution(data, inv_index)
        elif kind == "SURFACE_CONTRACT":
            machine, relocated = migrate_surface(data)
        else:
            continue
        counts[kind] += 1
        if not args.dry_run:
            path.write_text(render(path, machine, relocated), encoding="utf-8")

    verb = "would migrate" if args.dry_run else "migrated"
    for k, n in counts.items():
        print(f"  {verb} {n:>3} {k}")
    print(f"  invariant index: {len(inv_index)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())