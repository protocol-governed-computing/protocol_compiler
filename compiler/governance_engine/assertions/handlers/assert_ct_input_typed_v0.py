"""
ASSERT_CT_INPUT_TYPED_V0

Enforces capability_transforms::INVARIANT_CT_INPUT_TYPED_V0 at compile time.

A transform is given only values of the types it declares. Each input a contract binds to a transform
step has a source, and the source's type is known before the build:

  a literal                   the type of its value
  $.inputs.<field>            the type the contract declares for that input
  $.results.<step>.<name>     the type the earlier step's transform declares for the output that
                              step maps to <name>

The runtime checks the types a workflow is entered with, and not what one step gives another, so a
disagreement here would run. Refusing it at build keeps it out of every sealed snapshot.

A declaration of `any`, or a source whose type is not declared, is not compared. An integer
satisfies `number`. A transform this build cannot see is left to the reference checks, which refuse
it. A stood-down contract is not checked: it is present and not in force, and its successor is.
"""

from typing import Any

from compiler.atoms.force import in_force

RULE = "capability_transforms::INVARIANT_CT_INPUT_TYPED_V0"

_LITERAL = ((bool, "boolean"), (int, "integer"), (float, "number"), (str, "string"),
            (list, "array"), (dict, "object"))


def _literal_type(value: Any) -> str | None:
    for python_type, declared in _LITERAL:  # bool before int: a bool is an int in Python
        if isinstance(value, python_type):
            return declared
    return None


def _satisfies(given: str | None, declared: str | None) -> bool:
    if given is None or declared is None or "any" in (given, declared):
        return True
    return given == declared or (declared == "number" and given == "integer")


def _types(frontmatter: dict | None, part: str) -> dict[str, str | None]:
    fields = ((frontmatter or {}).get("core", {}) or {}).get(part, {}) or {}
    return {name: (spec or {}).get("type") for name, spec in fields.items() if isinstance(spec, dict)}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    local = compilation_context.get("artifacts_by_fqdn", {}) or {}
    imported = compilation_context.get("imported_frontmatter", {}) or {}

    def frontmatter(fqdn: str) -> dict | None:
        if fqdn in local:
            return local[fqdn].get("frontmatter", {}) or {}
        return imported.get(fqdn)

    violations: list[dict] = []
    checked = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue
        cc = artifact.get("frontmatter", {}) or {}
        if not in_force(cc):
            continue
        fqdn = artifact.get("fqdn_id", "unknown")
        contract_inputs = _types(cc, "inputs")
        produced: dict[str, dict[str, str | None]] = {}  # step -> name -> declared type

        for step in (cc.get("core", {}) or {}).get("pipeline", []) or []:
            if not isinstance(step, dict):
                continue
            step_id = step.get("step") or "unknown"
            transform = step.get("transform")
            ct = frontmatter(transform) if transform else None
            ct_inputs = _types(ct, "inputs")
            ct_outputs = _types(ct, "outputs")

            for field, source in (step.get("inputs") or {}).items():
                if ct is None or field not in ct_inputs:
                    continue
                if isinstance(source, str) and source.startswith("$.inputs."):
                    given = contract_inputs.get(source.split(".", 2)[2])
                elif isinstance(source, str) and source.startswith("$.results."):
                    parts = source.split(".")
                    given = produced.get(parts[2], {}).get(parts[3]) if len(parts) == 4 else None
                elif isinstance(source, str) and source.startswith("$."):
                    given = None
                else:
                    given = _literal_type(source)
                checked += 1
                if not _satisfies(given, ct_inputs[field]):
                    violations.append({
                        "fqdn": fqdn,
                        "rule": RULE,
                        "message": (f"Step '{step_id}' gives {transform} input '{field}' a {given}; "
                                    f"the transform declares {ct_inputs[field]}"),
                        "fix": (f"Bind '{field}' to a {ct_inputs[field]}, or run a transform that "
                                f"declares {given}"),
                    })

            names: dict[str, str | None] = {}
            for name, target in (step.get("outputs") or {}).items():
                if isinstance(target, str) and target.startswith("$.capability_result."):
                    names[name] = ct_outputs.get(target.split(".", 2)[2])
            produced[step_id] = names

    return {
        "assert_count": checked,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
