# Architectural Findings

Surfaced by the machine-block closure work. Each is independent of that closure and larger than it; none should be folded into it.

---

## 1. Domain builds bypass governance assertions entirely — RESOLVED

**Status: resolved** by the domain governance import (`DOMAIN_GOVERNANCE_IMPORT_DESIGN.md`). A domain build now imports the domain-applicable platform invariants as checked protocol state, runs them against its own artifacts, and drops them before materialize. Collatz is governed by 63 invariants (62 imported + 1 native surface-closure it declares for its own CTs); its assertion coverage is recorded in evidence. The original finding is retained below for provenance.

**Severity: blocking.** A domain build performs no assertion checking.

`S4_GOVERN._execute_assertions` derives its work from INVARIANT nodes in the compiled graph:

```python
invariant_nodes = [n for n in graph.nodes.values()
                   if n.frontmatter.get("artifact_kind") == "INVARIANT"]
if not invariant_nodes:
    return errors, warnings
```

A domain build carries none. Governance imports are resolve-only — tolerated in S1, dropped in S2 — and `_inject_imported_capabilities` lifts only CS and CT. Measured on the collatz reference workload after S2:

```
AC 1 · CC 3 · CT 2 · CS 1 · EV 1 · IN 1 · RB 1 · WF 1 · GOVERNANCE 2
INVARIANT nodes: 0
```

So every platform invariant — CT/CS surface closure, topology acyclicity, CC binding validity, schema conformance — is inert for domain builds. The 25 collatz artifacts pass S4 ungoverned.

Two consequences:

- **A green domain build is a compile proof, not a governance proof.** It should not be cited as evidence that a domain conforms.
- **Platform governance over domain-instantiated kinds can never fire.** AC, WF, CC, RB, IN and EV exist only in domain builds. `INVARIANT_AC_DECLARATION_WELL_FORMED_V0` is correct and correctly scoped, yet has no reachable subject in either build. This is an import-model gap, not a scope error, and it is why the platform surface can appear fully governed while the artifacts that actually execute are not.

The fix is a change to what a domain build imports, which is a compiler and import-model decision.

---

## 2. STRUCTURE is a heterogeneous family, not one kind

20 STRUCTURE artifacts carry **50 distinct top-level keys**, most appearing exactly once. At least five unrelated shapes share the `STRUCTURE_` prefix:

| family | distinguishing keys |
|---|---|
| build configuration | `artifact_discovery`, `layer_definitions`, `output_configuration` |
| discovery / identity master | `discovery`, `identity`, `normalization`, `module_data_roots` |
| federation-boundary contract | `trust_mode`, `placement_mode`, `scheduling_mode`, `security_domain` |
| registry location | `artifact_source_dirs`, `layer_directories` |
| contract structure | `artifact`, `contract`, `required_fields`, `field_types`, `invariants` |

There is no consistent discriminator: `structure_scope` on 3, `artifact_kind` on 5, `status` on 4.

A single `SCHEMA_STRUCTURE_V0` with `additionalProperties: false` over all 50 keys would be a union permitting everything — closed in name, open in fact, and a fresh instance of the defect the closure work removed. Closing STRUCTURE properly requires splitting it into distinct normative kinds first, each with its own schema and its own dispatch entry. That is a normative surface change, and it is the real content of Phase 3.

Until then the four genuinely checkable STRUCTURE rules are enforced by `INVARIANT_STRUCTURE_PATHS_WELL_FORMED_V0`, whose Rule 4 — referenced layers resolve to a declaration — is cross-artifact and could not have been expressed as a per-artifact schema constraint in any case.

---

## 3. Domain references inside the platform surface

Platform STRUCTURE artifacts declare paths into domain registries:

```
domains/blockchain/registry/identity
domains/ai_licensing/registry
domains/agent_governance/registry
```

`platform/CLAUDE.md` states that domain artifacts belong in `pgs::` and MUST NOT appear in this surface, and that any leaked domain reference is resolved by moving it out. These are the same class as `CONSTITUTION_ENTITY_V0`, which was excluded on exactly that basis.

Each needs classifying: either the referenced domain is part of the platform's declared discovery surface — in which case the platform depends on repositories outside its own boundary — or the reference is harvest residue and should be removed.

---

## 4. Transport artifacts are declared but unauthorized

Two artifacts cannot satisfy a closed schema without authoring transport governance, which `protocol_transport/CLAUDE.md` explicitly defers:

> Constitutions, compiler `TI_`/`TE_` kinds, and adapters are later phases and are **not yet authorized** until the standard is accepted.

- `CONSTITUTION_TRANSPORT_V0` declares `rules: []`. Its governance lives entirely in prose, and the four transport invariants that exist are `governed_by` `CONSTITUTION_INVARIANTS_V0` rather than by it — so it governs nothing.
- `SURFACE_CONTRACT_TRANSPORT_SEND_V0` declares `governs: []` with no `capability_id_prefix`, making it reachable by neither exact nor prefix lookup. It canonicalizes a `SEND` op for a transport capability that does not yet exist.

Both are premature placeholders for frozen work. The consistent disposition is the one applied to `CONSTITUTION_ENTITY_V0`: exclude from the normative surface until the owning phase is authorized, and record the exclusion in the harvest ledger. Supplying the missing fields instead would mean authoring transport design decisions inside a closure exercise.

---

## 5. Artifact-identity hashes do not prove assertion equivalence

**Severity: methodology.** Throughout this effort the `graph_topology_hash` / `graph_address_hash` no-op proof was used to show a change was semantically neutral. It is sound for what it measures — the *compiled artifacts* — but it has a blind spot that stage 3 exposed concretely.

Assertions do not write to the graph. They read it and either pass or raise. So a change that alters *what an assertion checks* — even one that silently disables it — leaves every compiled artifact, and therefore every hash, bit-identical. The stage-1 scope overload made the platform CT/CS surface-closure checks vacuous; the platform build stayed green with an identical hash, and the no-op proof did not flag it. The check had stopped checking, and nothing in the artifact identity could show it.

**The rule:** artifact-identity equivalence proves *what was compiled*, never *which invariants verified it*. The two must be evidenced separately.

**Mitigation in place.** S4 now records per-assertion coverage — which derived ASSERTs executed, their pass/fail, violation counts, and whether the enforcing invariant was native or imported — into build metadata and the evidence projection (`assertions_executed`, `assertions_passed`, `assertions_imported`). A build that stops running an assertion now shows a drop in coverage even when its artifact hashes are unchanged.

**Still open.** Coverage records *that* an assertion ran, not *that it would have caught a violation* — a handler can execute and be vacuous (empty subject set). A stronger guarantee is mutation-style assertion testing (perturb an artifact, confirm the expected assertion fires), which the `machine_key_mutation.py` approach could be extended to cover. Recommended before the domain governance model is relied on as a conformance gate.
