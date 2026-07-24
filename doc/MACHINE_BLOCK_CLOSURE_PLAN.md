# Machine-Block Closure — Implementation Plan

Three phases. Domain-exposed risk is isolated into the last one.

---

## Regression coverage — where I differ

Concur on the decision: proceed now, re-verify when the two user domains migrate. The defect is in the governance authoring surface, and every day it stands is a day the Platform specification is reverse-engineered from a surface that lies.

I do not concur that coverage is absent today. Two harnesses exist and cover most of this work:

**1. The collatz reference workload compiles.** `./compile_domain.sh ../platform/reference_workloads/collatz` — 25 artifacts, Verified, Attested. It exercises the full domain path: `layer_definitions`, `identity_rules`, `import_surface`, `_inject_imported_capabilities`, and CT/CS/CC/WF artifacts under a domain namespace. It is not equivalent to the user domains in breadth, but it touches every code path this work changes. Both builds must stay green at every phase boundary.

**2. Graph-hash equality is a stronger gate than a test suite for this class of change.** Phases 1 and 3 are semantically neutral by construction — moving prose out of the fence and relocating a dispatch table must not change compiled meaning. `graph_topology_hash` and `graph_address_hash` are derived from the typed graph, not source bytes, so hash equality before and after is a hard proof of neutrality. A test suite could not assert that as tightly.

What genuinely lacks coverage is narrower than "regression testing": the breadth of *domain build manifest shapes*. Collatz exercises one manifest. `SCHEMA_STRUCTURE_V0`, once closed, can reject a manifest key that collatz happens not to use but a user domain does. That is the real exposure, it is confined to Phase 3, and it is the specific thing to re-verify at migration.

---

## Phase 1 — Make the boundary truthful

Scope: registry artifacts and new schemas. No dispatch mechanism changes.

1. **Resolve `core.enforcement_stage`.** Merge into `assert_projection.enforcement.phase`; repoint `governance_engine/assertions/handlers/assert_runtime_invariant_wired_v0.py:53`; delete the field from all 38 invariants. One enforcement descriptor per invariant, one authority.
2. **Author `SCHEMA_INVARIANT_V0`, `SCHEMA_CONSTITUTION_V0`, `SCHEMA_SURFACE_CONTRACT_V0`**, each `additionalProperties: false`. Derive the permitted key set from the consumer inventory and required validation roles — **not** by transcribing the current machine blocks. Transcribing reproduces the defect inside the fix.
3. **Register them** by adding four entries to the existing `schema_file_map` (`s4_govern.py:602`). The dict stays a dict in this phase; changing the dispatch mechanism at the same time as the schemas would conflate two failure modes.
4. **Relocate prose** across the affected artifacts: `core.description`, `core.rule`, `core.summary`, `core.anti_patterns`, `core.clarification`, `examples`, `rules[].constraint` move below the fence under `## Purpose` / `## Validation Rules` / `## Rationale` / `## Examples`. Delete `invariant_code`, `constitution_code`, `rules[].rule_id`, `core.scope`, `core.violation_response`.

`SCHEMA_STRUCTURE_V0` is deliberately held back — STRUCTURE blocks carry domain build manifests, which is the one genuinely uncovered surface.

**Exit gate:** platform compile green; collatz compile green; `machine_key_census.py --kind INVARIANT` and `--kind CONSTITUTION` report DEAD = 0; graph hashes unchanged from baseline except where a deleted key was genuinely load-bearing.

---

## Phase 2 — Make declared relationships resolve

Scope: compiler + one new invariant. Closure alone leaves `enforced_by` as theater — a schema can accept a field nothing resolves.

1. **New `INVARIANT_GOVERNANCE_DECLARATION_RESOLVES_V0`** with handler `assert_governance_declaration_resolves_v0.py`, asserting bidirectionally:
   - every `rules[].enforced_by` FQDN resolves to a compiled INVARIANT whose derived ASSERT has a registered handler;
   - every INVARIANT in scope is named by at least one constitution rule — no orphans.
2. **Promote `rules[].enforced_by` and `rules[].applies_to`** to schema-required in `SCHEMA_CONSTITUTION_V0`.
3. **Retire** the emptiness check in `assert_compiler_governance_declared_v0.py:51` — subsumed.

This is the phase that converts `CONSTITUTION → INVARIANT → ASSERT → HANDLER` from a naming convention into a verified chain.

**Exit gate:** both compiles green; negative tests pass — pointing an `enforced_by` at a nonexistent invariant must fail the compile, and adding an invariant no constitution names must fail the compile.

---

## Phase 3 — Declared dispatch and the standing gate

Scope: the domain-exposed work. This is the phase to re-run against the user domains at migration.

1. **Move `schema_file_map` into a STRUCTURE artifact** declaring kind → schema; the compiler consumes the declaration. A hardcoded dict deciding which artifacts are governed is the same category of defect being fixed.
2. **Author and bind `SCHEMA_STRUCTURE_V0`** (the file exists, unloaded). Closing it validates build manifests — `artifact_discovery`, `layer_definitions`, `identity_rules`, `import_surface`, `output_configuration`. Highest rejection risk against an unseen domain manifest.
3. **Wire the standing gate:** `machine_key_census.py` per commit expecting DEAD = 0; `machine_key_mutation.py` as the adjudicator for disputed keys.

**Exit gate:** both compiles green; graph hashes identical across the dispatch relocation (it must be a semantic no-op); census clean across all kinds.

**At domain migration:** compile both user domains, confirm no manifest key is rejected by `SCHEMA_STRUCTURE_V0`, and run the census over their registries.

---

## Two notes on the acceptance criterion

**Mutation cannot be the per-commit gate.** 713 key paths × a full compile each is hours, not seconds. Census per commit (static, whole-registry, seconds); mutation nightly or on census dispute. The census is the detector, mutation is the truth — but only the detector can run at commit frequency.

**"DEAD = 0" and "defined validation role" are in slight tension.** A field whose only role is schema presence-checking will read DEAD under mutation: deleting it fails the compile at S4, which the verifier reports as LIVE — but a field that is *permitted* and *unrequired* and merely accepted will read DEAD while satisfying a loose reading of "has a validation role."

The resolution is to allow no exemption list. If a key has no consequence beyond being tolerated, it does not belong in the schema. An exemption list is precisely the mechanism that produced the current state: a category of key that is present, blessed, and inert. Every permitted key must be either required, or resolved, or consumed — and each of those makes it LIVE under mutation.