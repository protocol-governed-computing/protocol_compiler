# Unenforced Rule Triage

Every constitution rule that named no enforcing invariant, adjudicated individually. The test applied to each: *can a compile-time assertion, reading only compiled artifact data, decide this?*

---

## Resolved — 21 rules

### Runtime behaviour (11) → `RUNTIME_ENFORCED`

These describe what execution must do. No compiled artifact carries the fact, so no compile-time assertion can decide them; the runtime enforces them or nothing does.

`EXECUTION_PHASE_ORDER` · `EXECUTION_NO_BUSINESS_LOGIC` · `EXECUTION_NO_SILENT_FAILURE` · `EXECUTION_DECLARED_SIDE_EFFECTS_ONLY` · `EXECUTION_DETERMINISM` · `ADMISSION_READ_ONLY` · `ADMISSION_PRECONDITION_ONLY` · `ADMISSION_DENIAL_IS_GOVERNED` · `POLICY_LOAD_BEFORE_EXECUTION` · `POLICY_IMMUTABLE_DURING_EXECUTION` · `POLICY_EXPLICIT_PROFILE`

### Source-code or process properties (8) → `PROCESS_ENFORCED`

These constrain the compiler's or a handler's *implementation*, or a promotion process. Compiler source is not a compiled artifact, so the compiler cannot assert them about itself from artifact data.

`CONSTRUCTION_CLOSURE_STATIC` · `COMPILER_GATED_PROMOTION` · `ASSERT_PURITY` · `ASSERT_VIOLATIONS_OUTPUT` · `COMPILER_NO_HEURISTICS` · `COMPILER_FQDN_TREE_AUTHORITY` · `COMPILER_RULE_DRIVEN_VALIDATION` · `VOCAB_APPEND_ONLY`

`VOCAB_APPEND_ONLY` is the one worth noting: append-only is a claim about vocabulary *history*, and a single compile sees only the current state. It becomes compiler-checkable only against a prior snapshot.

### Already enforced by an existing invariant (2)

| rule | bound to |
|---|---|
| `ASSERT_BINDS_ONE_INVARIANT` | `fb.conformance::INVARIANT_ASSERT_PARITY_V0` |
| `INVARIANT_DECLARATIVE_ONLY` | `fb.topology::INVARIANT_SCHEMA_CONFORMANCE_V0` |

`INVARIANT_DECLARATIVE_ONLY` became enforceable only in Phase 1: with `SCHEMA_INVARIANT_V0` closed, an invariant cannot carry executable logic because it cannot carry anything undeclared.

---

## Requires new enforcement — 13 rules

Each is genuinely decidable from artifact data, and each has a subject present in the platform. These need an invariant authored; most can share a generic handler rather than getting one each.

| rules | subject | shape of the check |
|---|---|---|
| `STRUCTURE_EXPLICIT_PATHS`, `STRUCTURE_NO_ABSOLUTE_PATHS`, `STRUCTURE_NO_ESCAPE`, `STRUCTURE_LAYER_DECLARED`, `STRUCTURE_DETERMINISTIC_RESOLUTION`, `STRUCTURE_BOOTSTRAP_ELIGIBLE` | 20 STRUCTURE artifacts | path declarations: no absolute paths, no `..`, layer codes resolve |
| `AC_TYPE_REQUIRED`, `AC_ATTRIBUTES_TYPED`, `AC_IDENTITY_GOVERNED`, `AC_IDENTITY_ONLY` | 1 AC artifact | required fields, typed attributes, no execution keys |
| `VOCAB_UNKNOWN_SYMBOL_FORBIDDEN`, `VOCAB_UPPER_SNAKE_CASE` | 3 VOCAB artifacts | symbol resolution and naming form |
| `ASSERT_COMPILER_ONLY` | RB / CC / WF | no runtime artifact references an ASSERT |

The six STRUCTURE rules are largely subsumed by a closed `SCHEMA_STRUCTURE_V0` — which is Phase 3 work. Authoring a separate structural invariant now would duplicate it.

---

## Requires a ruling — 15 rules

### `CONSTITUTION_ENTITY_V0` — 14 rules over a kind with no instances

The platform contains **zero ENTITY artifacts**. Present artifact-code prefixes:

```
AC 1 · CC 3 · CONSTITUTION 30 · CS 3 · CT 14 · EV 1 · IN 1
INVARIANT 73 · RB 1 · STRUCTURE 20 · SURFACE 9 · TE 1 · TI 1 · VOCAB 3 · WF 1
```

The rules themselves are well-formed and mostly decidable — identity declared, attributes typed, relationships by FQDN, lifecycle enums. But authoring 11–14 invariants and their handlers for a class with no instances buys vacuous passes and standing maintenance.

Two honest dispositions:

- **Defer the constitution.** ENTITY is a planned kind not yet realized. A constitution in the compiled normative surface claiming compiler enforcement over a nonexistent class is itself a form of the defect being removed. Deferring it until the first ENTITY artifact exists keeps the surface truthful.
- **Author the invariants now.** They pass vacuously and enforce the moment entities appear. Correct, but pays the cost before the benefit and adds ~14 artifacts to the normative surface for no current effect.

Deferring is the more consistent choice with everything else here; authoring is defensible if ENTITY is imminent.

### `INVARIANT_FAIL_FAST` — the rule contradicts the doctrine

The rule states `violation_response MUST be FAIL_IMMEDIATELY; no warnings, no partial success`. But `rule_ownership.md` establishes `BUSINESS_VIOLATION` as the required response for `runtime_outcome` invariants, and one platform invariant already declares `WARN`. `SCHEMA_INVARIANT_V0` admits all three.

The rule predates the two-class model and is stale. It cannot be bound to `INVARIANT_SCHEMA_CONFORMANCE_V0` without asserting something the schema does not enforce — that would be a new instance of exactly the defect under repair. It needs amending to something like *"FAIL_IMMEDIATELY for compiler-staged invariants; BUSINESS_VIOLATION for runtime_outcome"*, which is a constitutional change rather than a binding.

---

## Position after this pass

| | count |
|---|---:|
| unenforced at Phase 2 close | 49 |
| resolved here | 21 |
| pending new enforcement | 13 |
| pending a ruling | 15 |
| **remaining** | **28** |

Reverse closure is clean: 0 orphan invariants, down from 24.