"""
ASSERT_NO_SMART_EXECUTION_V0 Handler

Validates execution layer code does not perform type-based conversions.
"""

import re
from pathlib import Path
from typing import Any

from compiler.governance_engine.structure.resolution.layer_resolver import LayerResolver
from compiler.governance_engine.structure.resolution.path_registry import bootstrap, paths


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Scan execution layer for smart executor violations.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains layer_mapping

    Returns:
        {
            "assert_count": int,
            "violations": list[dict]
        }
    """
    violations = []

    # Scan execution layer files
    # PROTOCOL: Use LayerResolver for layer path discovery
    bootstrap()
    resolver = LayerResolver()
    # PGC: the EXECUTION (runtime) layer is not part of the normative platform snapshot.
    # When it is absent/unmapped, there is no execution code to scan → N/A (PASSED).
    try:
        exec_layer_path = resolver.resolve_layer_root("EXECUTION")
    except ValueError:
        exec_layer_path = None

    if exec_layer_path is None or not exec_layer_path.exists():
        return {
            "assert_count": 0,
            "violations": [],
            "status": "PASSED"
        }

    # Key files to scan
    target_files = [
        exec_layer_path / "machine" / "transforms" / "atom_registry.py",
        exec_layer_path / "machine" / "workflow_runner.py",
    ]

    patterns = [
        # Type metadata loading
        (r"load_contract\(", "Type metadata loading detected"),
        (r"_load_atom_output_types\(", "Type metadata loading detected"),
        (r"_load_atom_input_types\(", "Type metadata loading detected"),

        # Type-based conditionals
        (r'if\s+.*type.*==\s*["\']hex_string["\']', "Type-based conditional detected"),
        (r'if\s+.*\[.*\]\s*==\s*["\']hex_string["\']', "Type-based conditional detected"),

        # Type conversion calls
        (r'\.hex\(\)', "Type conversion (.hex()) detected"),
        (r'bytes\.fromhex\(', "Type conversion (bytes.fromhex) detected"),

        # Type caching
        (r'_OUTPUT_TYPES_CACHE', "Type caching detected"),
        (r'_INPUT_TYPES_CACHE', "Type caching detected"),
    ]

    for file_path in target_files:
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        for pattern, message in patterns:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    violations.append({
                        "fqdn": f"execution.layers::{file_path.name}",
                        "rule": "fb.execution::INVARIANT_NO_SMART_EXECUTION_V0",
                        "message": f"{file_path.name}:{line_num} - {message}: {line.strip()}",
                        "fix": "Remove type-based conversion logic from execution layer - execution must be type-agnostic"
                    })

    if violations:
        return {
            "assert_count": len(target_files),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(target_files),
        "violations": [],
        "status": "PASSED"
    }
