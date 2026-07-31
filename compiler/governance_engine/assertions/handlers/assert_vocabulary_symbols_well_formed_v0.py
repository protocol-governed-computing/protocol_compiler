"""
ASSERT_VOCABULARY_SYMBOLS_WELL_FORMED_V0 Handler

Closes the symbol space against the **vocabulary closure** of the build:

    visible vocabulary = reserved platform vocabulary
                       + imported governance
                       + authorized extensions
                       = the closure every symbol rule is evaluated against

There is no "platform vocabulary" versus "domain vocabulary" — a domain is not an independent
language, it is written in the PGC language. Every compile therefore begins with that language
already in scope (`s1_extract._inject_imported_governance` imports VOCABULARY alongside
INVARIANT), and a domain MAY extend the closure only where the reserving declaration permits it.

Rules:

  1. every artifact code is UPPER_SNAKE_CASE with a version suffix
  2. every workflow node type appears in the closure's `node_types`
  3. every CC result_status_contract.allowed status appears in the closure's `result_status`
  4. an extending vocabulary may only contribute to a category whose reserving declaration marks
     it `domain_extensible: true` (CONSTITUTION_VOCABULARY_V0 §9.1)
  5. an extension symbol may not collide with a reserved non-authorable word (§9.1)

Rules 2 and 3 are evaluated only when the governing category is present in the closure. That skip
is now near-unreachable by construction: a build carrying no vocabulary would have to have
imported no governance either.
"""

import re

RULE = "fb.vocabulary::INVARIANT_VOCABULARY_SYMBOLS_WELL_FORMED_V0"

ARTIFACT_CODE = re.compile(r"^[A-Z][A-Z0-9_]*_V[0-9]+$")

# The reserving declaration for each governed category — the artifact that owns the category and
# decides whether it is extensible. Extension is authorized by that artifact, never assumed.
_RESERVING = {
    "node_types": "VOCAB_PROTOCOL_KINDS_V0",
    "result_status": "VOCAB_EXECUTION_STATES_V0",
    "exit_reasons": "VOCAB_EXECUTION_STATES_V0",
}
_RESERVED_WORDS_VOCAB = "VOCAB_LANGUAGE_CONSTRAINTS_V0"
_RESERVED_WORDS_CATEGORY = "reserved_non_authorable"


def _vocabularies(artifacts: list[dict]) -> list[dict]:
    """Every VOCABULARY artifact visible in this build — the closure's source set."""
    return [
        a for a in artifacts
        if a.get("artifact_type") == "VOCAB"
        or (a.get("frontmatter", {}) or {}).get("artifact_kind") == "VOCABULARY"
    ]


def _category(artifact: dict, category: str) -> dict | None:
    node = (artifact.get("frontmatter", {}) or {}).get(category)
    return node if isinstance(node, dict) else None


def _entries(artifact: dict, category: str) -> list[str]:
    block = _category(artifact, category)
    entries = block.get("entries") if block else None
    return [e for e in entries if isinstance(e, str)] if isinstance(entries, list) else []


def _closure(artifacts: list[dict], category: str) -> set[str] | None:
    """Union a category's symbols across every visible vocabulary. None if nothing declares it."""
    contributing = [v for v in _vocabularies(artifacts) if _category(v, category) is not None]
    if not contributing:
        return None
    symbols: set[str] = set()
    for v in contributing:
        symbols.update(_entries(v, category))
    return symbols


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
    node_types = _closure(artifacts, "node_types")
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
                         "Add the type to the vocabulary closure, or use a declared one")

    # --- Rule 3: result statuses ---
    statuses = _closure(artifacts, "result_status")
    if statuses is not None:
        for cc in (a for a in artifacts if a.get("artifact_type") == "CC"):
            core = (cc.get("frontmatter", {}) or {}).get("core", {}) or {}
            allowed = (core.get("result_status_contract", {}) or {}).get("allowed", [])
            for status in allowed if isinstance(allowed, list) else []:
                if status not in statuses:
                    flag(cc.get("fqdn_id", "unknown"),
                         f"undeclared result status '{status}'",
                         "Use a declared status, or declare a domain VOCABULARY that extends an "
                         "extensible category of the reserving vocabulary")

    # --- Rules 4 & 5: extensions are authorized, and avoid reserved words ---
    vocabs = _vocabularies(artifacts)
    by_code = {v.get("artifact_code"): v for v in vocabs}
    reserving_words = by_code.get(_RESERVED_WORDS_VOCAB)
    reserved_words = set(_entries(reserving_words, _RESERVED_WORDS_CATEGORY)) if reserving_words else set()

    for v in vocabs:
        extends = (v.get("frontmatter", {}) or {}).get("extends")
        if not extends:
            continue  # a reserving declaration, not an extension
        fqdn = v.get("fqdn_id", v.get("artifact_code", "unknown"))
        target_code = extends.split("::")[-1]
        if target_code not in by_code:
            flag(fqdn,
                 f"extends '{extends}', which is not visible in this build's vocabulary closure",
                 "Reference a vocabulary present in the imported governance surface")
            continue
        target = by_code[target_code]
        for category, reserver in _RESERVING.items():
            if _category(v, category) is None:
                continue
            if reserver != target_code:
                flag(fqdn,
                     f"extends '{target_code}' but contributes to category '{category}', "
                     f"which is reserved by '{reserver}'",
                     f"Extend {reserver} instead, or drop the category")
                continue
            if (_category(target, category) or {}).get("domain_extensible") is not True:
                flag(fqdn,
                     f"category '{category}' of '{target_code}' is not domain-extensible",
                     f"Map the symbol onto a declared one, or have {target_code} declare "
                     f"'{category}.domain_extensible: true'")
                continue
            for symbol in _entries(v, category):
                if symbol in reserved_words:
                    flag(fqdn,
                         f"extension symbol '{symbol}' collides with a reserved non-authorable word",
                         "Choose a symbol outside "
                         f"{_RESERVED_WORDS_VOCAB}.{_RESERVED_WORDS_CATEGORY}")

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
