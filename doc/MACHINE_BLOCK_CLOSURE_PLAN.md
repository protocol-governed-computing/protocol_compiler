# Machine-Block Closure — Implementation Plan

Three phases. Domain-exposed risk isolated into the last one.

## Closure definition

Closure is not a property of a schema alone:

```
Machine-block closure
  = schema closure          (additionalProperties: false)
  + field liveness          (every accepted key has semantic consequence)
  + reference closure       (every declared reference resolves)
  + governance closure      (every governed object is actually governed)
```

`additionalProperties: false` is necessary and insufficient. Each phase below closes one term.

## Adjudication model

The census is the detector; the mutation verifier is the authority.

```
machine key
   ↓ delete
compile
   ├── compile fails            → LIVE
   ├── semantic graph changes   → LIVE
   └── identical semantic graph → DEAD
```

---

## Findings that amend the plan

### F1 — `core.enforcement_stage` must not be merged or deleted

`platform/doc/rule_ownership.md` (marked **Doctrine**) establishes it as the designed discriminator between the two invariant classes:

| | Compile-time structural | Runtime business |
|---|---|---|
| `core.enforcement_stage` | `compiler_assertion` (etc.) | `runtime_outcome` |
| `core.violation_response` | `FAIL_IMMEDIATELY` | `BUSINESS_VIOLATION` |
| enforced by | an ASSERT handler (S4) | a CC violation outcome + WF routing |
| verified by | the ASSERT itself | `ASSERT_RUNTIME_INVARIANT_WIRED_V0` |

A `runtime_outcome` invariant declares `core.runtime_binding` (`enforced_by`, `enforcing_workflow`, `violation_outcome`, `terminal_node`, `over_store`), and `assert_runtime_invariant_wired_v0` proves that binding against the CC result surface and the WF routing. `assert_assert_parity_v0` also branches on it, exempting runtime invariants from INVARIANT↔ASSERT parity.

Both fields are load-bearing. Both read DEAD under mutation, because **no platform-registry invariant is `runtime_outcome`-staged**. The path exists in the compiler; the corpus does not exercise it.

**Revised disposition** — make the discriminator load-bearing rather than removing it:

- Keep `core.enforcement_stage` in `SCHEMA_INVARIANT_V0` as a closed enum. Normalize the vocabulary first: `compiler_assert` (4 artifacts) and `compiler_assertion` (4) are the same thing; `compiler_validation` (27), `compiler_discovery`, `compiler_meta_validation` also appear.
- Make the schema conditional. `enforcement_stage: [runtime_outcome]` **requires** `core.runtime_binding` and `violation_response: BUSINESS_VIOLATION`; `compiler_*` stages **forbid** `runtime_binding`. That converts a tag into a checked contract.
- Keep `core.violation_response` as a closed enum. It was slated for deletion; that was wrong.
- Leave `assert_projection.enforcement.phase` alone — a separate axis (S4 execution ordering). It overlaps `enforcement_stage` on only the 7 artifacts declaring both. Reconcile those 7 by hand; do not merge the fields.
- No change to `assert_runtime_invariant_wired_v0.py`.

### F2 — DEAD has a false-positive class

The mutation verifier measures liveness against the **compiled corpus**, not the compiler's capability. A field gating a domain-facing path reads DEAD whenever no artifact in the build exercises that path. F1 is the first confirmed instance.

A DEAD verdict therefore means: *dead, or live only on a path this corpus does not exercise.* This qualifies the Phase 1 exit gate — a DEAD verdict licenses relocation only after the consumer has been read and shown to have no unexercised branch. It is also the strongest argument yet that the two user domains are required before the census can stand as an unattended acceptance gate.

### F3 — `graph_topology_hash` is always empty

`canonical/metadata.json` carries `graph_topology_hash: ""` in the platform build. Only `graph_address_hash` currently carries signal, so the adjudicator rests on one hash rather than two. Fix or drop the field before Phase 3 makes the mutation gate standing; until then, adjudication is sound but narrower than intended.

### F4 — `rules[].constraint` verified DEAD

Stripped from every rule in `CONSTITUTION_WORKFLOW_V0`; compile clean, `graph_address_hash` identical (`ec023c23…`). No reader exists — the only `constraint` reader is `projections/ipm.py:279`, reading `core.invariants[]` on entity artifacts, an unrelated path. Cleared for relocation below the fence.

### F5 — governance scope is the compiled corpus

"Every INVARIANT in scope" resolves against the current build's compiled graph. The domain build carries **zero INVARIANT and zero CONSTITUTION** nodes — governance imports are resolve-only and dropped in S2 (collatz compiles 25 artifacts: STRUCTURE, CT, CS, CC, WF, RB, AC, IN, EV). The bidirectional closure is therefore vacuous in a domain build and total in a platform build. A platform constitution can never be required to name a domain invariant; the scope leak is impossible by construction rather than by rule.

Where finer scoping is needed, reuse the established idiom rather than inventing one: `assert_projection.scope.applies_to` + `layer_category_map` + `is_domain_build`, exactly as `assert_ct_surface_closed_v0` and `assert_cs_surface_closed_v0` already do.

---

## Regression coverage

Two harnesses exist and must both stay green at every phase boundary:

