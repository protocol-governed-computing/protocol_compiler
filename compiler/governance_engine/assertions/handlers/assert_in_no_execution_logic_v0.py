"""
ASSERT_IN_NO_EXECUTION_LOGIC_V0 Handler

Validates that IN (Intent) artifacts do not contain execution logic fields.
Intents are admission gates — they declare preconditions, not execution.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only
"""

_FORBIDDEN_EXECUTION_FIELDS = frozenset({
    "execute",
    "callable",
    "implementation",
    "logic",
    "transform",
    "code",
    "handler",
})


def _find_forbidden_fields(obj: dict, path: str = "") -> list[str]:
    """Recursively find forbidden execution fields in a dict."""
    found = []
    if not isinstance(obj, dict):
        return found
    for key, value in obj.items():
        current_path = f"{path}.{key}" if path else key
        if key in _FORBIDDEN_EXECUTION_FIELDS:
            found.append(current_path)
        if isinstance(value, dict):
            found.extend(_find_forbidden_fields(value, current_path))
    return found


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all IN artifacts do not contain execution logic fields.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    in_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "IN":
            continue

        in_code = artifact.get("artifact_code", "UNKNOWN")
        in_count += 1

        frontmatter = artifact.get("frontmatter", {})
        forbidden_paths = _find_forbidden_fields(frontmatter)

        for field_path in forbidden_paths:
            violations.append({
                "assert": "ASSERT_IN_NO_EXECUTION_LOGIC_V0",
                "artifact": in_code,
                "field": field_path,
                "violation": (
                    f"IN artifact contains forbidden execution field '{field_path}'; "
                    f"intents are admission gates and must not contain execution logic"
                ),
                "fix": (
                    f"Remove field '{field_path}' from IN artifact. "
                    f"Move execution logic to the appropriate CC or CT artifact."
                ),
            })

    return {
        "assert_count": in_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
