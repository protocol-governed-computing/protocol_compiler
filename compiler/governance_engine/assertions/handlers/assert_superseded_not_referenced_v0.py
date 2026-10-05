"""
ASSERT_SUPERSEDED_NOT_REFERENCED_V0 Handler

Validates that:
1. Every artifact declaring `superseded_by` names at least one successor
2. Every named successor resolves to an artifact in the composition
3. No **live** artifact references a superseded one

Supersession is a declared relation between two exact identities, never a resolution rule. This
handler is what makes the declaration mean something: without it a superseded artifact stays
compiled, stays dispatchable, and everything that referenced it goes on reaching it — so a change
could stand a workflow down, report success, and leave the composition executing what it retired.

The closure binds live artifacts only. A retired artifact naming another retired one is coherent
history: an entry intent and the workflow it dispatched are stood down together, and each still says
what it said. Refusing that would oblige a change to rewrite the records it is retiring.

CONSTITUTIONAL: Pure rule checker — reads pre-computed structure from artifacts.
"""


def _identity(artifact: dict) -> tuple[str, str]:
    """An artifact's FQDN and its bare code, both of which a reference may legitimately use."""
    fqdn = str(artifact.get("fqdn_id") or "")
    return fqdn, fqdn.split("::")[-1] if fqdn else str(artifact.get("artifact_code") or "")


def _frontmatter(artifact: dict) -> dict:
    block = artifact.get("frontmatter")
    return block if isinstance(block, dict) else {}


# The supersession declaration is not a reference to what it replaces. Naming the artifact you stand
# in place of is the whole point of the relation; counting it as a reach would make every correct
# supersession its own violation. Which parts declare supersession is the platform's declaration
# (`supersession` in artifact::VOCAB_DECLARATION_REPRESENTATION_V1), not a list kept here.

def _successors(frontmatter: dict) -> list:
    """The successors an artifact names, however it names them.

    `superseded_by` is written as a list by construction and may be written as one identity by hand,
    and both are the same declaration. Iterating the scalar form yields its characters: one
    hand-authored supersession reported fifty-one violations, one per character of the successor's
    FQDN, each claiming a successor named `t`, `r`, `a`… and the whole of it read as fifty-one
    references to a retired artifact. Normalizing here is what makes the two spellings one fact.
    """
    value = frontmatter.get("superseded_by")
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)



def _reached(frontmatter: dict, own: str, representation) -> set:
    """Every identity a live declaration reaches, by full name or by short code.

    A full name is a reference only in a part the platform declares one, and S1 refuses a full name
    anywhere else, so the declaration finds every full name there is. A short code is not declared
    anywhere yet, and nothing else guards one, so every string outside a supersession part is still
    read for one. This check must see no less than it did before references were declared.
    """
    found, _ = representation.references(frontmatter, own)

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key not in representation.supersession:
                    walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, str) and "::" not in value:
            found.add(value)

    walk(frontmatter)
    return found


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    representation = compilation_context.get("representation")
    if representation is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "artifact::ASSERT_SUPERSEDED_NOT_REFERENCED_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing representation",
                "fix": "S1 must read the platform's declaration of what a reference is",
            }],
            "status": "FAILED",
        }
    violations = []

    superseded: dict[str, dict] = {}      # fqdn -> the artifact standing down
    by_identity: dict[str, str] = {}      # fqdn and bare code -> fqdn
    for artifact in artifacts:
        fqdn, bare = _identity(artifact)
        if not fqdn:
            continue
        by_identity[fqdn] = fqdn
        by_identity.setdefault(bare, fqdn)
        if _frontmatter(artifact).get("superseded_by"):
            superseded[fqdn] = artifact

    for fqdn, artifact in sorted(superseded.items()):
        successors = _successors(_frontmatter(artifact))
        if not successors:
            violations.append({
                "fqdn": fqdn,
                "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                "message": (f"{fqdn} declares superseded_by with no successor — 'superseded' with "
                            f"nothing standing in its place is a deletion wearing a softer word"),
                "fix": "Name the artifact that stands in its place, or delete it deliberately.",
            })
        for successor in successors:
            if str(successor) not in by_identity:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                    "message": (f"{fqdn} is superseded by {successor}, which is not in this "
                                f"composition — the artifact standing in its place must exist"),
                    "fix": f"Author {successor}, or correct the successor named.",
                })

    if not superseded:
        return {"assert_count": len(artifacts), "violations": [], "status": "PASSED"}

    for artifact in artifacts:
        fqdn, _ = _identity(artifact)
        # A retired artifact may name another. The closure is about what the composition can still
        # reach, and nothing reaches either of these.
        if not fqdn or fqdn in superseded:
            continue
        for value in _reached(_frontmatter(artifact), fqdn, representation):
            target = by_identity.get(value)
            if target and target in superseded and target != fqdn:
                successors = ", ".join(_successors(_frontmatter(superseded[target])))
                violations.append({
                    "fqdn": fqdn,
                    "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                    "message": (f"{fqdn} references {target}, which is superseded by {successors}. "
                                f"A superseded artifact is unreachable — reaching it means the "
                                f"composition still runs what the design stood down"),
                    "fix": f"Re-point the reference at one of: {successors}",
                })

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