- **`./compile_domain.sh ../platform/reference_workloads/collatz`** — 25 artifacts, Verified, Attested. Exercises `layer_definitions`, `identity_rules`, `import_surface`, `_inject_imported_capabilities`, and CT/CS/CC/WF under a domain namespace.
- **`graph_address_hash` equality** — derived from the typed graph, not source bytes, so equality across a semantically-neutral change is a hard proof of neutrality.

What genuinely lacks coverage is the breadth of **domain build-manifest shapes**. Collatz exercises one. `SCHEMA_STRUCTURE_V0`, once closed, can reject a manifest key collatz does not use but a user domain does. Confined to Phase 3.

---

## Phase 1 — Make the boundary truthful

Scope: registry artifacts and new schemas. No dispatch mechanism change — the `schema_file_map` dict stays a dict, so that a later domain failure is attributable to schema *selection* (Phase 3) or schema *content* (Phase 1), never both.

1. Normalize the `enforcement_stage` vocabulary and reconcile the 7 artifacts declaring both it and `enforcement.phase` (F1).
2. Author `SCHEMA_INVARIANT_V0`, `SCHEMA_CONSTITUTION_V0`, `SCHEMA_SURFACE_CONTRACT_V0`, each `additionalProperties: false`, with the conditional `runtime_binding` requirement from F1. Derive the permitted key set from the consumer inventory and required validation roles — **not** by transcribing the current machine blocks, which reproduces the defect inside the fix.
3. Register them by adding three entries to `schema_file_map` (`s4_govern.py:602`).
4. Relocate prose below the fence under `## Purpose` / `## Validation Rules` / `## Rationale` / `## Examples`: `core.description`, `core.rule`, `core.summary`, `core.anti_patterns`, `core.clarification`, `examples`, `rules[].constraint`. Delete `invariant_code`, `constitution_code`, `rules[].rule_id`, `core.scope`.

`SCHEMA_STRUCTURE_V0` is deliberately held back — STRUCTURE blocks carry domain build manifests, the one genuinely uncovered surface.

**Exit gate.** For every relocated or deleted key, the mutation adjudicator must return LIVE or COMPILE_FAIL — no affected key may be DEAD — with any DEAD verdict qualified by an F2 consumer read before it licenses relocation. For the prose relocation itself, `graph_address_hash` MUST be identical. Platform and collatz compiles green.

---

## Phase 2 — Make declared relationships resolve

Closure alone leaves `enforced_by` as theater: a schema can accept a field nothing resolves. The compiler must prove the full chain `CONSTITUTION → INVARIANT → ASSERT → HANDLER` and its reverse.

1. New `INVARIANT_GOVERNANCE_DECLARATION_RESOLVES_V0` with handler `assert_governance_declaration_resolves_v0.py`, asserting bidirectionally:
   - every `rules[].enforced_by` FQDN resolves to a compiled INVARIANT whose derived ASSERT has a registered handler;
   - every compiled INVARIANT within the governance scope (F5) is named by at least one applicable constitution rule.
2. Promote `rules[].enforced_by` and `rules[].applies_to` to schema-required in `SCHEMA_CONSTITUTION_V0`.
3. Retire the emptiness check in `assert_compiler_governance_declared_v0.py:51` — subsumed.

**Implementation constraint.** The handler validates the compiler's already-resolved graph — `artifacts_by_fqdn`, the derived-ASSERT set, `HANDLER_REGISTRY` — and must not reimplement discovery. Compiler resolves, governance validates; an assertion that independently rediscovers the corpus will drift from the compiler as the platform evolves.

**Exit gate.** Both compiles green. Negative tests: an `enforced_by` pointing at a nonexistent invariant must fail the compile; an invariant no constitution names must fail the compile.

---

## Phase 3 — Declared dispatch and the standing gate

The domain-exposed phase. Re-run against the user domains at migration.

1. Move `schema_file_map` into a STRUCTURE artifact declaring **kind → schema identity only**. Narrow scope is the point: if the declaration grows to carry compiler phase, loader selection, or exception behaviour, the hardcoded dispatch table has merely been relocated into an artifact without improving the architecture.
2. Author and bind `SCHEMA_STRUCTURE_V0` (the file exists, unloaded). Closing it validates build manifests — `artifact_discovery`, `layer_definitions`, `identity_rules`, `import_surface`, `output_configuration`. Highest rejection risk against an unseen manifest.
3. Wire the standing gate: census per commit expecting DEAD = 0; mutation as adjudicator for disputed keys. Resolve F3 first — a gate resting on a hash field that is always empty is weaker than it appears.

**Exit gate.** Both compiles green; `graph_address_hash` identical across the dispatch relocation (it must be a semantic no-op); census clean across all kinds.

**At domain migration (mandatory validation).** Compile both user domains; confirm no manifest key is rejected by `SCHEMA_STRUCTURE_V0`; run the census over their registries; re-adjudicate every F2-qualified DEAD verdict now that the runtime-invariant path is exercised.

---

## Cadence note

Mutation cannot be the per-commit gate — 713 key paths × a full compile each is hours. Census per commit (static, seconds); mutation nightly or on census dispute.

## No exemption list

If a key has no consequence beyond being tolerated, it does not belong in the schema. Every permitted key must be required, resolved, or consumed — each of which makes it LIVE under mutation. An exemption list is the exact mechanism that produced the current state: a category of key that is present, blessed, and inert.
