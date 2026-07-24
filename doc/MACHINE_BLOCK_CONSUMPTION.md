# Machine-Block Consumption

What the compiler actually reads out of a `## Machine` block, what it merely carries, and how to prove which is which for any key.

---

## 1. How artifacts are read

There is exactly one reader. `S1_EXTRACT` (`compiler/stages/s1_extract.py`) does all artifact ingestion; no later stage opens a source file.

```
STRUCTURE_DISCOVERY_V0 + STRUCTURE_<BUILD>_CONFIG   → layers to scan
        ↓  LayerResolver.resolve_layer_root(layer)
platform/registry/FB_*/{constitutions,invariants,structures,schemas}/*.md
        ↓  filename_pattern → artifact_type, name, version
STRUCTURE_IDENTITY_V0 derivation rules              → namespace
        ↓
namespace::ARTIFACT_CODE_Vn                         → Node.fqdn
```

`FB_*` directories are **not** special-cased anywhere in the compiler. They are ordinary subdirectories under a layer root; the recursive `rglob("*.md")` in `_scan_layer` finds them, and the `module_path` derived from their relative path is what the identity rules match on to produce a namespace (`fb.topology`, `fb.constitution`, …). Renaming an `FB_*` folder changes the namespace and therefore every FQDN under it — nothing else.

### The Machine block

