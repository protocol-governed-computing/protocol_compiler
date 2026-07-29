# Semantic Alignment — Implementation Spec

Self-contained execution plan for one large checkpoint. Written for a session with **no prior context**. Execute A then B in order. Do not deviate from the acceptance gates.

Work happens on branch **`semantic_alignment`**, already created and checked out on both `software_governance` and `protocol_compiler`. `protocol_runtime` and `snapshot_assembler` are **not touched** — A and B preserve every FQDN value, so the assembled snapshot stays consumable unchanged.

---

## 0. The goal in three sentences

Today an artifact's identity (its FQDN) is *derived from its filesystem folder*: `platform/registry/FB_TOPOLOGY/...` → `fb.topology::...`, via namespace rules in `STRUCTURE_IDENTITY_V0` matched against the module path. That is backwards — a human organization decision is accidentally a protocol-identity decision. This effort makes identity **declared in the artifact** and the folder **discovery-only**, so a file may later move, split, or be renamed without changing what the artifact *is* — while preserving every current FQDN value exactly.

Two deliverables:
- **A — `GOVERNANCE_SURFACE_MAP`**: the standard-facing semantic taxonomy (additive, zero identity risk).
- **B — FQDN/path decoupling**: identity becomes declared; the folder loses semantic authority (provable no-op on identity).

Reference reading (same repo): `pgc_charter/doc/governance_semantic_classification.md` (the concern taxonomy the map realizes).

---

## 1. Invariants to preserve (the acceptance baseline)

Capture these BEFORE any change and prove them AFTER B. They are the definition of "identity unchanged."

| invariant | current value | how to check |
|---|---|---|
| platform `graph_address_hash` | `c00003ce35547b187901c7e6d12a3fe280c07a76eaf08d4deca078b5cc4ecfea` | `canonical/metadata.json` |
| collatz `graph_address_hash` | `7be6d6d3fc7cc22ee1ecacdba0eb09b503b2c55e385eeb8df4e6569cb0a1843e` | domain `canonical/metadata.json` |
| platform FQDN identity map | 178 entries | `vocabulary/platform/reverse.json` byte-identical |
| collatz FQDN identity map | — | `vocabulary/workload/reverse.json` byte-identical |

**Critical subtlety — do NOT use `graph_topology_hash` as the B proof.** B edits artifact files (it inserts a `fqdn:` line), which changes each file's `content_hash`, which changes `graph_topology_hash`. That change is *expected and harmless*. The identity-preservation proof is:

1. `graph_address_hash` **bit-identical** before/after (addressing is a pure function of the FQDN set), and
2. `vocabulary/*/reverse.json` and `forward.json` **byte-identical** before/after (the literal FQDN↔address map).

If those two hold, no artifact's identity changed. `topology_hash` and `content_hash` differences are the source edits, not identity drift.

Re-capture the baseline at execution time in case earlier commits shifted it:
```bash
cd protocol_compiler && ./compile.sh >/dev/null && ./compile_domain.sh ../conformance_workloads/workloads/collatz >/dev/null
cp ../software_governance/snapshot/compiled/vocabulary/platform/reverse.json /tmp/base_platform_reverse.json
cp ../conformance_workloads/workloads/collatz/snapshot/compiled/vocabulary/workload/reverse.json /tmp/base_workload_reverse.json
python -c "import json;print('platform',json.load(open('../software_governance/snapshot/compiled/canonical/metadata.json'))['graph_address_hash'])"
python -c "import json;print('collatz ',json.load(open('../conformance_workloads/workloads/collatz/snapshot/compiled/canonical/metadata.json'))['graph_address_hash'])"
```

---

## 2. Phase A — GOVERNANCE_SURFACE_MAP

**Location:** `platform/doc/GOVERNANCE_SURFACE_MAP.md` (+ a machine-readable `platform/doc/governance_surface_map.yaml`). It lives in `doc/`, **not** `registry/`, so it is not compiled, adds no node, and is therefore hash-neutral. (It may become a compiled artifact in a future version; not now.)

