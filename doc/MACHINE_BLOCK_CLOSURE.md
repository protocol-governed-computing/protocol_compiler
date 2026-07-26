# Closing the Machine-Block Surface

The machine block is a compiler-consumed surface. Anything in it that the compiler does not read is either an unmet obligation or noise, and both are defects. This states the defect precisely and gives the rectification.

---

## 1. The problem

### 1.1 The stated principle

A `## Machine` block declares what the compiler consumes. Prose below it addresses humans. The two audiences are separated by the fence, and the separation is the point: a reader must be able to trust that what is inside the fence is binding.

Today that trust is unwarranted. 168 of 210 key paths on INVARIANT artifacts are inert. `CONSTITUTION_WORKFLOW_V0` can be stripped to `fqdn` + `governed_by` with a bit-identical snapshot. The fence marks nothing.

### 1.2 Three distinct defects, not one

Lumping all dead keys together obscures that they fail in different ways and need different fixes.

**Defect A — Governance theater.** `rules[].enforced_by` names an assertion. Nothing resolves it. A constitution can bind a rule to `ASSERT_DOES_NOT_EXIST_V0` and compile clean. The same holds for `rules[].constraint`, `rules[].applies_to`, `rules[].rule_id`, and `core.enforcement_model`.

This is the severe one. It is not merely unread — it is a *false claim of enforcement*. PGC's central guarantee is that no behavior enters at execution time that was not in the snapshot. The inverse hole is open: declared governance that never enters the snapshot. An invariant's `core.rule` may state one thing while `assert_<name>.py` enforces another, or nothing at all, and no stage can detect the divergence, because the handler is bound by filename convention rather than by the declaration.

**Defect B — Prose inside the fence.** `core.description`, `core.anti_patterns`, `core.clarification`, `examples`, `core.violation_response`. These make no enforcement claim; they are documentation that happens to be typed as YAML. Harmless in isolation, corrosive in aggregate — they are the bulk that makes the fence look substantive and hides Defect A inside it.

**Defect C — Redundant identity.** `invariant_code` and `constitution_code` restate the filename. `_derive_assert` already falls back to `artifact_code`, so the authored value is dead *and* is a second source of truth that can disagree with the filename with no error raised.

### 1.3 Why it happened

Structural, not incidental. `S4_GOVERN._analyze_schema_conformance` validates frontmatter against JSON Schemas with `additionalProperties: false` — a genuine closure mechanism, already working. But it is applied to five kinds only:

```python
schema_file_map = {
    NodeKind.CT: "SCHEMA_CAPABILITY_TRANSFORM_V0.json",
    NodeKind.CS: "SCHEMA_CAPABILITY_SIDE_EFFECT_V0.json",
    NodeKind.CC: "SCHEMA_CAPABILITY_CONTRACT_V0.json",
    NodeKind.WF: "SCHEMA_WORKFLOW_V0.json",
    NodeKind.RB: "SCHEMA_RUNTIME_BINDING_V0.json",
}
```

There is no `SCHEMA_INVARIANT_V0` and no `SCHEMA_CONSTITUTION_V0`. The kinds with closed schemas are exactly the kinds with healthy consumption ratios (CT/CS/CC/WF ≈ 4 read : 1 dead). The kinds without are exactly the kinds that rotted (INVARIANT ≈ 1 read : 4 dead).

Two aggravating factors:

- The map is a hardcoded Python dict. Which kinds are schema-governed is itself an undeclared surface, decided in code rather than by a STRUCTURE artifact — the pattern the compiler exists to forbid.
- The governance kinds are the ones that *define* closure for everything else. They are the only kinds exempt from it.

---

## 2. The rectification

No new machinery. Extend a mechanism that already works to the kinds it was never applied to, then add the one check that closure alone cannot give.

### Phase 1 — Close the governance kinds

Author `SCHEMA_INVARIANT_V0.json`, `SCHEMA_CONSTITUTION_V0.json`, `SCHEMA_STRUCTURE_V0.json` (a `SCHEMA_STRUCTURE_V0.json` file exists but is unbound), and `SCHEMA_SURFACE_CONTRACT_V0.json`, each with `additionalProperties: false`, permitting only keys the compiler demonstrably reads.

For INVARIANT that is:

```yaml
fqdn: <ns>::INVARIANT_<NAME>_V<n>
artifact_kind: INVARIANT
version: V<n>
governed_by: <ns>::CONSTITUTION_<NAME>_V<n>
assert_projection:
  handler: <module>                    # optional; convention otherwise
  enforcement: {level, order, phase, scope}
  scope: {applies_to: [...]}
  ci_override: {level}
```

Six top-level keys. Everything else moves below the fence.

For CONSTITUTION, after Phase 2 makes `rules` load-bearing:

