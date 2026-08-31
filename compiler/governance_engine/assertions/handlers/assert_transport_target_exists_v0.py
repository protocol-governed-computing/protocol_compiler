"""
ASSERT_TRANSPORT_TARGET_EXISTS_V0 Handler

Every TI_ artifact must declare an explicit, static invocation target appropriate to its
handler KIND. A boundary with no destination is a dead letter.

What "target" means is kind-dependent, and the check is as strong as each kind allows:

    WF_INVOCATION    handler.workflow  — must resolve to a WF in the compiled artifact set
    SNAPSHOT_READ    handler.operation — must be declared and static
    SNAPSHOT_QUERY   handler.operation — must be declared and static

Only WF_INVOCATION can be checked for resolvability, because only its target is an artifact.
An inspection target is an Operation Identity resolved by the inspector's own internal
registry, which belongs to no compiled artifact set — the compiler cannot see it without
importing an implementation, which compiler purity forbids. The check for those kinds is
therefore declared-and-static, and says so rather than pretending to more.

The kind set is CLOSED: an unrecognised handler kind is a violation, never a pass. Every TI is
counted in `assert_count` whatever its kind, so a weaker check stays visible instead of looking
like an absence of subjects.

CONSTITUTIONAL: Pure rule checker — reads artifact set from context.
"""

# Declared target field per handler kind. Closed set; no fallback, no inference.
_TARGET_FIELD = {
    "WF_INVOCATION": "workflow",
    "SNAPSHOT_READ": "operation",
    "SNAPSHOT_QUERY": "operation",
}

# Kinds whose target is an artifact, and can therefore be resolved against the compiled set.
_RESOLVABLE_KINDS = {"WF_INVOCATION"}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate TI_ artifact invocation target bindings.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []

    # Index of declared WF artifact codes and FQDNs — the resolvable target population.
    wf_codes: set[str] = set()
    wf_fqdns: set[str] = set()
    for a in artifacts:
        if a.get("artifact_type") == "WF":
            code = a.get("artifact_code")
            fqdn = a.get("fqdn_id")
            if code:
                wf_codes.add(code)
            if fqdn:
                wf_fqdns.add(fqdn)

    ti_count = 0
    for artifact in artifacts:
        if artifact.get("artifact_type") != "TI":
            continue

        ti_code = artifact.get("artifact_code", "UNKNOWN")
        ti_count += 1
        handler = artifact.get("frontmatter", {}).get("handler", {}) or {}
        kind = handler.get("kind")

        target_field = _TARGET_FIELD.get(kind)
        if target_field is None:
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "handler_kind": kind,
                "violation": f"TI declares handler.kind '{kind}', which is not a governed kind",
                "fix": f"Declare one of: {sorted(_TARGET_FIELD)}",
            })
            continue

        target = handler.get(target_field)
        if not target:
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "handler_kind": kind,
                "violation": f"TI with handler.kind '{kind}' must declare handler.{target_field}",
                "fix": f"Add handler.{target_field} to declare the explicit governed target",
            })
            continue

        # Reject dynamic references ($ prefix) for EVERY kind — a target resolved at request
        # time is not a compile-time-closed boundary.
        if isinstance(target, str) and target.startswith("$"):
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "handler_kind": kind,
                "target": target,
                "violation": (f"TI handler.{target_field} must be a static target — "
                              "dynamic references are forbidden"),
                "fix": "Replace the dynamic reference with an explicit static target",
            })
            continue

        if kind not in _RESOLVABLE_KINDS:
            continue  # declared + static is the whole check this kind admits

        # Resolve: accept bare code or full FQDN
        bare = target.split("::")[-1] if "::" in target else target
        if bare not in wf_codes and target not in wf_fqdns:
            violations.append({
                "assert": "ASSERT_TRANSPORT_TARGET_EXISTS_V0",
                "artifact": ti_code,
                "handler_kind": kind,
                "workflow": target,
                "violation": (f"TI handler.workflow '{target}' does not resolve to a "
                              "declared WF artifact"),
                "fix": "Declare the target WF artifact or correct the FQDN reference",
            })

    return {
        "assert_count": ti_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
