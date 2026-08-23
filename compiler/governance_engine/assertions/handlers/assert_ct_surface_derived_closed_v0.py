"""
ASSERT_CT_SURFACE_DERIVED_CLOSED_V0 Handler

Closes a domain's capability-transform surface by derivation: `declared == invoked`, within the
domain, with neither side a list anyone maintains.

The platform closes its own surface with an allow-list and is right to — an enumerated set is how a
deliberate set is stated. A domain cannot borrow that: the list belongs to the artifact carrying it,
so importing the platform's invariant asserts the platform's transforms against the domain's. That
is why the platform's invariant scopes itself to PLATFORM, and why for a while nothing closed a
domain surface at all — a workload's own closure invariant had been withdrawn as unnamed by any
constitution, and nothing would have refused a third transform being added there.

So the closure is stated once, by the platform, in a form that names no domain:

  declared   the transforms this domain's registry carries
  invoked    the transforms named by the pipeline steps of this domain's capability contracts

The platform's own surface is exempt and not by special-casing a name: platform transforms are
invoked by the domains that import them, so the equality is false there by construction. The build
that carries them is identified by `is_domain_build`, which the compiler already determines.

CONSTITUTIONAL: Pure rule checker — no side effects
"""
from typing import Any

RULE = "capability_transforms::INVARIANT_CT_SURFACE_DERIVED_CLOSED_V0"


def _frontmatter(artifact: dict) -> dict:
    return artifact.get("frontmatter") or {}


def _invoked(artifact: dict) -> set[str]:
    """Every transform a capability contract's pipeline names.

    Read from the pipeline rather than from a declared dependency list, because the pipeline is what
    executes. A contract that lists a transform it never steps through has not invoked it, and a
    closure taken over the list would call that reachable.
    """
    out: set[str] = set()
    for step in (_frontmatter(artifact).get("core") or {}).get("pipeline") or []:
        if not isinstance(step, dict):
            continue
        for key in ("transform", "capability"):
            value = step.get(key)
            if isinstance(value, str) and "::CT_" in value:
                out.add(value)
    return out


def execute(artifacts: list[dict], compilation_context: dict) -> dict[str, Any]:
    """Refuse a domain surface where a declared transform is unreached, or an invoked one unresolved.

    Args:
        artifacts: All validated artifacts of this build
        compilation_context: Carries `is_domain_build` and the imported platform surface

    Returns:
        {"assert_count": int, "violations": list[dict], "status": "PASSED"|"FAILED"}
    """
    violations: list[dict] = []

    # A platform build is not a domain surface. Its transforms are invoked by the domains that
    # import it, so `declared == invoked` is false there for a reason that is not a defect, and
    # `INVARIANT_CT_SURFACE_CLOSED_V1` is what closes it instead.
    if not compilation_context.get("is_domain_build", False):
        return {"assert_count": len(artifacts), "violations": [], "status": "PASSED"}

    imported = set(compilation_context.get("imported_surface_fqdns") or ())

    declared: set[str] = set()
    invoked: set[str] = set()
    for artifact in artifacts:
        fqdn = artifact.get("fqdn_id")
        if not fqdn:
            continue
        kind = _frontmatter(artifact).get("artifact_kind")
        if kind == "CAPABILITY_TRANSFORM":
            declared.add(fqdn)
        elif kind == "CAPABILITY_CONTRACT":
            invoked |= _invoked(artifact)

    for ct_fqdn in sorted(declared - invoked):
        violations.append({
            "fqdn": ct_fqdn,
            "rule": RULE,
            "message": ("declared capability transform is invoked by no capability contract of this "
                        "domain — the surface is not enumerable, because something executable exists "
                        "that no act reaches"),
            "fix": (f"Invoke '{ct_fqdn}' from a capability contract's pipeline, or withdraw it. A "
                    f"transform nothing reaches is closed by nothing."),
        })

    for ct_fqdn in sorted(invoked - declared - imported):
        violations.append({
            "fqdn": ct_fqdn,
            "rule": RULE,
            "message": ("capability contract invokes a transform declared neither in this domain nor "
                        "in the imported platform surface"),
            "fix": f"Declare '{ct_fqdn}' in this domain, or invoke one that resolves.",
        })

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
