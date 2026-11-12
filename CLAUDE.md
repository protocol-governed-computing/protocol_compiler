## Response Style

Keep responses under ~400 output tokens. Prefer terse bullet summaries over prose narration. When a full document is needed, Write it to a file instead of printing it in chat.

## Document Authoring Rules

- Never include internal review notes, meta-scaffolding, work-order framing, cross-reference stubs, or 'Status:' metadata in deliverable docs or figures.
- Do not add dates to papers or appendices.
- An 'outline' means a clean reader-facing outline of the paper, not an execution plan.

# PGC Protocol Compiler — Architectural Rules

## What This Is

The **PGC protocol compiler** — a topology-native governance compiler that constructs an
immutable semantic graph from the normative protocol surface, then projects that graph
into multiple deterministic execution representations.

- **Org:** `protocol-governed-computing` (the only hyphenated name).
- **Repo / top-level:** `protocol_compiler` (underscore).
- **Import package:** `compiler` — no `protocol_`/`transformation_` prefix inside; the org
  provides the namespace. Distribution `pgc-compiler`, `import compiler`.
- **Version:** declared in `pyproject.toml`. It moves on its own, as the README's Versioning
  section describes.
- **Sibling:** `transformation_compilers` holds the import package `transformation`. It holds two
  compilers, design and construction.

## Clean break from RI-0 (MANDATORY)

Clean-break rule: **no PGC-org repo may take a code
dependency on a `pgs_*` package.** This compiler:

- **MUST NOT import `pgs_governance`, `pgs_capabilities`, `pgs_runtime`, or any `pgs_*`.**
- **Reads the normative surface (registry + structural schemas) from `software_governance`** —
  resolved from an explicit platform root (`PGC_PLATFORM_ROOT` / `--platform`), never from a
  `pgs_*` package `__file__`, never from `cwd`.
- **Vendors the governance engine** (assertion handlers + `HANDLER_REGISTRY`, structure
  loaders/resolvers, `artifact_kinds`, conformance, constitution validator) into this
  package. Boundary: **`software_governance` = what PGC is; this compiler = how PGC is compiled.**

No module under `compiler/` imports any `pgs_*` package. Keep it that way. The compiler began as
a fork of RI-0's `pgs_compiler`, and it does not track it.

## Architecture

### Compilation stages (pure `State → State`)

```
S1 EXTRACT             Artifacts → raw graph nodes (no edges)
S2 CANONICALIZE        Identity resolution, FQDN normalization, reference edges
S3 SEMANTIC_ADDRESSING Deterministic address allocation (identities → integer tokens)
S4 GOVERN              Graph legality verification (schema conformance + assert handlers)
S5 CONSTRUCT           Full graph assembly (CT-IR, CS-IR, CC projection, WF enrichment)
S6 PROJECT             Graph → deterministic execution projections
S7 MATERIALIZE         Projections → serialized files on disk (the only side effect)
S8 VERIFY              Roundtrip validation, determinism check, hash verification
S9 ATTEST              Trust attestation for verified projections (SHA256 binding)
```

### Module layout (package `compiler`, flattened — no `compiler.compiler`)

```
compiler/                 # package root = repo root (package-dir "compiler" = ".")
  atoms/                  # pure primitives (FQDN, errors, snapshot gate, …)
  graph/                  # semantic graph data model (state, nodes, edges)
  stages/                 # s1_extract … s9 (+ s10_pps_projection)
  projections/            # typed projection representations (canonical, tokenized, vocab)
  governance/             # graph-native governance predicates
  visualization/          # WF graph rendering
  cli.py                  # Click CLI entry point
  structure_loader.py     # STRUCTURE bootstrap search roots (→ PGC platform, see migration)
```

## Compiler purity (MANDATORY)

- **Pure — nine stages, no side effects except S7 MATERIALIZE (file writes).**
- MUST NOT execute CT, CS, or workflows; MUST NOT import any execution/runtime layer.
- Output is data only: canonical JSON, tokenized, and vocabulary projections + evidence
  and artifact index. No runtime logic, no execution hooks in the pipeline.

## Graph immutability & stage purity (MANDATORY)

- Graph dataclasses are `frozen=True`; collections are `MappingProxyType`/`tuple`.
- Stages return a NEW graph via builder methods — never mutate in place; no shared mutable
  state between stages.
- Semantic addressing is compile-time, deterministic, immutable per snapshot version —
  never runtime-generated.

## ASSERT handler resolution (MANDATORY)

- All handlers statically imported in the vendored `HANDLER_REGISTRY`, explicitly
  enumerated, resolved by static lookup only.
- No `importlib.import_module`, no dynamic import, no module discovery, no filesystem scan.
- Missing handler → immediate compile failure, no fallback. (`INVARIANT_HANDLER_REGISTRY_CLOSED`.)

## Import rules (MANDATORY)

```python
# CORRECT — absolute, fully-qualified from the `compiler` root
from compiler.atoms.errors import CompilerError
from compiler.graph.state import State
from compiler.stages import s1_extract

# FORBIDDEN
from .atoms import X                        # relative import
from atoms import X                         # short-name import
from pgs_compiler.compiler.atoms import X   # old RI-0 package name
from pgs_governance... import X             # any pgs_* dependency (clean-break violation)
```

- All imports absolute and fully-qualified from `compiler`. No relative imports ever.
- No imports from any `pgs_*` package.

## Structure, identity, data & error rules

- Resolution via STRUCTURE artifacts only. No `cwd`, no relative/parent traversal, no
  implicit search roots — all paths declared (platform root explicit).
- All references use FQDN, resolved at compile time. No short names, no partial ids.
- Inputs/outputs match declared contract exactly — no extra/missing fields, no coercion,
  no implicit defaults.
- Fail fast on ambiguity, missing data, contract violation. Never silent success, warning
  continuation, retry, or fallback.

## Forbidden patterns

`sys.path` manipulation · dynamic imports / reflection module loading · `try/except` for
control flow · fallback logic · environment-driven branching · hidden defaults · magic
constants · filesystem-based handler discovery · mutable shared state between stages ·
in-place graph mutation · runtime-generated token addresses · **imports from any `pgs_*`
package**.

## Workflow rules (MANDATORY)

**Diagnose before fix:** state root cause → list files to change and why → identify layer
boundaries crossed → **wait for approval.** Multi-file changes: present the full file list
first, then execute one coherent pass — no scattered edits.

## Environment rules

- Build against the workspace venv (`protocol-governed-computing/.venv`), never the RI-0
  venv. This repo is editable-installed there; `import compiler` and the `protocol_compiler`
  console script resolve without `PYTHONPATH` manipulation.
- Verify isolation — a reachable `pgs_*` package is a clean-break violation even when nothing
  imports it:

  ```bash
  python -c "import sys, importlib.util as u
  print(sys.prefix)
  print('compiler:', bool(u.find_spec('compiler')))
  print('pgs_ reachable:', bool(u.find_spec('pgs_compiler')))"
  ```
- Dependencies: `click`, `pyyaml`, `jsonschema`. Do not add more without approval.

## One-line summary

PGC protocol compiler (package `compiler`): the semantic graph is the sole authority;
all projections are derived deterministic materializations; absolute imports, strict
purity, zero execution, zero inference, **zero `pgs_*` dependency** — protocol drives
everything, code only obeys.