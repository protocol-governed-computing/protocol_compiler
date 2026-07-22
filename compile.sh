#!/usr/bin/env bash
#
# PGC compile runner — no PYTHONPATH / env fuss.
#
# Usage:
#   ./compile.sh                                  # default structure (platform V1)
#   ./compile.sh STRUCTURE_BUILD_PLATFORM_CONFIG_V1 -v
#
# Env overrides:
#   PGC_PLATFORM_ROOT   (default: sibling ../platform)
#   PGC_SNAPSHOT_ROOT   (default: <platform>/snapshot)
#   PYTHON              (default: python)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"            # protocol_compiler/ = the `compiler` package root
PGC_PLATFORM_ROOT="${PGC_PLATFORM_ROOT:-$(cd "$SCRIPT_DIR/../platform" && pwd)}"
STRUCTURE="${1:-STRUCTURE_BUILD_PLATFORM_CONFIG_V1}"
PYTHON="${PYTHON:-python}"

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PGC_PLATFORM_ROOT

echo "PGC compile"
echo "  compiler : $SCRIPT_DIR (package: compiler)"
echo "  platform : $PGC_PLATFORM_ROOT"
echo "  snapshot : ${PGC_SNAPSHOT_ROOT:-$PGC_PLATFORM_ROOT/snapshot}"
echo "  structure: $STRUCTURE"
echo

exec "$PYTHON" -m compiler.cli compile --structure "$STRUCTURE" "${@:2}"
