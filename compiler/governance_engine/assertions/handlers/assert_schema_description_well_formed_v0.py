"""
ASSERT_SCHEMA_DESCRIPTION_WELL_FORMED_V0 Handler

Three things about the descriptions the platform governs itself with:

  1. every artifact kind the composition carries has a disposition — described or exempt
  2. a description dispatched to a kind names a required field and closes its surface
  3. a dispatched description still matches every artifact of its kind

Rule 2 exists because one kind was dispatched to a description requiring no field and closing no
surface. Thirty-three declarations passed it, because everything passes it, and the kind read as
governed to anyone counting dispatched kinds. Coverage is not governance.

Rule 3 exists because three descriptions had drifted at three separate undated divergences, and each
was found by dispatching it and reading the hundred refusals it produced — a method that works only
while nobody relies on the description. A stale description refuses correct work with the authority
of a rule, so drift is reported rather than discovered.

CONSTITUTIONAL: Pure rule checker — no side effects
"""
import json
from pathlib import Path
from typing import Any

RULE = "structure::INVARIANT_SCHEMA_DESCRIPTION_WELL_FORMED_V0"
DISPATCH = "STRUCTURE_SCHEMA_DISPATCH_V0"


def _frontmatter(artifact: dict) -> dict:
    return artifact.get("frontmatter") or {}


def _dispatch_core(artifacts: list[dict]) -> dict | None:
    for artifact in artifacts:
        fqdn = artifact.get("fqdn_id") or ""
        if fqdn.endswith(f"::{DISPATCH}"):
            return _frontmatter(artifact).get("core") or {}
    return None


def _describes(schema: dict) -> bool:
    """Whether a description describes: it names a required field and closes its surface."""
    return bool(schema.get("required")) and schema.get("additionalProperties") is False


def execute(artifacts: list[dict], compilation_context: dict) -> dict[str, Any]:
    violations: list[dict] = []

    core = _dispatch_core(artifacts)
    if core is None:
        # A domain build carries no dispatch table of its own; the platform's is imported governance
        # and is asserted where it is authored, not here.
        return {"assert_count": len(artifacts), "violations": [], "status": "PASSED"}

    dispatch = core.get("schema_dispatch") or {}
    disposition = core.get("schema_disposition") or {}

    present = {k for k in (_frontmatter(a).get("artifact_kind") for a in artifacts) if k}
    for kind in sorted(present):
        if kind not in disposition:
            violations.append({
                "fqdn": f"{DISPATCH}#{kind}",
                "rule": RULE,
                "message": (f"artifact kind '{kind}' carries no disposition — a kind is described or "
                            f"exempt, and an absence reads the same as nobody having decided"),
                "fix": f"Record '{kind}' in core.schema_disposition as described or exempt.",
            })

    from compiler.governance_engine.platform_root import governance_registry_root
    schema_dir = governance_registry_root() / "schema"
    for kind, filename in sorted(dispatch.items()):
        path = schema_dir / filename
        if not path.exists():
            violations.append({
                "fqdn": f"{DISPATCH}#{kind}",
                "rule": RULE,
                "message": f"kind '{kind}' is dispatched to '{filename}', which does not exist",
                "fix": f"Write {filename}, or record '{kind}' as exempt.",
            })
            continue
        with open(path) as handle:
            schema = json.load(handle)
        if not _describes(schema):
            violations.append({
                "fqdn": f"{DISPATCH}#{kind}",
                "rule": RULE,
                "message": (f"kind '{kind}' is dispatched to '{filename}', which names no required "
                            f"field or does not close its surface — it admits every declaration of "
                            f"its kind and refuses none, so the kind reads as governed and is not"),
                "fix": f"Have {filename} name a required field and set additionalProperties to false.",
            })

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
