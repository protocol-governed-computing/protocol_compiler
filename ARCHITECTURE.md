# Architecture — `protocol_compiler`

This document describes what this repository is, what it owns, and what it must never do. It is
written to be read before any code, and assumes no prior familiarity with Protocol-Governed
Computing.

For the big picture — what PGC is and how the repositories compose — see
**https://github.com/protocol-governed-computing**.

---

## 1. What this repo is

This is the **compiler**. It reads governance declarations and business declarations, checks that
they are legal, and constructs from them a description of **every execution path the system is
allowed to take**.

It is a compiler in a specific and slightly unusual sense. A conventional compiler translates source
code into instructions a machine will run. This one does something different:

> It does not translate behaviour. **It constructs admissibility.**

The output is not a program. It is a map of what may happen — and, by omission, a statement of what
can never happen. Nothing outside that map is later prevented at run time. It is simply never built,
and therefore has nowhere to occur.

**What this repo is not.** It does not execute anything. It never runs an implementation to find out
what it does. It has no opinion about whether business logic is *correct* — only about whether it is
*permitted*.

## 2. Where it sits

```
   software_governance ─┐
                        │
   business domains ────┼──▶  protocol_compiler   ← YOU ARE HERE
                        │            │
   conformance workloads┘            │  produces per-domain projections
                                     ▼
                             snapshot_assembler ──▶ sealed snapshot
                                     │
                                     ▼
                             protocol_runtime ──▶ execution + evidence
```

Everything upstream is declarations written by people. Everything downstream consumes what this
repository built. **The compiler is the only component that decides what is admissible** — the
runtime cannot add a path, and no one can add one later by writing clever code.

## 3. The central idea: construction, not prevention

Most systems treat security and correctness as *filtering*: everything is possible, and something
must stop the bad cases. This compiler inverts that.

```
   CONVENTIONAL                          PROTOCOL-GOVERNED

   all possible behaviour                declarations
        │                                     │
        │  guards, policies,                  │  compiler constructs
        │  reviews try to                     ▼
        │  block the bad                 admissible paths
        ▼                                     │
   what actually runs                         │  runtime traverses
   (hopefully a subset)                       ▼
                                         what actually runs
                                         (exactly the subset)
```

If a path is not in what the compiler built, it is not *blocked* — it is **absent**. There is no code
path to reach it, no flag that could enable it, and no implementation trick that reintroduces it.
This is why the compiler is the seat of enforcement rather than the runtime.

## 4. What it owns, and what it must never do

**It owns:**

- reading declarations and resolving every name to exactly one thing;
- checking every declaration against the governance rules that apply to it;
- building the execution graph — the paths a workflow may take, and the outcomes that route between
  them;
- producing the **projections** downstream components read;
- producing **evidence** that records why each artifact was admitted.

**It must never:**

- **execute an implementation.** Admissibility is decided without running anyone's code. This is what
  makes the decision independent of what the code happens to do today.
- **infer what a declaration meant.** If something is not declared, compilation fails. There is no
  default, no fallback, and no best guess — a guess would make the compiler a second author of
  behaviour that nobody governed.
- **know a business domain.** The compiler has no built-in knowledge of any domain. A domain
  describes itself, including where its own source lives.

## 5. How a compile proceeds

Nine stages, each with one job. The sequence matters: a stage may only rely on what earlier stages
established.

```
   S1  EXTRACT              read declarations from source
        ↓
   S2  CANONICALIZE         one normal form, so two spellings cannot mean two things
        ↓
   S3  SEMANTIC ADDRESSING  every name resolved to exactly one artifact
        ↓
   S4  GOVERN               ◀── the gate. every rule checked. illegal graphs stop here
        ↓
   S5  CONSTRUCT            build the execution structure on the resolved graph
        ↓
   S6  PROJECT              derive the views downstream components read
        ↓
   S7  MATERIALIZE          write them out
        ↓
   S8  VERIFY               check what was written matches what was built
        ↓
   S9  ATTEST               sign the result as verified
```

**S4 is the gate.** Everything before it establishes facts; everything after it assumes legality.
A declaration that violates a rule stops here, and stops the whole compile — there is no partial
output, because a partially admissible system is not a meaningful thing.

**S8 exists because writing is not the same as building.** Verifying the output against the model
catches the case where construction was right and materialization was wrong.

## 6. What it produces

The compiler builds one semantic model and derives several **projections** from it. They are views
of the same verified thing, not separate compilations.

| projection | what it is for |
|---|---|
| canonical | the artifacts themselves, in normal form — what the assembler seals |
| execution graph | every path a workflow may take, before anything runs |
| tokenized | the same graph addressed by integer rather than by name — what the runtime actually walks |
| dispatch | what the runtime consults to route between steps |
| vocabulary | every named concept, indexed — so two things cannot quietly share a name |
| evidence | why each artifact was admitted |
| visualization | rendered diagrams of the compiled graph |

That last one matters more than it sounds. **The compiled execution graph can be looked at.** A
reviewer can see every path, every outcome and every terminal state of a workflow *before it has ever
run* — not a simulation of it, but the literal structure the runtime will walk. Rendered examples are
sealed into every snapshot under `behavior_logic/<domain>/<workflow>/`.

## 7. Layout

```
compile.sh              compile the governance surface
compile_domain.sh       compile one domain against it

compiler/
    stages/             the nine stages, one file each
    governance_engine/  the rules, and the handlers that check them
    governance/         graph-native governance predicates
    graph/              the semantic model everything is derived from
    projections/        the views listed above
    visualization/      graph rendering
    diagnostics/        how a failure is reported
    atoms/  structure_loader.py
```

## 8. Rules this repo enforces

1. **No implementation is executed during compilation.** Admissibility never depends on running code.
2. **Every reference resolves, or the compile fails.** A workflow naming a contract that does not
   exist is a compile error, not a run-time surprise.
3. **No partial output.** A failed compile writes nothing; there is no half-admissible system.
4. **The compiler infers nothing.** Undeclared means absent, and absent means the compile stops.
5. **Domains are self-describing.** Adding a domain requires no edit to this repository.

## 9. How to know it works

```bash
./compile.sh                       # the governance surface compiles
./compile_domain.sh <domain-root>  # one domain compiles against it
```

A successful compile reports the stages it ran, the artifacts it materialized, and that the result
was verified and attested. A failure names the rule that refused, and the artifact it refused —
the diagnostic is the point, not a side effect.

## 10. Where the architecture is explained

This document describes *this repository*. The architecture it realizes is developed in the papers
indexed at **https://github.com/protocol-governed-computing**:

- **Compiler Conceptual Model** — the closest companion to this repository: what the compiler
  produces, why the runtime is simple, and the admissibility boundary contract.
- **A Conceptual Model** — the snapshot, admissibility, and the constitutional invariants this
  compiler enforces.
- **Realizing the Normative Platform and Its Governed Transformation** — where compilation sits in
  the three-function model, between transformation and execution.
