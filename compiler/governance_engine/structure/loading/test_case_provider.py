"""
test_case_loader.py — Test case file loading (structure runtime)

This module provides runtime test case file loading.
Governance layer uses this for conformance testing and trace validation.

ARCHITECTURAL BOUNDARY:
- Structure: Implements test case file loading (this file)
- Governance: Defines test validation logic and conformance rules

Moved from registry/conformance/oracle/trace_oracle.py to establish clean separation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, NamedTuple


class TestCaseLoadError(RuntimeError):
    """Raised when test case file loading fails."""
    pass


class TestCase(NamedTuple):
    """
    Represents a single test case from a *.test.json file.

    A test case contains:
    - title: Human-readable test description
    - target: Target artifact to test (e.g., workflow code, intent code)
    - payload: Input data for the test
    - expected_trace: Expected execution trace events
    """
    title: str
    target: str
    payload: Dict[str, Any]
    expected_trace: List[Dict[str, Any]]


def load_test_cases(path: Path) -> List[TestCase]:
    """
    Load test cases from a *.test.json file.

    Test case file format (JSON):
    [
      {
        "title": "Test description",
        "target": "WF_EXAMPLE_V0",
        "payload": {"input": "data"},
        "trace": [{"event": "data"}]
      },
      ...
    ]

    Args:
        path: Path to *.test.json file.

    Returns:
        List of TestCase objects.

    Raises:
        TestCaseLoadError: If file not found, malformed, or invalid structure.
    """
    if not path.is_file():
        raise TestCaseLoadError(f"Test case file not found: {path}")

    try:
        data = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise TestCaseLoadError(f"Invalid JSON in test file: {path}\n{e}") from e

    if not isinstance(data, list):
        raise TestCaseLoadError("Test file must contain a JSON list of test cases.")

    test_cases: List[TestCase] = []
    for i, case_data in enumerate(data, 1):
        if not isinstance(case_data, dict):
            raise TestCaseLoadError(f"Test case #{i} must be a JSON object.")

        # Validate required keys
        required_keys = {"title", "target", "payload", "trace"}
        missing_keys = required_keys - set(case_data.keys())
        if missing_keys:
            raise TestCaseLoadError(f"Test case #{i} is missing keys: {missing_keys}")

        # Validate types
        if not isinstance(case_data["title"], str):
            raise TestCaseLoadError(f"Test case #{i} 'title' must be a string.")
        if not isinstance(case_data["target"], str):
            raise TestCaseLoadError(f"Test case #{i} 'target' must be a string.")
        if not isinstance(case_data["payload"], dict):
            raise TestCaseLoadError(f"Test case #{i} 'payload' must be a dict.")
        if not isinstance(case_data["trace"], list):
            raise TestCaseLoadError(f"Test case #{i} 'trace' must be a list.")

        test_cases.append(
            TestCase(
                title=case_data["title"],
                target=case_data["target"],
                payload=case_data["payload"],
                expected_trace=case_data["trace"],
            )
        )

    return test_cases


def load_test_cases_safe(path: Path) -> List[TestCase] | None:
    """
    Load test cases, returning None on failure instead of raising.

    Useful for optional test case loading where missing files are acceptable.

    Args:
        path: Path to *.test.json file.

    Returns:
        List of TestCase objects, or None if loading failed.
    """
    try:
        return load_test_cases(path)
    except TestCaseLoadError:
        return None
