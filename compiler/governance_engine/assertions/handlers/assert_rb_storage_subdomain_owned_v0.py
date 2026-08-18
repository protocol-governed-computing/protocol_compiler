"""
ASSERT_RB_STORAGE_SUBDOMAIN_OWNED_V0 Handler

Validates that a runtime binding names the storage description its own subdomain wrote.

A binding naming another subdomain's description restates what that subdomain declares, so two
subdomains then describe one record and nothing says which is authoritative. That workaround is
what an act needing another subdomain's records reaches for today, and it passes every other
check — which is what makes it the easy wrong act.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter and module organization only
"""

RULE = "ASSERT_RB_STORAGE_SUBDOMAIN_OWNED_V0"


def _owning_subdomain(module_path: str | None) -> str | None:
    """The owning subdomain declared by an artifact's module organization.

    `<pkg>.registry.<subdomain>.<kind>` — the subdomain sits before a kind directory. A
    domain-level artifact (`<pkg>.registry.<kind>`) is owned by the domain and not by a
    subdomain, and reads as None. Derived exactly as the artifact index derives it, because two
    derivations of one fact are two facts.
    """
    if not module_path:
        return None
    parts = module_path.split(".")
    if len(parts) >= 4 and parts[1] == "registry":
        return parts[2]
    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """Hold every binding to describing only its own subdomain's storage."""
    violations: list[dict] = []
    checked = 0

    # Indexed by identity across every artifact, not by kind. A storage description does not
    # reach this stage as a STRUCTURE — the kinds present here are the executable families plus
    # GOVERNANCE — so filtering by kind produced an empty index and a rule that passed on
    # everything. Identity is what the binding names, so identity is what to look it up by.
    by_identity = {a.get("fqdn_id"): a for a in artifacts if a.get("fqdn_id")}

    for artifact in artifacts:
        if artifact.get("artifact_type") != "RB":
            continue

        core = (artifact.get("frontmatter") or {}).get("core") or {}
        named = core.get("storage_structure")
        if not named:
            # A binding that addresses no records has no description to own or borrow.
            continue

        checked += 1
        rb_code = artifact.get("artifact_code", "UNKNOWN")
        mine = _owning_subdomain(artifact.get("module_path"))

        structure = by_identity.get(named)
        if structure is None:
            # Not deferred to another assertion. Nothing else asserts that a binding's
            # `storage_structure` resolves — `ASSERT_FQDN_ONLY_REFERENCES_V0` holds the shape of a
            # reference and not its resolution — so a skip here would be a rule reporting nothing
            # about a binding that names a description the composition does not hold.
            violations.append({
                "assert": RULE,
                "artifact": rb_code,
                "storage_structure": named,
                "violation": (
                    f"binding '{rb_code}' names storage description '{named}', which no artifact "
                    f"in this composition declares. Whose records it describes cannot be "
                    f"established, so whether the binding speaks for its own subdomain is unchecked"
                ),
                "fix": (
                    f"name a description the composition holds, or add the artifact that declares "
                    f"'{named}' to the domain being compiled"
                ),
            })
            continue

        theirs = _owning_subdomain(structure.get("module_path"))

        # `None` is a value here rather than an absence: an artifact organized as
        # `<pkg>.registry.<kind>` is owned by its domain and not by a subdomain, which the artifact
        # index states and the conformance workload demonstrates — it declares no subdomains at
        # all, so its binding and its storage description are both domain-owned and agree.
        #
        # Compared as (domain, subdomain), because a binding naming another *domain's* description
        # is the same defect one level up, and two domain-owned artifacts in different domains
        # would otherwise read as equal.
        mine_domain = str(artifact.get("fqdn_id") or "").split("::")[0]
        their_domain = named.split("::")[0]
        if (mine_domain, mine) == (their_domain, theirs):
            continue

        where_mine = f"{mine_domain}/{mine}" if mine else mine_domain
        where_theirs = f"{their_domain}/{theirs}" if theirs else their_domain

        violations.append({
            "assert": RULE,
            "artifact": rb_code,
            "storage_structure": named,
            "violation": (
                f"binding '{rb_code}' belongs to {where_mine} and names storage described by "
                f"{where_theirs}. A description maintained by someone other than the owner of what "
                f"it describes is a second copy of one truth, and the second copy is the one "
                f"nobody maintains"
            ),
            "fix": (
                f"{where_theirs} describes those records; leave the description where it is. An "
                f"act that must consult them reaches them as a declared reach, which is a change "
                f"to how an act resolves its records — not a line in this binding"
            ),
        })

    return {
        "assert_count": checked,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
