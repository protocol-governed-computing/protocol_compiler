# Domain Governance Import — Design

Closes finding #1: a domain build compiles ungoverned. This designs the missing half of the import model — governance imported as checked protocol state — without touching the capability half that already works.

Design only. No code changed.

---

## 1. The one import contract

A domain build imports two things from the platform, for two different reasons, with two different fates:

| imported | why | enters graph | asserted on | re-emitted to domain snapshot |
|---|---|---|---|---|
| **capabilities** (CS/CT) | the domain must *run* | yes | yes (as subjects) | **yes** — static link, runtime needs them |
| **governance** (INVARIANT/CONSTITUTION) | the domain must be *checked* | yes | no (they are the asserters) | **no** — checking state, not artifact set |

The capability half exists (`_inject_imported_capabilities`). This adds the governance half and states the asymmetry explicitly:

> Capabilities are imported **as executable substrate** — linked into the domain and emitted.
> Governance is imported **as checked protocol state** — it acts on the domain graph and is discarded before materialize.

`metadata.imported` alone cannot express this — both are imported. The design introduces `metadata.import_role ∈ {execution, governance}`. `execution` → emitted (today's behaviour). `governance` → asserted then dropped at S7.

---

## 2. Scope authority — the one real decision

Platform-only invariants (`COMPILER_NO_EXECUTION`, `HANDLER_REGISTRY_CLOSED`, `SCHEMA_CONFORMANCE`, `ASSERT_PARITY`, `GOVERNANCE_DECLARATION_RESOLVES`, `IDENTITY_FQDN_CONSISTENCY`, `UNIQUE_ARTIFACT_ID`, `ARTIFACT_CONTENT_HASH_DECLARED`, `COMPILER_GOVERNANCE_DECLARED` — 9 of 72) govern the compiler and the governance surface itself. They have no domain subject and must never be imported. The other ~63 govern CT/CS/CC/WF/RB/AC/topology and must reach a domain build.

Today that split is a **heuristic** — the handler string-matches `is_domain_build and "PLATFORM" in scope`, and only 2 invariants declare `assert_projection.scope.applies_to` at all. Inference is the defect we spent this whole effort removing. The split must be **declared**.

> **Correction (stage 3 finding).** The original design proposed reusing `scope.applies_to` as the applicability field. That was wrong: `scope.applies_to` already carried a distinct meaning — the **layer/surface** an assertion governs (`PLATFORM`, a domain layer), read by the surface-closure handlers. Overloading it silently made platform surface-closure vacuous. The two axes are now separate fields, one meaning each:
>
> - **`assert_projection.applies_to_kinds`** — the artifact **kinds** an invariant governs. Authoritative for the import filter. Required on every invariant.
> - **`assert_projection.scope.applies_to`** — the **layer/surface** an invariant governs. Optional; present only where a surface-scoped handler needs it. A layer-scoped invariant is surface-specific and is *not* generically imported — each surface declares its own (see §2b).

**Applicability is *derived* from set intersection on `applies_to_kinds`, not separately declared:**

```
domain-instantiated kinds = {WF, CC, CS, CT, RB, AC, IN, EV, TI, TE}

invariant is domain-applicable  ⟺  applies_to_kinds ∩ domain-instantiated ≠ ∅
                                AND no layer/surface scope.applies_to (§2b)
```

### 2b. Surface-owned invariants — not blanket-imported

A surface-closure invariant (`CT_SURFACE_CLOSED`, `CS_SURFACE_CLOSED`) declares an *allowed set* that is a property of one surface. Importing the platform's into a domain would check domain CTs against the *platform's* allowed list — meaningless. Per rule-ownership doctrine, a domain reuses the generic closure *handler* but supplies its own *allowed list* via its own native invariant.

The declared signal is the layer scope: an invariant with `scope.applies_to` is surface-specific and excluded from the generic import. The domain authors its own (e.g. collatz's `INVARIANT_CT_SURFACE_CLOSED_WORKLOAD_V0`, `scope.applies_to: [WORKLOAD]`, allowed = its own CTs) — a native domain invariant that runs against the domain's surface. Reference-closure invariants (`PROTOCOL_SURFACE_CLOSED`, `BINDING_SURFACE_CLOSED`) carry no layer scope and *are* imported: they check that references resolve, which is surface-independent.

**The scope vocabulary is closed and every token is concrete — there is no "all" token.** This is the patch: a token that reads as "all" but means "all platform-produced" is exactly the ambiguity class this effort removes, so it does not exist. The vocabulary is:

| token group | tokens | in domain-instantiated set |
|---|---|---|
| executable / instantiable kinds | `WF` `CC` `CS` `CT` `RB` `AC` `IN` `EV` `TI` `TE` | yes |
| platform-produced governance/structural kinds | `INVARIANT` `CONSTITUTION` `STRUCTURE` `SURFACE` `VOCAB` `SCHEMA` | no |
| non-artifact build scopes | `COMPILER` `TEST_DATA` `SNAPSHOT` | no |

- `ALL_ARTIFACTS` is **removed**. An invariant that governs every kind enumerates them; because that enumeration necessarily contains domain kinds, such an invariant is domain-applicable, which is correct (identity hygiene, FQDN-only references, and vocabulary casing genuinely apply to domain artifacts). Enumeration is verbose but has no hidden meaning.
- `PLATFORM` is **removed** as a scope token. It was a build scope masquerading as an artifact scope — the collision the inventory exposed. Build-scope is now *derived* from kind intersection, never declared. `is_domain_build and "PLATFORM" in scope` is retired.
- `COMPILER` names compiler self-governance honestly (`COMPILER_NO_EXECUTION`, `HANDLER_REGISTRY_CLOSED`, content-hash, governance-declared). It is a real scope — the compiler and its build — not a synonym for "all," and it is not in the domain-instantiated set, so these stay platform-only by construction rather than by special case.

Truly platform-only after this: the four `COMPILER`-scoped self-governance invariants, and the two governance-artifact invariants (`ASSERT_PARITY` → `INVARIANT`, `GOVERNANCE_DECLARATION_RESOLVES` → `CONSTITUTION`/`INVARIANT`) whose subjects a domain never natively carries. Everything governing CT/CS/CC/WF/RB/AC/IN/EV and identity/reference/vocabulary hygiene is domain-applicable.

This is the same move as `STRUCTURE_SCHEMA_DISPATCH_V0`: replace a dictionary/heuristic in compiler code with a declaration the compiler follows, reusing `scope.applies_to` rather than adding a second scope axis.

**Cost:** all 72 invariants get an authored, concrete `scope.applies_to`; the 5 that already declare one are normalized off `PLATFORM`/`ALL_ARTIFACTS`; `SCHEMA_INVARIANT_V0` promotes the field from optional to required with the closed token enum. That is a Phase-1-class closure of the invariant schema and the bulk of the work.

---

## 3. Mechanism, by stage

### S1 — inject
New `_inject_imported_governance`, mirroring `_inject_imported_capabilities`:

1. Read the platform compiled canonical (`invariants/`, `concerns/`).
2. For each invariant, parse `assert_projection.scope.applies_to`; keep it only if domain-applicable (§2).
3. Inject the invariant node **and its governing constitution** (so `governed_by` resolves in-graph), each with `metadata = {imported: True, import_role: "governance", import_domain: "platform"}`.

Governing constitutions are imported transitively so the reverse-closure invariant (if itself imported) stays satisfiable.

### S2 — survive, don't drop
Two changes:
- A governance node is now present in the graph, so its `GOVERNED_BY` edge resolves to an in-graph target instead of hitting the drop path.
- Imported governance nodes are **excluded from topology typing** — they are asserter state, not domain topology. An imported invariant never becomes a WF/CC subject or acquires execution edges.

### S4 — govern
- **Schema conformance:** skip nodes with `import_role == "governance"`. They were validated at platform compile; re-validating them in the domain context is redundant and risks a platform-only schema rule firing in a domain build.
- **Assertions:** structurally unchanged. `_execute_assertions` already iterates INVARIANT nodes and derives ASSERTs; once imported invariants are present it runs them. `is_domain_build` is already in context. The `"PLATFORM" in scope` skip logic in the surface-closure handlers is *retired* in favour of the declared applicability filter from §2 — an invariant that reaches S4 in a domain build is, by construction, domain-applicable.
- **Handler resolution:** `HANDLER_REGISTRY` is static and global; imported invariants resolve their derived-ASSERT handlers with no change.

### S7 — don't emit
Materialize excludes `import_role == "governance"` nodes. Governance checked the domain graph; it is not part of the domain's artifact set and must not appear in the domain snapshot (unlike statically-linked capabilities). This keeps the assembled snapshot's domain artifact set exactly what the domain authored.

### Self-application boundary
The one subtlety: an imported invariant is an **asserter**, never a **subject**. `import_role == "governance"` is the marker every subject-iterating check (schema conformance, reverse-closure, surface-closure discovery) filters out. Without this an imported invariant would be validated, counted, and cross-checked as though the domain had authored it.

---

## 4. What this predicts

The collatz domain's 25 artifacts have never faced an assertion. First governed compile **will surface real violations** — that is the success signal, not a regression. Expected live checks against the domain: CT surface closure, CT output-contract match, CC binding validity, CC inputs satisfied, WF CC-only nodes, WF execution-path validity, topology acyclicity, AC well-formedness, vocabulary symbol closure. Vacuous (no subject in the Phase-1 collatz subset): CS-traceability, RB policy conformance, transport.

The domain build is expected to go **red on first run**, then be driven to green by fixing the domain artifacts — the same arc the platform surface just went through.

---

## 5. Staging

1. **Declare scope** — author `assert_projection.scope.applies_to` on all invariants; require it in `SCHEMA_INVARIANT_V0`; platform build stays green (additive). *Verifiable in isolation.*
2. **Inject + survive + don't-emit** — S1 injection, S2 survival, S7 exclusion, `import_role`. Platform build unaffected (no import_surface); domain build now carries governance nodes. *Graph-hash of the platform build must be identical — proof this is domain-only.*
3. **Govern** — retire the heuristic skip; let S4 run imported assertions. Domain build goes red. *Drive collatz to green.*
4. **Retire `is_domain_build` string-scope** once the declared filter subsumes it.
5. **Bind provenance** — S9 writes `imported_governance` (§6) into the domain attestation; the assembler/runtime verify chain checks the closure hash. Sealed last, after the governance mechanism is proven.

Each stage is independently verifiable; only stage 3 changes the domain outcome, and it changes it to the correct one.

---

## 6. Governance provenance — bound into the domain attestation

Imported governance is discarded before materialize, so the domain snapshot's content hash excludes it. But the domain was *checked against* a specific platform governance closure. If that closure is not bound into the domain's attestation, a domain could later be re-verified — or a runtime could accept it — under different governance than it was compiled against, and the "governed" claim would be unfalsifiable. Provenance is therefore part of this contract, not an afterthought.

**The binding.** At S1 injection the domain reads the platform snapshot's identity alongside the governance nodes it imports, and carries it as build metadata:

```
imported_governance:
  domain: platform
  governance_closure_hash: <sha256>      # closure over the imported governance set
  platform_snapshot_id:    <id>          # the platform snapshot the import was taken from
```

`governance_closure_hash` is a canonical digest over the exact set of imported invariant + constitution nodes (FQDN + content_hash of each, sorted) — not the whole platform snapshot, so it changes only when the *governance* that checked the domain changes, not when unrelated platform capabilities do. It is the domain-scoped analogue of `graph_topology_hash`.

**Where it lives.** S9 ATTEST writes `imported_governance` into the domain's trust attestation. The domain attestation then answers, verifiably: *this domain was compiled clean against exactly this governance closure.* Two consequences:

- Re-verification recomputes the closure hash from the platform surface and MUST match, or the domain is stale-against-governance and fails closed.
- The assembler and runtime already hash-verify the assembled snapshot; the governance-closure hash extends that chain so a domain cannot be paired at runtime with governance it was not compiled under.

**What it deliberately does not do.** It does not re-embed the governance artifacts in the domain snapshot (they remain platform-owned and unemitted, per §1). It binds the *hash*, not the bytes — provenance without duplication. Regenerating the domain against changed platform governance is an explicit recompile that produces a new closure hash, never a silent drift.

This is a trust-model addition and touches S9 and the assembler's verify step; it is staged last (stage 5) so the governance mechanism is proven before its provenance is sealed.

**Stage 5 status: implemented.** The closure hash is computed at S1 over the imported governance set (sorted `fqdn` + `content_hash`), carried in build metadata, and written to the domain attestation as `imported_governance`. The assembler recomputes it from the assembled platform surface and fails closed on mismatch (`_verify_governance_provenance`). Four mutation properties are verified by `scripts/test_governance_provenance.py`: determinism (unchanged governance → identical hash), sensitivity (imported invariant changed → hash changes), **isolation** (platform-only invariant changed → hash unchanged, proving the closure covers exactly the imported set), and enforcement (stale domain against changed governance → assembly fails). The platform build carries no `imported_governance` (nothing imported), so it is unaffected.