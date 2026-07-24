"""Generate the GOVERNANCE_SURFACE_MAP from the actual registry artifacts.

Emits platform/doc/governance_surface_map.yaml — a semantic coordinate for every governance
artifact, derived from real fields (enforcement_stage, assert_projection scope, the governing
constitution's enforcement_model), not hand-assigned. This is documentation ABOUT the registry;
it lives in doc/, not registry/, so it is not compiled and adds no node (hash-neutral).

Coordinate per artifact:
  domain · concern · property · lifecycle · enforcement_locus · authority · coverage.status
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

# FB → (concern family, concern). Composite FBs are refined per-artifact below.
FB_FAMILY = {
    "FB_VOCABULARY": ("declaration", "vocabulary"),
    "FB_IDENTITY": ("declaration", "identity"),
    "FB_AUTHORITY": ("composition", "authority"),
    "FB_CONFORMANCE": ("composition", "conformance"),
    "FB_TOPOLOGY": ("composition", "topology"),
    "FB_CRYPTOGRAPHIC_TRUST": ("execution_envelope", "cryptographic_trust"),
    "FB_EXECUTION_PLACEMENT": ("execution_envelope", "placement"),
    "FB_EXECUTION_SCHEDULING": ("execution_envelope", "scheduling"),
    "FB_SECURITY_DOMAIN": ("execution_envelope", "security_domain"),
    "FB_TRANSPORT": ("execution_envelope", "transport"),
    "FB_CHANGE_MGMT": ("evolution", "change_management"),
    "FB_CONSTITUTION": ("meta_governance", "constitution"),
}

# Per-artifact-code refinements inside the composite FBs (§6 of the classification doc).
# FB_CONSTITUTION holds meta-kernel + build machinery + schema registry.
CONSTITUTION_REFINE = {
    "INVARIANTS": ("meta_governance", "invariants"),
    "GOVERNANCE": ("meta_governance", "governance_authority"),
    "ASSERT": ("meta_governance", "assertions"),
    "COMPILER": ("meta_governance", "compiler_governance"),
    "STRUCTURE": ("declaration", "structure"),
    "EVENT": ("composition", "event"),
    "FEDERATION_BOUNDARY": ("meta_governance", "governance_authority"),
}
# FB_TOPOLOGY runtime-doctrine constitutions belong to execution semantics, not composition.
TOPOLOGY_RUNTIME = {"EXECUTION", "TRACE_EXECUTION", "EXECUTION_POLICY", "ADMISSION"}


def load():
    for md in sorted(REGISTRY.rglob("*.md")):
        m = MB.search(md.read_text(encoding="utf-8"))
        if not m:
            continue
        d = yaml.safe_load(m.group("y").rstrip())
        if isinstance(d, dict):
            fb = next((p for p in md.parts if p.startswith("FB_")), "?")
            yield md, fb, d


def constitution_models(artifacts):
    models = {}
    for md, fb, d in artifacts:
        if d.get("artifact_kind") == "CONSTITUTION":
            models[md.stem] = (d.get("core", {}) or {}).get("enforcement_model", "?")
    return models


def coordinate(md, fb, d, con_models):
    code = md.stem
    kind = d.get("artifact_kind") or code.split("_")[0]
    core = d.get("core", {}) or {}
    proj = d.get("assert_projection", {}) or {}
    stages = set(core.get("enforcement_stage") or [])
    kinds = set(proj.get("applies_to_kinds") or [])

    family, concern = FB_FAMILY.get(fb, ("unclassified", fb.lower()))

    # refine composite FBs
    subject = code.split("_", 1)[1] if "_" in code else code
    subject = re.sub(r"_V\d+$", "", subject)
    if fb == "FB_CONSTITUTION":
        for key, (f, c) in CONSTITUTION_REFINE.items():
            if subject == key or subject.startswith(key):
                family, concern = f, c
                break
        if kind == "STRUCTURE":
            family, concern = "declaration", "structure"
    if fb == "FB_TOPOLOGY" and kind == "CONSTITUTION" and subject in TOPOLOGY_RUNTIME:
        family, concern = "execution_semantics", subject.lower()
    if fb == "FB_TOPOLOGY" and subject in ("TRACE_EXECUTION",):
        family, concern = "execution_semantics", "trace"

    # enforcement locus (derived from real fields)
    gov = d.get("governed_by")
    gov = gov[0] if isinstance(gov, list) else gov
    gov_model = con_models.get(str(gov).split("::")[-1], "")
    if "SNAPSHOT" in kinds:
        locus, lifecycle, authority = "snapshot_declaration", "seal", "snapshot"
    elif "runtime_outcome" in stages or gov_model == "runtime_enforced" or subject in TOPOLOGY_RUNTIME:
        locus, lifecycle, authority = "runtime_execution", "execute", "constitution"
    elif (con_models.get(code, "") == "process_enforced") or gov_model == "process_enforced":
        locus, lifecycle, authority = "meta_process", "evolve", "process"
    elif family == "meta_governance":
        locus, lifecycle, authority = "meta_process", "compile", "constitution"
    elif family == "declaration":
        locus, lifecycle, authority = "compile_composition", "declare", "constitution"
    else:
        locus, lifecycle, authority = "compile_composition", "compile", "constitution"

    # coverage status
    if fb == "FB_TRANSPORT":
        status = "intentionally_deferred"
    elif locus == "meta_process" and authority == "process":
        status = "process_enforced"
    else:
        status = "implemented"

    return {
        "artifact_code": code,
        "kind": kind,
        "fb": fb,
        "semantic": {
            "domain": family, "concern": concern, "property": subject.lower(),
            "lifecycle": lifecycle, "enforcement_locus": locus, "authority": authority,
        },
        "coverage": {"status": status},
    }


def main():
    artifacts = list(load())
    con_models = constitution_models(artifacts)
    coords = [coordinate(md, fb, d, con_models) for md, fb, d in artifacts]
    coords.sort(key=lambda c: (c["semantic"]["domain"], c["semantic"]["concern"], c["artifact_code"]))

    by_family = defaultdict(Counter)
    by_status = Counter()
    by_locus = Counter()
    for c in coords:
        by_family[c["semantic"]["domain"]][c["semantic"]["concern"]] += 1
        by_status[c["coverage"]["status"]] += 1
        by_locus[c["semantic"]["enforcement_locus"]] += 1

    doc = {
        "governance_surface_map": {
            "artifact_count": len(coords),
            "families": {f: dict(c) for f, c in sorted(by_family.items())},
            "by_enforcement_locus": dict(by_locus),
            "by_coverage_status": dict(by_status),
            "coverage_ledger": {
                "transport": {"status": "intentionally_deferred", "reason": "transport phase frozen; TI/TE governance not yet authorized"},
                "state_entity_platform": {"status": "not_applicable", "reason": "ENTITY/state is domain-owned; not a platform concern"},
                "trace_observability": {"status": "implemented", "note": "governed by CONSTITUTION_TRACE_EXECUTION, currently located inside FB_TOPOLOGY (misplaced boundary)"},
            },
            "artifacts": coords,
        }
    }
    OUT.write_text(yaml.safe_dump(doc, sort_keys=False, width=100, allow_unicode=True), encoding="utf-8")
    print(f"wrote {OUT.relative_to(WORKSPACE)}  ({len(coords)} artifacts)")
    print("families:", {f: sum(c.values()) for f, c in sorted(by_family.items())})
    print("locus:", dict(by_locus))
    print("status:", dict(by_status))


if __name__ == "__main__":
    main()
