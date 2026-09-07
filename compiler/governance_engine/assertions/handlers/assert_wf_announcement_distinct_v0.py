"""
ASSERT_WF_ANNOUNCEMENT_DISTINCT_V0 Handler

Validates that a terminal node announces each moment at most once, and that every moment it
announces is a fully-qualified identity.

An announcement is an ordered sequence, and a repeat inside one is easy to introduce and invisible
afterwards: the trail is append-only, so a moment stated twice produces an account saying something
happened twice when it happened once, permanently. A single moment is a sequence of one — that is
how every act announcing today is read, and this handler treats it so rather than requiring the
corpus to be rewritten as lists.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

TERMINAL_TYPES = {"EXIT", "EXIT_SUCCESS"}


def _announced(emit) -> list[str]:
    """The moments a node announces, in declared order.

    A string is a sequence of one. Anything else that is not a list is left to the schema, which
    states the admitted shapes; reporting it here as well would say one thing twice.
    """
    if isinstance(emit, str):
        return [emit]
    if isinstance(emit, list):
        return [m for m in emit if isinstance(m, str)]
    return []


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    wf_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_code = artifact.get("artifact_code", "UNKNOWN")
        wf_count += 1

        nodes = artifact.get("frontmatter", {}).get("core", {}).get("nodes", {})
        for node_name, node_def in nodes.items():
            if node_def.get("type") not in TERMINAL_TYPES:
                continue
            announced = _announced(node_def.get("emit"))
            if not announced:
                continue

            seen = set()
            for moment in announced:
                if moment in seen:
                    violations.append({
                        "assert": "ASSERT_WF_ANNOUNCEMENT_DISTINCT_V0",
                        "artifact": wf_code,
                        "node": node_name,
                        "moment": moment,
                        "violation": (
                            f"'{moment}' is announced twice at one ending — the account would "
                            f"state that it happened twice when it happened once, and the trail "
                            f"is append-only, so neither entry can be withdrawn"
                        ),
                        "fix": "Announce the moment once, or distinguish the two moments meant",
                    })
                seen.add(moment)

                if "::" not in moment:
                    violations.append({
                        "assert": "ASSERT_WF_ANNOUNCEMENT_DISTINCT_V0",
                        "artifact": wf_code,
                        "node": node_name,
                        "moment": moment,
                        "violation": (
                            f"'{moment}' is not a fully-qualified identity — what an act announces "
                            f"must resolve to a declared artifact rather than to a bare name"
                        ),
                        "fix": "Name the moment as <domain>::EV_<NAME>_V<n>",
                    })

    return {
        "assert_count": wf_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
