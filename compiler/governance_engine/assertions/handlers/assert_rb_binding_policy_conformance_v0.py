"""
ASSERT_RB_BINDING_POLICY_CONFORMANCE_V0 Handler

Validates that RB bindings for file-path CS types declare a non-empty `policy.path`.

File-path CS types are those whose runtime implementations call `policy['path']`
directly to resolve a storage file (registry JSON). Declaring `policy: {}` for
these types compiles cleanly but causes a runtime KeyError crash before any payload
is processed, leaving an empty trace.

CS types with other policy schemas are not checked by this assertion:
- CS_MUTABLE_JSON_V0: STRUCTURE-based resolution via storage_structure_artifact
- CS_APPENDONLY_JSONL_V0: entity-based __pgs_store_entity__ resolution
- CS_REGISTRY_V0: entity-based __pgs_store_entity__ resolution (same pattern as
  CS_APPENDONLY_JSONL_V0 — StorageUnavailable raised loudly if entity unresolvable)

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only.
"""

# CS types whose runtime implementations call policy['path'] directly.
# These must declare a non-empty policy.path in every RB binding.
# Currently empty: all current CS types use STRUCTURE-based or entity-based resolution.
# CS_REGISTRY_V0 was removed when it migrated to entity-based __pgs_store_entity__
# resolution (same pattern as CS_APPENDONLY_JSONL_V0).
_FILE_PATH_CS_TYPES = frozenset()


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate RB binding policy conformance for file-path CS types.

    For every RB artifact, for every CS binding key in _FILE_PATH_CS_TYPES:
    - `policy.path` must be declared and non-empty.
    - `policy: {}` is a violation — it causes a runtime KeyError crash.

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
    # What was EXAMINED, not what was iterated. Counting RB artifacts here reported "5 examined"
    # while `_FILE_PATH_CS_TYPES` was empty and no binding was checked at all — vacuity wearing the
    # shape of coverage. A count that can be zero is what makes an empty scope visible.
    examined = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "RB":
            continue

        fqdn = artifact.get("fqdn_id", artifact.get("artifact_code", "UNKNOWN"))
        bindings = artifact.get("frontmatter", {}).get("core", {}).get("bindings", {})

        if not isinstance(bindings, dict):
            continue

        for binding_key, binding_value in bindings.items():
            # Extract CS artifact code from FQDN
            # e.g., "capability_side_effects::CS_REGISTRY_V0" → "CS_REGISTRY_V0"
            cs_code = binding_key.split("::")[-1] if "::" in binding_key else binding_key

            if cs_code not in _FILE_PATH_CS_TYPES:
                # Not a file-path CS type — policy schema is unconstrained here
                continue

            examined += 1

            # File-path CS type: policy.path must be declared and non-empty
            if not isinstance(binding_value, dict):
                violations.append({
                    "assert": "ASSERT_RB_BINDING_POLICY_CONFORMANCE_V0",
                    "artifact": fqdn,
                    "binding_key": binding_key,
                    "violation": (
                        f"RB binding '{binding_key}' has no binding block. "
                        f"CS type '{cs_code}' requires explicit policy.path."
                    ),
                    "fix": f"Add 'policy: {{path: \"<storage-path>\"}}' to the binding for '{binding_key}'.",
                })
                continue

            policy = binding_value.get("policy")

            if not isinstance(policy, dict):
                violations.append({
                    "assert": "ASSERT_RB_BINDING_POLICY_CONFORMANCE_V0",
                    "artifact": fqdn,
                    "binding_key": binding_key,
                    "violation": (
                        f"RB binding '{binding_key}' missing policy block. "
                        f"CS type '{cs_code}' requires explicit policy.path."
                    ),
                    "fix": f"Add 'policy: {{path: \"<storage-path>\"}}' to the binding for '{binding_key}'.",
                })
                continue

            path_value = policy.get("path")
            if not path_value or not str(path_value).strip():
                violations.append({
                    "assert": "ASSERT_RB_BINDING_POLICY_CONFORMANCE_V0",
                    "artifact": fqdn,
                    "binding_key": binding_key,
                    "violation": (
                        f"RB binding '{binding_key}' has empty or missing policy.path. "
                        f"CS type '{cs_code}' calls policy['path'] at runtime — "
                        f"an empty policy causes a KeyError crash before any payload is processed."
                    ),
                    "fix": (
                        f"Set policy.path to the storage file path for this binding. "
                        f"Example: 'policy: {{path: \"{{{{module_data_root}}}}/blockchain/consensus_pos/registry/validators.json\"}}'"
                    ),
                })

    return {
        "assert_count": examined,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
