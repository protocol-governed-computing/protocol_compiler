"""
artifact_locator.py — Artifact discovery and code extraction (structure runtime)

This module provides runtime artifact discovery across the filesystem.
Governance layer uses this for vocabulary building and validation.

ARCHITECTURAL BOUNDARY:
- Structure: Implements artifact discovery (this file)
- Governance: Defines artifact schemas and validation rules

Pure functions for scanning protocol artifacts and extracting codes.
Moved from registry layer to establish clean separation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Set, List, Callable, Dict, Any


# Type alias for file reader
FileReader = Callable[[Path], str]


def load_json_strict(path: Path, read_file: FileReader) -> Dict[str, Any]:
    """
    Load JSON file with strict error handling.

    Args:
        path: Path to JSON file.
        read_file: File reader function.

    Returns:
        Parsed JSON as dict.

    Raises:
        ValueError: If JSON is malformed.
    """
    try:
        content = read_file(path)
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON: {path}\n{e}")


def iter_protocol_jsons(root: Path) -> List[Path]:
    """
    Iterate over protocol JSON files, excluding metadata directories.

    Args:
        root: Root directory to scan.

    Returns:
        List of JSON file paths.
    """
    if not root.exists():
        return []

    return [
        p for p in root.rglob("*.json")
        if "metadata" not in p.parts
    ]


def extract_codes(
    root: Path,
    read_file: FileReader,
    key: str,
    prefix: str,
) -> Set[str]:
    """
    Extract artifact codes from JSON files.

    Scans all JSON files in root directory and extracts codes matching
    the specified key and prefix.

    Args:
        root: Directory to scan.
        read_file: File reader function.
        key: JSON key containing the code.
        prefix: Required prefix for codes.

    Returns:
        Set of extracted codes.
    """
    codes: Set[str] = set()

    for path in iter_protocol_jsons(root):
        try:
            data = load_json_strict(path, read_file)
            value = data.get(key)
            if isinstance(value, str) and value.startswith(prefix):
                codes.add(value)
        except ValueError:
            # Skip malformed files
            continue

    return codes


def extract_wf_codes(
    workflows_dir: Path,
    read_file: FileReader,
) -> Set[str]:
    """
    Extract workflow codes, handling both wf_code and workflow_code keys.

    Args:
        workflows_dir: Workflows directory.
        read_file: File reader function.

    Returns:
        Set of workflow codes (WF_*).
    """
    codes: Set[str] = set()

    for path in iter_protocol_jsons(workflows_dir):
        try:
            data = load_json_strict(path, read_file)
            code = data.get("workflow_code") or data.get("wf_code")
            if isinstance(code, str) and code.startswith("WF_"):
                codes.add(code)
        except ValueError:
            continue

    return codes


def extract_in_codes(
    intents_dir: Path,
    read_file: FileReader,
) -> Set[str]:
    """
    Extract intent codes, handling both in_code and intent_code keys.

    Args:
        intents_dir: Intents directory.
        read_file: File reader function.

    Returns:
        Set of intent codes (IN_*).
    """
    codes: Set[str] = set()

    for path in iter_protocol_jsons(intents_dir):
        try:
            data = load_json_strict(path, read_file)
            code = data.get("intent_code") or data.get("in_code")
            if isinstance(code, str) and code.startswith("IN_"):
                codes.add(code)
        except ValueError:
            continue

    return codes


def extract_cc_codes(
    contracts_dir: Path,
    read_file: FileReader,
) -> Set[str]:
    """
    Extract capability contract codes.

    Args:
        contracts_dir: Capability contracts directory.
        read_file: File reader function.

    Returns:
        Set of capability contract codes (CC_*).
    """
    codes: Set[str] = set()

    for path in iter_protocol_jsons(contracts_dir):
        try:
            data = load_json_strict(path, read_file)
            code = data.get("cc_code")
            if isinstance(code, str) and code.startswith("CC_"):
                codes.add(code)
        except ValueError:
            continue

    return codes


def scan_artifacts_by_type(
    root: Path,
    read_file: FileReader,
    artifact_type_mapping: Dict[str, tuple[str, str]],
) -> Dict[str, Set[str]]:
    """
    Scan for multiple artifact types and extract their codes.

    Args:
        root: Root directory to scan.
        read_file: File reader function.
        artifact_type_mapping: Dict of {artifact_type: (key, prefix)}.
            Example: {"workflow": ("workflow_code", "WF_")}

    Returns:
        Dict mapping artifact_type to set of codes.
    """
    results: Dict[str, Set[str]] = {}

    for artifact_type, (key, prefix) in artifact_type_mapping.items():
        codes = extract_codes(root, read_file, key, prefix)
        if codes:
            results[artifact_type] = codes

    return results
