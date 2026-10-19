"""
ASSERT_SUPERSEDED_NOT_REFERENCED_V0 Handler

Validates that no **live** artifact references a superseded one.

The relation is declared once, on the successor, as `supersedes` (`4e` SU-3), and an artifact is
superseded when an artifact present names it there. A predecessor declares nothing about its own
retirement, so it cannot claim to be superseded by nothing: SU-4 holds by construction. A
`supersedes` naming an identity the composition no longer holds is a predecessor deleted, and the
retirement ledger, not this handler, answers for that deletion.

Supersession is a declared relation between two exact identities, never a resolution rule. This
handler is what makes the declaration mean something: without it a superseded artifact stays
compiled, stays dispatchable, and everything that referenced it goes on reaching it — so a change
could stand a workflow down, report success, and leave the composition executing what it retired.

The closure binds live artifacts only. A retired artifact naming another retired one is coherent
history: an entry intent and the workflow it dispatched are stood down together, and each still says
what it said. Refusing that would oblige a change to rewrite the records it is retiring.

CONSTITUTIONAL: Pure rule checker — reads pre-computed structure from artifacts.
"""
from compiler.atoms.force import predecessors


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
# (`supersession` in artifact::VOCAB_DECLARATION_REPRESENTATION_V0), not a list kept here.




def _reached(frontmatter: dict, own: str, representation) -> set:
    """Every identity a live declaration reaches, by full name or by short code.

    A full name is a reference only in a part the platform declares one, and S1 refuses a full name
    anywhere else, so the declaration finds every full name there is. A short code is not declared
    anywhere yet, and nothing else guards one, so every string outside a supersession part is still
    read for one. This check must see no less than it did before references were declared.
    """
    found, _ = representation.references(frontmatter, own)

    # A workflow labels its places and routes between them by those labels, conventionally spelled
    # as the code each place runs. A label is local, not a reference: after a contract is replaced
    # and the place re-pointed, its `code` names the successor while its label and the routes to it
    # keep the old spelling. Outside a declared reference part, a value naming one of the
    # workflow's own places is that label.
    nodes = (frontmatter.get("core") or {}).get("nodes") if isinstance(
        frontmatter.get("core"), dict) else None
    labels = set(nodes) if isinstance(nodes, dict) else set()

    def walk(value, under):
        if isinstance(value, dict):
            for key, item in value.items():
                if key not in representation.supersession:
                    walk(item, under or key in representation.reference)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item, under)
        elif isinstance(value, str) and "::" not in value and (under or value not in labels):
            found.add(value)

    walk(frontmatter, False)
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

    by_identity: dict[str, str] = {}      # fqdn and bare code -> fqdn
    successors: dict[str, list[str]] = {}  # predecessor fqdn -> the artifacts standing in its place
    for artifact in artifacts:
        fqdn, bare = _identity(artifact)
        if not fqdn:
            continue
        by_identity[fqdn] = fqdn
        by_identity.setdefault(bare, fqdn)
        for predecessor in predecessors(_frontmatter(artifact)):
            successors.setdefault(predecessor, []).append(fqdn)
    superseded = {fqdn for fqdn in successors if fqdn in by_identity}

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
                standing = ", ".join(sorted(successors[target]))
                violations.append({
                    "fqdn": fqdn,
                    "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                    "message": (f"{fqdn} references {target}, which is superseded by {standing}. "
                                f"A superseded artifact is unreachable — reaching it means the "
                                f"composition still runs what the design stood down"),
                    "fix": f"Re-point the reference at one of: {standing}",
                })

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
