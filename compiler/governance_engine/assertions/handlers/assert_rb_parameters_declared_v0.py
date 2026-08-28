"""
ASSERT_RB_PARAMETERS_DECLARED_V0 Handler

Validates that an RB's declared `parameters` list agrees with the `{{...}}` templates its
binding policies actually use.

An RB declares the template parameters its policies expand at runtime:

    parameters:
      - module_data_root
    core:
      bindings:
        capability_side_effects::CS_REGISTRY_V0:
          policy:
            path: "{{module_data_root}}/ai_governance/ai_licensing/license_registry.json"

The template itself is load-bearing — the compiler emits it as-is and the runtime expands it.
The `parameters` list is the *declaration* of what the RB requires, and nothing read it, so it
could disagree with the policies indefinitely without anyone noticing. Two failure directions:

- A template with no declared parameter is an **undeclared runtime requirement**: the RB depends
  on a value its own contract never announces.
- A declared parameter used by no template is a **stale declaration**: it says the binding needs
  something it does not, which misleads anyone provisioning the runtime.

Both are silent today. This assertion closes that gap, and turns `parameters` from documentation
that can drift into a checked contract.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only.
"""

import re

_TEMPLATE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _templates_in(value) -> set:
    """Every {{name}} appearing anywhere in a policy value, at any nesting depth."""
    found = set()
    if isinstance(value, str):
        found.update(_TEMPLATE.findall(value))
    elif isinstance(value, dict):
        for nested in value.values():
            found |= _templates_in(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found |= _templates_in(nested)
    return found


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate that RB `parameters` and policy templates agree.

    For every RB artifact:
    - Every `{{name}}` used in any binding policy MUST appear in `parameters`.
    - Every entry in `parameters` MUST be used by at least one binding policy template.

    An RB that declares no parameters and uses no templates is conformant.

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
    rb_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "RB":
            continue

        rb_count += 1
        fqdn = artifact.get("fqdn_id", artifact.get("artifact_code", "UNKNOWN"))
        frontmatter = artifact.get("frontmatter", {})

        declared_raw = frontmatter.get("parameters") or []
        declared = {str(p).strip() for p in declared_raw if str(p).strip()}

        bindings = frontmatter.get("core", {}).get("bindings", {})
        used = _templates_in(bindings) if isinstance(bindings, dict) else set()

        for name in sorted(used - declared):
            violations.append({
                "assert": "ASSERT_RB_PARAMETERS_DECLARED_V0",
                "artifact": fqdn,
                "parameter": name,
                "violation": (
                    f"Binding policy expands '{{{{{name}}}}}' but '{name}' is not declared in "
                    f"parameters. The RB depends on a runtime value its contract never announces."
                ),
                "fix": f"Add '{name}' to the RB's 'parameters' list.",
            })

        for name in sorted(declared - used):
            violations.append({
                "assert": "ASSERT_RB_PARAMETERS_DECLARED_V0",
                "artifact": fqdn,
                "parameter": name,
                "violation": (
                    f"Parameter '{name}' is declared but no binding policy expands "
                    f"'{{{{{name}}}}}'. The declaration is stale and misleads runtime provisioning."
                ),
                "fix": f"Remove '{name}' from 'parameters', or use it in a binding policy.",
            })

    return {
        "assert_count": rb_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
