#!/usr/bin/env bash
#
# PGC domain compile runner — compile a domain AGAINST the compiled platform surface.
#
# The platform must be compiled first (./compile.sh) — a domain resolves its governance/capability
# references against the platform's compiled vocabulary (import_surface). A domain is self-describing:
# its build manifest declares its own layer + namespace rule, so NO compiler edit is needed.
#
# Usage:
#   ./compile_domain.sh <domain_root> [STRUCTURE_CODE] [flags]
#     Compiles the domain, then runs its transform conformance (runtime conformance); fails if either
#     fails.
#     <domain_root> — dir containing registry/structures/STRUCTURE_BUILD_<X>_CONFIG_V0.md
#     STRUCTURE_CODE — optional; auto-discovered from the domain's registry/structures if omitted
#     flags — anything starting with '-' (e.g. -v/--verbose) is forwarded to the compiler
#
# Example:
#   ./compile_domain.sh ../conformance_workloads/workloads/collatz
#   ./compile_domain.sh ../conformance_workloads/workloads/collatz -v
#
# Env overrides: PGC_PLATFORM_ROOT (default sibling ../software_governance), PYTHON (default python).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # protocol_compiler/ = the `compiler` package root
UMBRELLA="$(cd "$SCRIPT_DIR/.." && pwd)"                       # protocol-governed-computing/
PYTHON="${PYTHON:-python}"
PGC_PLATFORM_ROOT="${PGC_PLATFORM_ROOT:-$UMBRELLA/software_governance}"

DOMAIN_ROOT="${1:?usage: compile_domain.sh <domain_root> [STRUCTURE_CODE] [flags]}"
DOMAIN_ROOT="$(cd "$DOMAIN_ROOT" && pwd)"
shift

# Separate the optional STRUCTURE positional from pass-through flags (e.g. -v).
STRUCTURE=""
FLAGS=()
for arg in "$@"; do
  case "$arg" in
    -*) FLAGS+=("$arg") ;;
    *)  if [[ -z "$STRUCTURE" ]]; then STRUCTURE="$arg"; else FLAGS+=("$arg"); fi ;;
  esac
done

if [[ -z "$STRUCTURE" ]]; then
  manifest="$(ls "$DOMAIN_ROOT"/registry/structures/STRUCTURE_BUILD_*_CONFIG_V*.md 2>/dev/null | head -1 || true)"
  [[ -n "$manifest" ]] || { echo "No STRUCTURE_BUILD_*_CONFIG manifest under $DOMAIN_ROOT/registry/structures" >&2; exit 1; }
  STRUCTURE="$(basename "$manifest" .md)"
fi

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PGC_PLATFORM_ROOT
export PGC_DOMAIN_ROOTS="$DOMAIN_ROOT"
export PGC_SNAPSHOT_ROOT="$DOMAIN_ROOT/snapshot"

echo "PGC compile-domain"
echo "  domain   : $DOMAIN_ROOT"
echo "  structure: $STRUCTURE"
echo "  platform : $PGC_PLATFORM_ROOT (import surface)"
echo "  out      : $PGC_SNAPSHOT_ROOT"
echo

"$PYTHON" -m compiler.cli compile --structure "$STRUCTURE" ${FLAGS[@]+"${FLAGS[@]}"}

# Conformance, after a successful compile and before the domain can be assembled
# (conformance::CONSTITUTION_TEST_DATA_V2). A transform's implementation belongs to this domain, so its
# vectors run in this domain's build — on every build, because the composition seals a declaration and
# not the code behind it. The compiler never imports the runtime; this script composes the two tools.
# A refused transform fails the build; an unproven one is reported by name.
echo
exec "$UMBRELLA/protocol_runtime/run.sh" conformance "$DOMAIN_ROOT"