#!/usr/bin/env bash
#
# PGC domain compile runner — compile a domain AGAINST the compiled platform surface.
#
# The platform must be compiled first (./compile.sh) — a domain resolves its governance/capability
# references against the platform's compiled vocabulary (import_surface). A domain is self-describing:
# its build manifest declares its own layer + namespace rule, so NO compiler edit is needed.
#
# Usage:
#   ./compile_domain.sh <domain_root> [STRUCTURE_CODE]
#     <domain_root> — dir containing registry/structures/STRUCTURE_BUILD_<X>_CONFIG_V0.md
#     STRUCTURE_CODE — optional; auto-discovered from the domain's registry/structures if omitted
#
# Example:
#   ./compile_domain.sh ../platform/reference_workloads/collatz
#
# Env overrides: PGC_PLATFORM_ROOT (default sibling ../platform), PYTHON (default python).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # protocol_compiler/ = the `compiler` package root
UMBRELLA="$(cd "$SCRIPT_DIR/.." && pwd)"                       # protocol-governed-computing/
PYTHON="${PYTHON:-python}"
PGC_PLATFORM_ROOT="${PGC_PLATFORM_ROOT:-$UMBRELLA/platform}"

DOMAIN_ROOT="${1:?usage: compile_domain.sh <domain_root> [STRUCTURE_CODE]}"
DOMAIN_ROOT="$(cd "$DOMAIN_ROOT" && pwd)"
STRUCTURE="${2:-}"

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

exec "$PYTHON" -m compiler.cli compile --structure "$STRUCTURE"