```python
_MACHINE_BLOCK_PATTERN = re.compile(
    r"^## Machine\s*\n+```yaml\s*\n(?P<machine_yaml>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
```

The **first** fenced `yaml` block under the **first** `## Machine` heading is parsed with `yaml.safe_load` and becomes `Node.frontmatter` — wholesale, uninspected. There is no schema gate at parse time. A missing block is `E101`; a non-dict is `E101`; `status: deprecated` drops the artifact with a warning.

Everything below `## Machine` in the file — Purpose, Validation Rules, Rationale, Version History — is prose. It is captured into `Node.metadata["content"]` and echoed into the canonical projection, and is never parsed.

### What S1 does with the parsed block

Only three things:

| Action | Keys involved |
|---|---|
| Hash the raw file | (whole file bytes → `content_hash`) |
| Store verbatim | every key → `Node.frontmatter` |
| Build `REFERENCES` edges | `vocabulary_id`, `governed_by`, `structure`, `runtime_binding`, `transform` (scalar or list), `transforms[]`, `side_effects[]`, and `core.bindings` keys |

Reference extraction is a **recursive scan for those field names at any depth**, not a schema walk. Any FQDN-shaped value under any other key is invisible to the graph.

This is the crux: **S1 stores the whole block but interprets only reference fields.** Every other key is dead unless some later stage or assertion handler explicitly names it.

---

## 2. Where governance keys go — and don't

### INVARIANT

`S4_GOVERN` derives an executable `ASSERT` descriptor from each INVARIANT node (`_derive_assert`). It reads exactly two keys:

```python
inv_code = inv_node.frontmatter.get("invariant_code") or inv_node.artifact_code
proj     = inv_node.frontmatter.get("assert_projection") or {}
module   = proj.get("handler") or f"{_HANDLER_MODULE_PREFIX}.{assert_code.lower()}"
```

- `invariant_code` — and even this falls back to the filename-derived `artifact_code`, so it is redundant in practice.
- `assert_projection.*` — `handler`, `enforcement.{level,order,phase,scope}`, `scope.applies_to`, `ci_override.level`, `allowed_capability_*`. These are copied into the synthesized assert frontmatter and read by handlers.

The rule the invariant *states* is not read. Enforcement logic lives entirely in the Python handler at `compiler/governance_engine/assertions/handlers/assert_<name>.py`, bound by naming convention. `core.description`, `core.rule`, `core.enforcement_stage`, `core.scope`, `core.violation_response`, `core.anti_patterns`, `core.clarification`, `examples`, `extensions.error_codes` are documentation.

Two narrow exceptions, both in handlers rather than the compiler core:

- `assert_runtime_invariant_wired_v0` reads `core.enforcement_stage` to select invariants tagged for the runtime stage.
- `ipm.py` reads `core.invariant_code` / `core.rule` / `core.summary` when emitting the IPM projection — a documentation projection, not an execution input.

### CONSTITUTION

A constitution contributes **its identity and its `governed_by` edge**. The `rules:` list — `rule_id`, `applies_to`, `constraint`, `enforced_by` — is read in exactly one place, as an emptiness check on one specific artifact:

```python
# assert_compiler_governance_declared_v0.py
rules = frontmatter.get("rules", [])
if not rules:  # violation: "governance declaration surface is empty"
```

Nothing ever reads a rule's `constraint` or follows its `enforced_by` binding. `core.enforcement_model`, `core.governs` (outside one topology handler), and `constitution_code` are inert.

Governance authority flows through `governed_by` → `GOVERNED_BY` edges, not through rule text.

### STRUCTURE

The most genuinely consumed kind. `structure_loader.load_structure_artifact` reads these blocks as live configuration: `discovery.layers`, `discovery.rules.{filename_pattern,excluded_directories}`, `identity.fqdn.namespace.derivation.rules`, `artifact_discovery.{search_layers,artifact_types,import_surface}`, `layer_definitions`, `output_configuration.*`. Changing one changes what compiles.

### CT / CS / CC / WF

Also genuinely consumed. `machine.implementation` (module + callable), input/output contracts, `core.pipeline`, and `core.bindings` are lifted into `ct_ir` / `cs_ir` / pipeline structures in `S5_CONSTRUCT` and materialized into the snapshot. The dead-key ratio here is roughly 1 in 5, versus 4 in 5 for INVARIANT.

---

## 3. Verifying it yourself

Two tools, in `protocol_compiler/scripts/`. The first narrows the field; the second proves the verdict.

### Static census — `machine_key_census.py`

Flattens every Machine block into dotted key paths, then classifies each leaf by whether its name appears as a **string literal** in consumer source (a dict key can only be read via a literal):

```bash
python scripts/machine_key_census.py                      # whole registry
python scripts/machine_key_census.py --kind INVARIANT     # one artifact kind
python scripts/machine_key_census.py \
    --roots ../platform/capability_transforms \
    --src ../protocol_compiler/compiler ../protocol_runtime
```

Three buckets: `READ` (name appears as a literal — *candidate* consumption), `WEAK` (bare identifier only, likely coincidence), `DEAD` (name appears nowhere).

Its limit: it matches names, not contexts. `"scope"` is a literal in the source, so `core.scope` on a constitution lands in `READ` — but the only `scope` anyone reads is `assert_projection.scope`. `READ` is an upper bound on consumption, never a proof of it.

Registry-wide, by kind:

| Kind | READ | WEAK | DEAD |
|---|---:|---:|---:|
| INVARIANT | 41 | 1 | 168 |
| STRUCTURE | 16 | 2 | 18 |
| CONSTITUTION | 15 | 2 | 4 |
| SURFACE_CONTRACT | 8 | 0 | 1 |
| CT / CS / workloads | 401 | 25 | 100 |

### Mutation verification — `machine_key_mutation.py`

The definitive test. Delete the key, recompile, compare the snapshot:

```bash
python scripts/machine_key_mutation.py \
    --artifact ../platform/registry/FB_TOPOLOGY/invariants/INVARIANT_TOPOLOGY_ACYCLIC_V0.md \
    --key core.anti_patterns --key core.enforcement_stage --key governed_by
```

The artifact is restored and the snapshot rebuilt in a `finally` block, so the tree is left clean either way. Verdicts: `LIVE` (compile fails, or the snapshot changes semantically), `DEAD` (compiles clean, snapshot identical), `ABSENT`.

**The fingerprint is the whole difficulty.** `content_hash` is a SHA-256 of the entire raw file, so any edit — even to a comment — changes it, and it propagates into `canonical/*.json`, `canonical/metadata.json:projection_hash`, and the trust attestation. Compare those naively and every key looks live. The fingerprint therefore excludes:

- `content`, `content_hash`, `frontmatter` in canonical projections — verbatim echoes of the source
- `projection_hash`, `tokenized_projection_hash`, `attestation_hash`, `signature`, `signed_at` — rollups over those echoes, plus per-build timestamps

and keeps `graph_topology_hash` / `graph_address_hash` — the compiler's own identity for the typed graph, derived from nodes, addresses and edges rather than source bytes. If those are unchanged, the key contributed nothing to compiled meaning.

Deleting `core.anti_patterns` from `INVARIANT_TOPOLOGY_ACYCLIC_V0` changes exactly three files, and within them only:

```
canonical/invariants/…ACYCLIC_V0.json   content, content_hash, frontmatter
canonical/metadata.json                 projection_hash
trust/…/structure_attestation.json      signed_at
```

`graph_topology_hash` and `graph_address_hash` are untouched — the semantic graph is bit-identical.

### Measured results

`INVARIANT_TOPOLOGY_ACYCLIC_V0`:

| Key | Verdict |
|---|---|
| `governed_by` | LIVE |
| `invariant_code` | DEAD (falls back to `artifact_code`) |
| `core.description` | DEAD |
| `core.enforcement_stage` | DEAD |
| `core.violation_response` | DEAD |
| `core.anti_patterns` | DEAD |
| `core.clarification` | DEAD |

`CONSTITUTION_WORKFLOW_V0`:

| Key | Verdict |
|---|---|
| `constitution_code` | DEAD |
| `core.description` | DEAD |
| `core.scope` | DEAD |
| `core.governs` | DEAD |
| `core.enforcement_model` | DEAD |
| `rules` (entire list, incl. all `enforced_by`) | DEAD |

The whole Machine block of that constitution can be deleted down to `fqdn` + `governed_by` and the snapshot is unchanged.

---

## 4. Reading the result

Dead does not mean wrong. A governance artifact has two audiences, and only one of them is the compiler.

- The **prose and the `core:` narrative** are for a human or a reviewer establishing that the rule was declared before it was enforced.
- The **`assert_projection`** and the handler module are what the compiler executes.

The real exposure is that these two can drift apart with nothing detecting it. An invariant's `core.rule` can say one thing while `assert_<name>.py` enforces another, or nothing; a constitution's `rules[].enforced_by` can name an assertion that does not exist. Neither is caught, because neither field is read.

If declaration-to-enforcement correspondence is meant to be load-bearing, the fix is to make it load-bearing: read `rules[].enforced_by` and require it to resolve to a derived ASSERT, or drop the field. What cannot be sustained is a field that looks binding and is not.

The narrower cleanups, if the intent is to shrink the authored surface:

- `invariant_code` and `constitution_code` duplicate the filename and are already ignored — the fallback path is the real one.
- `core.enforcement_stage` is read by exactly one handler; everywhere else it is decoration.
- `core.anti_patterns`, `core.clarification`, `examples` belong under the prose heading, where their status as documentation is unambiguous.