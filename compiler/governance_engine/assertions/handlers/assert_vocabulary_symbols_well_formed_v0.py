"""
ASSERT_VOCABULARY_SYMBOLS_WELL_FORMED_V0 Handler

Closes the symbol space against the declared vocabulary:

  1. every artifact code is UPPER_SNAKE_CASE with a version suffix
  2. every workflow node type appears in VOCAB_PROTOCOL_KINDS_V0.node_types
  3. every CC result_status_contract.allowed status appears in
     VOCAB_EXECUTION_STATES_V0.result_status

Rules 2 and 3 are evaluated only when the governing vocabulary artifact is present in
the compiled set — a build carrying no vocabulary cannot be measured against one.
"""

import re

RULE = "fb.vocabulary::INVARIANT_VOCABULARY_SYMBOLS_WELL_FORMED_V0"

ARTIFACT_CODE = re.compile(r"^[A-Z][A-Z0-9_]*_V[0-9]+$")


def _vocab_entries(artifacts: list[dict], code: str, *path: str) -> set[str] | None:
    for a in artifacts:
        if a.get("artifact_code") != code:
            continue
        node = a.get("frontmatter", {}) or {}
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                return None
        return set(node) if isinstance(node, list) else None
    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []

    def flag(fqdn: str, message: str, fix: str) -> None:
        violations.append({"fqdn": fqdn, "rule": RULE, "message": message, "fix": fix})

    # --- Rule 1: artifact code form ---
    for a in artifacts:
        code = a.get("artifact_code", "")
        if code and not ARTIFACT_CODE.match(code):
            flag(a.get("fqdn_id", code),
                 f"artifact code is not UPPER_SNAKE_CASE with a version suffix: {code}",
                 "Rename to <UPPER_SNAKE>_V<n>")

    # --- Rule 2: workflow node types ---
    node_types = _vocab_entries(artifacts, "VOCAB_PROTOCOL_KINDS_V0", "node_types", "entries")
    if node_types is not None:
        for wf in (a for a in artifacts if a.get("artifact_type") == "WF"):
            nodes = ((wf.get("frontmatter", {}) or {}).get("core", {}) or {}).get("nodes", {})
            if not isinstance(nodes, dict):
                continue
            for name, spec in nodes.items():
                ntype = spec.get("type") if isinstance(spec, dict) else None
                if ntype and ntype not in node_types:
                    flag(wf.get("fqdn_id", "unknown"),
                         f"workflow node '{name}' declares undeclared type '{ntype}'",
                         "Add the type to VOCAB_PROTOCOL_KINDS_V0.node_types, or use a declared one")

    # --- Rule 3: result statuses ---
    statuses = _vocab_entries(artifacts, "VOCAB_EXECUTION_STATES_V0", "result_status", "entries")
    if statuses is not None:
        for cc in (a for a in artifacts if a.get("artifact_type") == "CC"):
            core = (cc.get("frontmatter", {}) or {}).get("core", {}) or {}
            allowed = (core.get("result_status_contract", {}) or {}).get("allowed", [])
            for status in allowed if isinstance(allowed, list) else []:
                if status not in statuses:
                    flag(cc.get("fqdn_id", "unknown"),
                         f"undeclared result status '{status}'",
                         "Add it to VOCAB_EXECUTION_STATES_V0.result_status, or use a declared one")

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