**Why here:** `platform/CLAUDE.md` restricts `registry/` to compiled normative declarations; a semantic map *about* the registry is documentation and belongs in `doc/`.

**Content — for every FB and every constitution/invariant, a coordinate tuple:**
```yaml
- artifact: fb.topology::INVARIANT_TOPOLOGY_ACYCLIC_V0
  semantic:
    domain: protocol_composition        # top-level concern family (§7 target map)
    concern: topology
    property: acyclicity
    lifecycle: compile                  # declare | compile | seal | execute | evolve
    enforcement_locus: compile_composition   # compile_composition | snapshot_declaration | runtime_execution | meta_process
    authority: constitution
  coverage:
    status: implemented                 # implemented | intentionally_deferred | not_applicable | process_enforced
```

**Required sections of the map:**
1. **The governance universe** — the concern taxonomy from `governance_semantic_classification.md §7` (Declaration / Composition / Execution{semantics,envelope} / State / Evolution / Meta-governance).
2. **Per-artifact coordinates** — every artifact classified (pull the inventory: 12 FBs; use the grounded table in §3 of the classification doc as the FB-level seed, then classify each artifact).
3. **Semantic-concept → current-FB identity mapping** — e.g. `execution_envelope.placement → FB_EXECUTION_PLACEMENT → fb.execution_placement::`.
4. **Coverage ledger** — every (lifecycle × concern × enforcement_locus) cell resolves to exactly one of `implemented | intentionally_deferred | not_applicable | process_enforced`; anything else is a declared gap. Known dispositions to record: transport = `intentionally_deferred` (frozen phase); ENTITY/state at platform = `not_applicable` (domain-owned); `FB_CHANGE_MGMT` = `process_enforced`.
5. **Known composites** — `FB_CONSTITUTION` (meta-kernel + build machinery + schema registry) and `FB_TOPOLOGY` (composition + runtime-execution doctrine) are each multiple concerns in one boundary; the map lists each artifact under its true concern regardless of folder.

**A acceptance gate:** platform + collatz compile unchanged; `graph_address_hash` AND `reverse.json` byte-identical to baseline (proves A added no compiled surface).

---

## 3. Phase B — decouple FQDN from folder path

Identity becomes declared; the folder becomes discovery-only. FQDN **values are preserved** — this is a mechanism change, not a rename.

### B1 — populate authoritative `fqdn:` on every registry artifact

Write a migration script `protocol_compiler/scripts/populate_declared_fqdn.py`:
- For every `*.md` under `software_governance/registry/**` and `conformance_workloads/workloads/collatz/registry/**` (135 platform + collatz domain artifacts):
  - Compute the artifact's **current path-derived FQDN** exactly as the compiler does today: namespace from the `FB_<NAME>` folder (platform) or the manifest `identity_rules` (collatz → `workload`), `artifact_code` from the filename (`filename_pattern`). This value must equal what the compiler already produces — verify against `reverse.json`.
  - Insert `fqdn: <derived>` as the **first key** of the `## Machine` YAML block if not already present and equal. Idempotent.
- The script prints any artifact whose declared value would differ from the compiled `reverse.json` entry — there must be **zero** such; a difference is a bug in the script, not a real identity change.

Note: the machine-block closure work earlier removed some redundant `fqdn:`/`*_code:` fields as path-derived duplicates. B1 reintroduces `fqdn:` deliberately — now it is *authoritative*, not redundant.

### B2 — make the identity declaration constitutional

Amend `platform/registry/FB_CONSTITUTION/invariants/INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0.md`:
- Current core principle reads: *"Identity derives from structure, never invented."* **Reverse it** to: *"An artifact's identity is declared by its authoritative `fqdn`. The namespace MUST be an authorized namespace. The filesystem location has no semantic authority over identity."*
- Keep the structural check `fqdn == namespace::artifact_code`.