```yaml
fqdn: <ns>::CONSTITUTION_<NAME>_V<n>
artifact_kind: CONSTITUTION
version: V<n>
governed_by: <ns>::CONSTITUTION_GOVERNANCE_V0
core:
  governs: [WF, ...]
rules:
  - applies_to: WF
    enforced_by: <ns>::INVARIANT_<NAME>_V<n>
```

Move the `schema_file_map` out of `s4_govern.py` and into a STRUCTURE artifact declaring kind → schema. A hardcoded map deciding which artifacts are governed is the same category of defect as an unread declaration.

**Effect:** Defects B and C become compile errors. Every prose key is rejected at S4. Every redundant identity key is rejected. Enforced mechanically, not by review.

### Phase 2 — Make enforcement claims resolve

Closure alone does not fix Defect A: a schema can permit `enforced_by` while nothing reads it, and the field stays theater. The claim must be resolved.

Add `INVARIANT_GOVERNANCE_DECLARATION_RESOLVES_V0` with handler `assert_governance_declaration_resolves_v0.py`, asserting:

1. Every `rules[].enforced_by` FQDN resolves to an artifact present in the compiled set.
2. Every INVARIANT in scope has a derived ASSERT with a registered handler. `_derive_assert` + `E702` covers the second half; the first is new.
3. Every INVARIANT is named by at least one constitution rule — no orphan invariants enforcing rules nobody declared.

Point 3 closes the loop in the other direction and is what makes the declaration a genuine surface rather than a lookup table.

Retire `assert_compiler_governance_declared_v0`'s emptiness check; it is subsumed.

### Phase 3 — Regression gate

Closure and resolution can both pass while a permissively-written schema readmits dead keys. Wire the existing tools into CI:

```bash
python scripts/machine_key_census.py --kind INVARIANT     # expect DEAD = 0
python scripts/machine_key_mutation.py --artifact <path> --key <k>
```

The census is the fast gate (static, whole-registry, seconds). The mutation verifier is the adjudicator for any key the census disputes — it is the only thing that distinguishes "name appears in source" from "compiler reads this key here". Run the census per-commit; run mutation on the keys it flags.

Nothing enforces `additionalProperties: false` on a *new* schema either. Either assert that property over every schema in `FB_CONSTITUTION/schemas`, or accept the census as the backstop.

---

## 3. Per-key disposition

**INVARIANT**

| Key | Disposition |
|---|---|
| `fqdn`, `artifact_kind`, `version`, `governed_by` | keep — read |
| `assert_projection.*` | keep — read; the only enforcement-bearing block |
| `invariant_code` | delete — restates filename, already falls back |
| `core.rule`, `core.summary`, `core.description` | move below fence |
| `core.enforcement_stage` | decide (§4) |
| `core.scope`, `core.violation_response` | delete — superseded by `assert_projection.scope` / fail-hard doctrine |
| `core.anti_patterns`, `core.clarification`, `examples` | move below fence |
| `extensions.error_codes` | move below fence, or bind to `ErrorCode` and make it resolve |

**CONSTITUTION**

| Key | Disposition |
|---|---|
| `fqdn`, `artifact_kind`, `version`, `governed_by` | keep — read |
| `core.governs` | keep — read by `assert_topology_surface_canonical_v0` |
| `rules[].applies_to`, `rules[].enforced_by` | keep — **promote to load-bearing** (Phase 2) |
| `rules[].rule_id` | delete — no referent |
| `rules[].constraint` | move below fence; the constraint is the invariant it points to |
| `constitution_code` | delete — restates filename |
| `core.description`, `core.scope`, `core.enforcement_model` | move below fence |

---

## 4. One decision to make

`core.enforcement_stage` is read by exactly one handler, `assert_runtime_invariant_wired_v0`, to select invariants tagged for the runtime stage. It is authored on 38 invariants and consulted for a handful.

Either it is a real dimension — in which case it belongs in `assert_projection.enforcement.phase`, which already exists and is already read, and the two should be merged — or it is decoration on 38 artifacts and should be deleted with the one handler repointed at `enforcement.phase`.

Merging into `assert_projection.enforcement.phase` is the better option: one enforcement-parameter block per invariant, no second location, and it eliminates a field that reads as binding on 38 artifacts while binding on few.

---

## 5. What remains outside the fence

Everything currently in `core.description`, `core.anti_patterns`, `core.clarification`, `examples`, and `rules[].constraint` survives as prose under `## Purpose`, `## Validation Rules`, `## Rationale`. Nothing is lost. The change is that it stops claiming to be machine-consumed.

The test after Phase 1 is direct: delete any key from any machine block and the compile fails. If it compiles, the surface is not closed yet.