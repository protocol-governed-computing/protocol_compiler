# protocol_compiler

**Topology-native governance compiler for Protocol-Governed Computing.**

The compiler translates protocol declarations into sealed, verified projections. It does not execute
behavior, contain runtime logic, or interpret intent. Everything a governed system will do is decided
here, before anything runs.

## Where it fits

```
software_governance    the normative surface every composition rests on
conformance_workloads  workloads that prove conformance
business_domains       domains built on the surface

protocol_compiler      source      → compiled projections      (this repo)
snapshot_assembler     projections → assembled snapshot
protocol_runtime       snapshot    → execution
snapshot_inspector     snapshot    → inspection
```

`transformation` sits upstream of all of it, turning a problem statement into the artifacts this
compiler consumes. `protocol_transport` governs the boundary at either end of execution.

The compiler is where **admissibility** is decided. A protocol artifact that violates a constitutional
boundary fails compilation, so the runtime is never in a position to execute ungoverned behavior — it
receives sealed, self-consistent instructions or the build does not complete.

## What it is, and is not

**It is** a nine-stage compilation pipeline, a governance enforcement gate, a projection producer, and
a conformance runner for capability-transform implementations.

**It is not** a runtime engine, a workflow interpreter, or a code generator for application logic.
Schema *correctness* is a governance concern declared in `software_governance`; the compiler enforces
what governance declares rather than deciding it.

## Inputs and outputs

Protocol source is Markdown with YAML frontmatter, discriminated by artifact kind:

```
AC_ actors          CC_ capability contracts    CS_ capability side effects
CT_ capability transforms                       EV_ events
IN_ intents         RB_ runtime bindings        WF_ workflows
TI_ transport ingress                           TE_ transport egress
```

Compilation writes per-domain projections, each shaped for one consumer: `canonical` (the complete
governed artifact graph, human-readable), `tokenized` (the integer-addressed execution substrate),
`vocabulary` (FQDN ↔ address index), `evidence` (the semantic causality graph), `dispatch` (per-workflow
routing and pipeline steps), `handlers` (CT-IR, side-effect handler refs, binding policy), plus the
artifact index. `snapshot_assembler` composes these into the snapshot the runtime consumes.

## Building

The platform surface compiles first — a domain resolves its governance and capability references
against the platform's compiled vocabulary:

```bash
./compile.sh STRUCTURE_BUILD_PLATFORM_CONFIG_V1   # the platform surface — named, no default
./compile_domain.sh <domain_root>             # one domain, against the compiled platform
```

Both wrap the same CLI, which is also installed as a console script:

```bash
protocol_compiler compile --structure STRUCTURE_BUILD_PLATFORM_CONFIG_V1
protocol_compiler compile --all-structures
protocol_compiler inspect --structure <CODE> --artifact <fqdn>     # identity + causality chain
protocol_compiler inspect --structure <CODE> --upstream <fqdn>     # walk causality upstream
```

A domain is **self-describing**: its build manifest declares its own layer and namespace rule, so
adding one requires no compiler edit. `PGC_PLATFORM_ROOT` and `PGC_SNAPSHOT_ROOT` override the
default sibling paths.

## How compilation works

Nine stages, run in order. Each transforms an immutable `State` — no stage mutates a prior stage's
output, and `S7` performs the only side effect in the pipeline.

| Stage | Name | What it does |
|-------|------|--------------|
| S1 | Extract | Parses frontmatter from source artifacts; builds raw graph nodes |
| S2 | Canonicalize | Resolves local keys to FQDNs; builds reference and topology edges |
| S3 | Semantic Addressing | Assigns deterministic integer addresses to every node and edge |
| S4 | Govern | Enforces constitutional invariants; validates governance boundaries |
| S5 | Construct | Assembles the full graph — CT-IR, CS-IR, contract projection, workflow enrichment |
| S6 | Project | Derives the deterministic execution projections |
| S7 | Materialize | Writes projections to disk — the pipeline's only side effect |
| S8 | Verify | Roundtrip validation, determinism check, hash and conformance verification |
| S9 | Attest | Computes the trust attestation binding the verified projections |

## What makes it different

**Governance is a compilation stage, not a linting pass.** `S4` is a gate: an artifact that violates a
constitutional boundary fails the build.

**Addressing is topology-native.** Every artifact receives a deterministic integer address derived
from graph position and content, so the runtime operates on integers and resolves no strings at
execution time.

**Closure is proven before anything is written.** Routing, bindings, input paths and output mappings
are all resolved and validated ahead of materialization.

**Conformance runs at compile time.** Capability-transform implementations are tested against their
declared `TEST_DATA` during every build; one that fails blocks snapshot validation.

## Purity rules

The semantic graph is the sole authority and every projection is a derived materialization of it.
Graph dataclasses are frozen; stages return new graphs rather than mutating in place. Assertion
handlers are statically enumerated in a closed registry and resolved by static lookup — no dynamic
import, no filesystem discovery, and a missing handler fails the compile rather than falling back.

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