Add `platform/registry/FB_CONSTITUTION/invariants/INVARIANT_FQDN_NAMESPACE_AUTHORIZED_V0.md`: the declared namespace MUST appear in the authorized namespace set. The authorized set is the namespace list already in `STRUCTURE_IDENTITY_V0` (23 rules) — repurposed from *derivation rules* to an *authorization allowlist*. Domain namespaces (e.g. `workload`) are authorized via the domain manifest's `identity_rules` (unchanged mechanism).

Add temporary `platform/registry/FB_CONSTITUTION/invariants/INVARIANT_IDENTITY_MIGRATION_CROSSCHECK_V0.md`: declared `fqdn` MUST equal the path-derived value. **This is a migration assertion only** — it proves the switch changed no value. It is retired in B6. Do not leave it permanent, or the folder remains secretly authoritative.

Author handlers for the two new invariants in `protocol_compiler/compiler/governance_engine/assertions/handlers/` and register them in `handlers/__init__.py` (`HANDLER_REGISTRY`). Give both `assert_projection.applies_to_kinds` covering all kinds (identity applies universally) and a layer scope only if platform-specific. Follow the existing handler pattern (`assert_*_v0.py`, `execute(artifacts, ctx) -> {violations}`).

### B3 — compiler reads declared identity

In `protocol_compiler/compiler/stages/s1_extract.py`:
- `_derive_fqdns` (line ~403): keep it, but rename its output to the **path-derived cross-check value** — store as `artifact["derived_fqdn"]` instead of `artifact["fqdn"]`/`artifact["namespace"]` being authoritative.
- `_parse_artifact_to_node` (line ~593, uses `artifact["fqdn"]` at ~606): read the **declared** `frontmatter["fqdn"]` as the authoritative node identity. Split it into namespace + code. If the declared `fqdn` is absent → error `E104` (identity must be declared). Set the node's `fqdn`/`namespace` from the declaration.
- Pass both declared and `derived_fqdn` into the graph/metadata so the cross-check invariant (B2) can compare them at S4. Simplest: stash `derived_fqdn` in `node.metadata["derived_fqdn"]`.
- The order dependency: `_derive_fqdns` currently runs before parsing. The declared `fqdn` is only available after the machine block is parsed. Restructure so the machine block is parsed (or pre-scanned for `fqdn:`) before identity is finalized — either move the `fqdn` read into `_parse_artifact_to_node` and have it own identity, or pre-parse the block in `_derive_fqdns`.

Keep the change minimal and behavior-preserving: with B1 populated, declared == derived for every artifact, so the resulting graph is identical in FQDN set and addressing.

### B4 — prove the no-op

```bash
cd protocol_compiler && ./compile.sh && ./compile_domain.sh ../conformance_workloads/workloads/collatz
diff <(python -m json.tool ../software_governance/snapshot/compiled/vocabulary/platform/reverse.json) <(python -m json.tool /tmp/base_platform_reverse.json) && echo "PLATFORM IDENTITY PRESERVED"
diff <(python -m json.tool ../conformance_workloads/workloads/collatz/snapshot/compiled/vocabulary/workload/reverse.json) <(python -m json.tool /tmp/base_workload_reverse.json) && echo "COLLATZ IDENTITY PRESERVED"
python -c "import json;assert json.load(open('../software_governance/snapshot/compiled/canonical/metadata.json'))['graph_address_hash']=='c00003ce35547b187901c7e6d12a3fe280c07a76eaf08d4deca078b5cc4ecfea', 'ADDRESS HASH DRIFT'; print('platform address hash preserved')"
```
Both `reverse.json` diffs empty and both address hashes identical ⇒ identity provably unchanged. Also confirm the migration cross-check invariant PASSES (declared == derived everywhere) and both builds are green/Verified/Attested. `graph_topology_hash` WILL differ (files edited) — expected, not a failure.

If any FQDN differs: stop. B1 mis-derived a value; fix the script, do not "accept" the diff.

### B5 — regression

