"""
Shared reading of capability transforms for the molecule and non-determinism assertions.

A molecule names its steps by code or by FQDN; both resolve through one index, so each assertion
reads a step's target the same way rather than each carrying its own resolution.
"""

CONSTITUTION_DETERMINISTIC = "capability_transforms::CONSTITUTION_DETERMINISTIC_ATOMS_V0"
CONSTITUTION_MOLECULES = "capability_transforms::CONSTITUTION_MOLECULES_V0"
CONSTITUTION_NONDETERMINISTIC = "capability_transforms::CONSTITUTION_NONDETERMINISTIC_ATOMS_V0"

DETERMINISTIC_PURITIES = {"ct_pure", "ct_exec"}
NONDETERMINISTIC_PURITY = "ct_impure"
STEP_KINDS = {"atom", "molecule", "loop"}


def transforms(artifacts: list[dict]) -> list[dict]:
    return [a for a in artifacts if a.get("artifact_type") == "CT"]


def index(artifacts: list[dict]) -> dict[str, dict]:
    """Every transform, reachable by its FQDN and by its bare code."""
    out: dict[str, dict] = {}
    for a in transforms(artifacts):
        if a.get("fqdn_id"):
            out[a["fqdn_id"]] = a
        if a.get("artifact_code"):
            out.setdefault(a["artifact_code"], a)
    return out


def machine(artifact: dict) -> dict:
    m = artifact.get("frontmatter", {}).get("machine", {})
    return m if isinstance(m, dict) else {}


def kind(artifact: dict) -> str:
    return machine(artifact).get("ct_kind", "")


def purity(artifact: dict) -> str:
    return machine(artifact).get("ct_purity", "")


def steps(artifact: dict) -> list[dict]:
    s = machine(artifact).get("atom_stream", [])
    return [x for x in s if isinstance(x, dict)] if isinstance(s, list) else []


def step_target(step: dict) -> str:
    """The transform a step runs: an atom step names an atom; a molecule step or loop, a molecule."""
    if step.get("kind") == "atom":
        return step.get("atom", "")
    return step.get("molecule", "")


def reachable(start: dict, idx: dict[str, dict]) -> list[dict]:
    """Every transform reachable through a molecule's steps, excluding the molecule itself unless it
    is reached again. Unresolved targets are skipped; another assertion reports them."""
    seen: set[str] = set()
    out: list[dict] = []
    stack = [start]
    while stack:
        current = stack.pop()
        for step in steps(current):
            target = idx.get(step_target(step))
            if target is None:
                continue
            key = target.get("fqdn_id", "")
            if key in seen:
                continue
            seen.add(key)
            out.append(target)
            if kind(target) == "molecule":
                stack.append(target)
    return out
