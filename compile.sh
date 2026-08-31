#!/usr/bin/env bash
#
# PGC compile runner — no PYTHONPATH / env fuss.
#
# Usage:
#   ./compile.sh STRUCTURE_BUILD_PLATFORM_CONFIG_V1
#   ./compile.sh STRUCTURE_BUILD_PLATFORM_CONFIG_V1 -v
#
# The STRUCTURE is REQUIRED. There is no default platform: a governance surface is whatever a
# build config declares, and defaulting one presumes *the* platform the way a defaulted profile
# presumes *the* profile. `compile_domain.sh` already requires its domain root; this matches it.
# Flags (anything starting with '-', e.g. -v/--verbose) are forwarded to the compiler in any position.
#
# Env overrides:
#   PGC_PLATFORM_ROOT   (default: sibling ../software_governance)
#   PGC_SNAPSHOT_ROOT   (default: <platform>/snapshot)
#   PYTHON              (default: python)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"            # protocol_compiler/ = the `compiler` package root
PGC_PLATFORM_ROOT="${PGC_PLATFORM_ROOT:-$(cd "$SCRIPT_DIR/../software_governance" && pwd)}"
PYTHON="${PYTHON:-python}"

# Separate the optional STRUCTURE positional from pass-through flags (e.g. -v), so a flag may
# appear in any position: `./compile.sh -v` and `./compile.sh STRUCTURE ... -v` both work.
STRUCTURE=""
FLAGS=()
for arg in "$@"; do
  case "$arg" in
    -*) FLAGS+=("$arg") ;;
    *)  if [[ -z "$STRUCTURE" ]]; then STRUCTURE="$arg"; else FLAGS+=("$arg"); fi ;;
  esac
done
if [[ -z "$STRUCTURE" ]]; then
  echo "usage: compile.sh <STRUCTURE_CODE> [flags]" >&2
  echo "  e.g. compile.sh STRUCTURE_BUILD_PLATFORM_CONFIG_V1" >&2
  echo "  No default: a platform is whatever a build config declares, and none is minimal by" >&2
  echo "  nature (6a §8). Name the structure you mean." >&2
  exit 2
fi

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PGC_PLATFORM_ROOT

echo "PGC compile"
echo "  compiler : $SCRIPT_DIR (package: compiler)"
echo "  platform : $PGC_PLATFORM_ROOT"
export PGC_SNAPSHOT_ROOT="${PGC_SNAPSHOT_ROOT:-$PGC_PLATFORM_ROOT/snapshot}"
echo "  snapshot : $PGC_SNAPSHOT_ROOT"
echo "  structure: $STRUCTURE"
echo

exec "$PYTHON" -m compiler.cli compile --structure "$STRUCTURE" ${FLAGS[@]+"${FLAGS[@]}"}