`cd protocol_compiler && python -m pytest scripts/testbed -q` (expect 16 passed). `cd ../protocol_runtime && python -m pytest testbed -q` (expect 59 passed — runtime untouched, snapshot values preserved). `python tools/pgc_env_check.py` (no `pgs_*`). Full pipeline: compile → compile_domain → assemble → run.sh → WF exec, all green.

### B6 — retire the derivation and the cross-check

Once B4 passes:
- Demote path-derivation to **discovery/default only** — it may remain as a convenience that suggests a namespace when authoring, but it is no longer authoritative and its mismatch is no longer an error.
- **Retire `INVARIANT_IDENTITY_MIGRATION_CROSSCHECK_V0`** (delete the artifact + handler + registry entry). Prove the build still green after removal.
- Final state: identity is declared; namespace must be authorized; folder has no identity authority. Re-run B4's identity proof once more as the closing gate.

---

## 4. What NOT to do

- **Do not reorganize or rename any folder.** That is Phase C (later, deliberate, post-blockchain). B keeps every file exactly where it is.
- **Do not change any FQDN value.** B preserves identity; it only changes where identity comes from. `fb.topology::X` stays `fb.topology::X`.
- **Do not use `graph_topology_hash` as the B proof** (see §1). Use `graph_address_hash` + `reverse.json` byte-identity.
- **Do not make the migration cross-check permanent** (§B6).
- **Do not touch `protocol_runtime` or `snapshot_assembler`.** If either needs a change, the no-op has failed — stop and diagnose.

---

## 5. Scope — files touched

**platform (`semantic_alignment`):**
- `doc/GOVERNANCE_SURFACE_MAP.md`, `doc/governance_surface_map.yaml` (A, new)
- `registry/**/*.md` — `fqdn:` populated on ~135 artifacts (B1)
- `registry/FB_CONSTITUTION/invariants/INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0.md` (amended, B2)
- `registry/FB_CONSTITUTION/invariants/INVARIANT_FQDN_NAMESPACE_AUTHORIZED_V0.md` (new, B2)
- `registry/FB_CONSTITUTION/invariants/INVARIANT_IDENTITY_MIGRATION_CROSSCHECK_V0.md` (new then deleted, B2/B6)
- `registry/FB_CONSTITUTION/structures/STRUCTURE_IDENTITY_V0.md` (semantics: derivation → authorization allowlist)
- constitution rule bindings for the two new invariants (add to the governing constitution's `rules`)

**protocol_compiler (`semantic_alignment`):**
- `compiler/stages/s1_extract.py` (B3 — declared identity)
- `compiler/governance_engine/assertions/handlers/assert_fqdn_namespace_authorized_v0.py` (new)
- `compiler/governance_engine/assertions/handlers/assert_identity_migration_crosscheck_v0.py` (new then deleted)
- `compiler/governance_engine/assertions/handlers/__init__.py` (register/unregister)
- `scripts/populate_declared_fqdn.py` (B1, migration tool)

**untouched:** `protocol_runtime`, `snapshot_assembler`, `pgc_charter`.

---

## 6. Sequence & commit points

1. Baseline capture (§1) → commit nothing.
2. **A** → verify hash-neutral → commit `software_governance`: "semantic surface map (additive)".
3. **B1** populate fqdn → **B2** constitution+invariants+handlers → **B3** compiler → **B4** prove no-op. Commit `software_governance` + `protocol_compiler` together: "declare identity; folder becomes discovery-only (identity preserved)".
4. **B6** retire cross-check + derivation authority → prove green → commit: "retire path-derived identity".
5. Update `pgc_charter/doc/governance_semantic_classification.md` §10/§13 to note identity is now declared (small edit; that repo is not branched — coordinate or defer).

After this lands, `pgs_blockchain` migration declares its FQDNs natively from day one and never couples identity to folders — that is the strategic payoff.

---

## 7. One-line contract

**A file may move without changing what the artifact is; identity changes only when the declared identity changes.** B makes that true; A makes the semantic space explicit; C (later) rearranges folders freely because neither identity nor the standard depends on them.
