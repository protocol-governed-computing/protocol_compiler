"""
ASSERT_INSPECTION_CAPABILITY_READ_ONLY_V0 Handler

Validates that a capability declaring `category: inspection` observes and never mutates.

Observation of the assembled system is a governed capability rather than an ad hoc read. That rule
is only worth anything if an inspection capability cannot also change what it observes: a workflow
executing from a sealed snapshot must not be able to alter that snapshot, and evidence gathered by
a capability that could rewrite its subject is not evidence.

For every CS with `core.category: inspection`:
- every declared operation must be idempotent
- no operation may name a mutating verb (WRITE, DELETE, APPEND, UPDATE, PUT, SET, …)
- `core.semantics.durability` must be `read_only`
- `core.configuration_schema` must declare the subject being observed (`snapshot_root`)

The last one matters as much as the others: a capability that discovers its subject rather than
having it bound could observe something other than the composition it was asked about.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only.
"""

# Operation names that change state. Matched as whole words against the operation key so that a
# read named LIST_UPDATES is not flagged while UPDATE is.
_MUTATING_VERBS = frozenset({
    "WRITE", "DELETE", "DELETE_MANY", "APPEND", "UPDATE", "UPDATE_WHERE",
    "PUT", "SET", "CREATE", "REMOVE", "DEREGISTER", "REGISTER", "DRAIN", "CLEAR",
})


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate that inspection capabilities are read-only.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused — reads frontmatter directly)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED" | "FAILED"
        }
    """
    violations = []
    inspection_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CS":
            continue

        core = artifact.get("frontmatter", {}).get("core", {})
        if core.get("category") != "inspection":
            continue

        inspection_count += 1
        fqdn = artifact.get("fqdn_id", artifact.get("artifact_code", "UNKNOWN"))

        operations = core.get("operations") or {}
        if isinstance(operations, dict):
            for op_name, op_spec in operations.items():
                if str(op_name).upper() in _MUTATING_VERBS:
                    violations.append({
                        "assert": "ASSERT_INSPECTION_CAPABILITY_READ_ONLY_V0",
                        "artifact": fqdn,
                        "operation": op_name,
                        "violation": (
                            f"Inspection capability declares mutating operation {op_name!r}. "
                            f"A capability that can alter what it observes cannot produce evidence "
                            f"about it."
                        ),
                        "fix": f"Remove {op_name!r}, or declare this capability under a category other than 'inspection'.",
                    })
                if isinstance(op_spec, dict) and op_spec.get("idempotent") is not True:
                    violations.append({
                        "assert": "ASSERT_INSPECTION_CAPABILITY_READ_ONLY_V0",
                        "artifact": fqdn,
                        "operation": op_name,
                        "violation": (
                            f"Inspection operation {op_name!r} is not declared idempotent. "
                            f"Observing the same snapshot twice must give the same answer."
                        ),
                        "fix": f"Declare 'idempotent: true' on operation {op_name!r}.",
                    })

        durability = (core.get("semantics") or {}).get("durability")
        if durability != "read_only":
            violations.append({
                "assert": "ASSERT_INSPECTION_CAPABILITY_READ_ONLY_V0",
                "artifact": fqdn,
                "violation": (
                    f"Inspection capability declares durability {durability!r}; expected 'read_only'."
                ),
                "fix": "Set core.semantics.durability to 'read_only'.",
            })

        config_schema = core.get("configuration_schema") or {}
        if "snapshot_root" not in config_schema:
            violations.append({
                "assert": "ASSERT_INSPECTION_CAPABILITY_READ_ONLY_V0",
                "artifact": fqdn,
                "violation": (
                    "Inspection capability does not declare 'snapshot_root' in its configuration "
                    "schema. The subject being observed must be bound, never discovered."
                ),
                "fix": "Declare a required 'snapshot_root' in core.configuration_schema.",
            })

    return {
        "assert_count": inspection_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
