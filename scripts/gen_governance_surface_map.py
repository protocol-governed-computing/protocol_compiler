"""Generate the GOVERNANCE_SURFACE_MAP from the semantic registry tree.

Since Phase C, the registry folders ARE the concern classification
(registry/<family>/<concern>/[<kind>/]<artifact>), so family + concern are read directly
from each artifact's path. The remaining coordinates (lifecycle, enforcement_locus,
authority, coverage) are derived from real artifact fields, not hand-assigned.

Emits platform/doc/governance_surface_map.yaml. This is documentation ABOUT the registry;
it lives in doc/, not registry/, so it is not compiled (hash-neutral).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / "platform" / "registry"
OUT = WORKSPACE / "platform" / "doc" / "governance_surface_map.yaml"

MB = re.compile(r"^## Machine\s*\n+```yaml\s*\n(?P<y>.*?)\n```", re.M | re.S)
DOMAIN_KINDS = {"WF", "CC", "CS", "CT", "RB", "AC", "IN", "EV", "TI", "TE"}
RUNTIME_SUBJECTS = {"execution", "execution_policy", "trace", "admission"}


def family_concern(path: Path) -> tuple[str, str]:
    """(family, concern) read directly from the semantic folder tree."""
    parts = path.relative_to(REGISTRY).parts  # <family>/.../<file>
    family = parts[0]
    if family == "meta_governance":
        return family, "(kernel)"
    if family == "execution":                 # execution/<envelope|semantics>/<concern>/...
        return "execution", parts[2] if len(parts) > 2 else parts[1]
    if family == "declaration" and parts[1] == "schema":
        return "declaration", "schema"
    return family, parts[1]


def load():
    for md in sorted(REGISTRY.rglob("*.md")):
        m = MB.search(md.read_text(encoding="utf-8"))
        if not m:
            continue
        d = yaml.safe_load(m.group("y").rstrip())
        if isinstance(d, dict):
            yield md, d
    for js in sorted((REGISTRY / "declaration" / "schema").glob("*.json")):
        if js.name != "schema_index.json":
            yield js, {"artifact_kind": "SCHEMA"}


def constitution_models(items):
    return {
        md.stem: (d.get("core", {}) or {}).get("enforcement_model", "?")
        for md, d in items if d.get("artifact_kind") == "CONSTITUTION"
    }


def coordinate(md, d, con_models):
    code = md.stem
    kind = d.get("artifact_kind") or code.split("_")[0]
    core = d.get("core", {}) or {}
    proj = d.get("assert_projection", {}) or {}
    stages = set(core.get("enforcement_stage") or [])
    kinds = set(proj.get("applies_to_kinds") or [])
    family, concern = family_concern(md)

    subject = re.sub(r"_V\d+$", "", code.split("_", 1)[1]) if "_" in code else code
    gov = d.get("governed_by")
    gov = gov[0] if isinstance(gov, list) else gov
    gov_model = con_models.get(str(gov).split("::")[-1], "")

    if kind == "SCHEMA":
        locus, lifecycle, authority = "compile_composition", "declare", "constitution"
    elif "SNAPSHOT" in kinds:
        locus, lifecycle, authority = "snapshot_declaration", "seal", "snapshot"
    elif "runtime_outcome" in stages or gov_model == "runtime_enforced" or concern in RUNTIME_SUBJECTS:
        locus, lifecycle, authority = "runtime_execution", "execute", "constitution"
    elif con_models.get(code, "") == "process_enforced" or gov_model == "process_enforced":
        locus, lifecycle, authority = "meta_process", "evolve", "process"
    elif family == "meta_governance":
        locus, lifecycle, authority = "meta_process", "compile", "constitution"
    elif family == "declaration":
        locus, lifecycle, authority = "compile_composition", "declare", "constitution"
    else:
        locus, lifecycle, authority = "compile_composition", "compile", "constitution"

    if concern == "transport":
        status = "intentionally_deferred"
    elif locus == "meta_process" and authority == "process":
        status = "process_enforced"
    elif kind == "SCHEMA":
        status = "declaration_substrate"
    else:
        status = "implemented"

    return {
        "artifact_code": code, "kind": kind, "family": family, "concern": concern,
        "semantic": {"property": subject.lower(), "lifecycle": lifecycle,
                     "enforcement_locus": locus, "authority": authority},
        "coverage": {"status": status},
    }


def main():
    items = list(load())
    con_models = constitution_models(items)
    coords = [coordinate(md, d, con_models) for md, d in items]
    coords.sort(key=lambda c: (c["family"], c["concern"], c["artifact_code"]))

    by_family = defaultdict(Counter)
    by_status = Counter()
    by_locus = Counter()
    for c in coords:
        by_family[c["family"]][c["concern"]] += 1
        by_status[c["coverage"]["status"]] += 1
        by_locus[c["semantic"]["enforcement_locus"]] += 1

    doc = {"governance_surface_map": {
        "note": "family and concern are read from the semantic registry tree (registry/<family>/<concern>/); "
                "identity (fqdn) is declared per-artifact and independent of this path.",
        "artifact_count": len(coords),
        "families": {f: dict(c) for f, c in sorted(by_family.items())},
        "by_enforcement_locus": dict(by_locus),
        "by_coverage_status": dict(by_status),
        "coverage_ledger": {
            "transport": {"status": "intentionally_deferred", "reason": "transport phase frozen; TI/TE governance not yet authorized"},
            "state_entity_platform": {"status": "not_applicable", "reason": "ENTITY/state is domain-owned; not a platform concern"},
            "schema": {"status": "declaration_substrate", "reason": "formal shape/type system of the declaration language, not an independent policy concern"},
            "trace_observability": {"status": "implemented", "note": "governed by CONSTITUTION_TRACE_EXECUTION under execution/semantics/trace"},
        },
        "artifacts": coords,
    }}
    OUT.write_text(yaml.safe_dump(doc, sort_keys=False, width=100, allow_unicode=True), encoding="utf-8")
    print(f"wrote {OUT.relative_to(WORKSPACE)}  ({len(coords)} artifacts)")
    print("families:", {f: sum(c.values()) for f, c in sorted(by_family.items())})
    print("status:", dict(by_status))


if __name__ == "__main__":
    main()
