"""
ASSERT_RB_NO_LOGIC_V0 Handler

Validates that RB artifacts contain no execution logic in binding config values.
Template variable substitution ({{var}}) is permitted.
Conditional expressions and callable references are forbidden.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

import re

# Patterns that indicate forbidden logic in config string values
_FORBIDDEN_PATTERNS = [
    (re.compile(r"\?\s*['\"/]"), "ternary conditional expression"),
    (re.compile(r"\bif\b.*\belse\b"), "inline if/else expression"),
    (re.compile(r"\(\s*\)"), "function call syntax"),
    (re.compile(r"->\s*\w"), "arrow callable reference"),
    (re.compile(r"=>\s*\w"), "fat-arrow callable reference"),
]


def _check_value(value, path: str, rb_code: str, violations: list) -> None:
    """Recursively inspect config values for forbidden logic patterns."""
    if isinstance(value, str):
        for pattern, description in _FORBIDDEN_PATTERNS:
            if pattern.search(value):
                violations.append({
                    "assert": "ASSERT_RB_NO_LOGIC_V0",
                    "artifact": rb_code,
                    "field": path,
                    "value": value,
                    "violation": (
                        f"RB binding config contains {description} — "
                        "logic is not permitted in runtime bindings"
                    ),
                    "fix": "Use a static value or {{var}} template substitution only",
                })
    elif isinstance(value, dict):
        for k, v in value.items():
            _check_value(v, f"{path}.{k}", rb_code, violations)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_value(item, f"{path}[{i}]", rb_code, violations)


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all RB artifacts for absence of execution logic.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused; all data from artifacts)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    rb_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "RB":
            continue

        rb_code = artifact.get("artifact_code", "UNKNOWN")
        rb_count += 1

        bindings = artifact.get("frontmatter", {}).get("core", {}).get("bindings", {})
        for binding_key, binding_def in bindings.items():
            config = binding_def.get("config", {})
            _check_value(config, f"bindings.{binding_key}.config", rb_code, violations)

    return {
        "assert_count": rb_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
