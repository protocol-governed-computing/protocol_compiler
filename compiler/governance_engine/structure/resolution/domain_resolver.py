"""
domain_resolver.py — Domain extraction from artifact paths.

Single source of truth for domain resolution.
MUST NOT be duplicated in any other module.

Governed by: CONSTITUTION_STRUCTURE_V0
"""

from pathlib import Path


def extract_domain_from_path(artifact_path: Path) -> str | None:
    """
    Extract domain name from artifact filesystem path.

    Domain artifacts follow pattern:
        .../domains/<domain_name>/registry/registry/...
        .../domains/<domain_name>/compiled/artifacts/...

    Args:
        artifact_path: Full filesystem path to artifact file

    Returns:
        Domain name (e.g., "blockchain", "ai_licensing", "agent_governance")
        or None if not a domain artifact

    Examples:
        >>> p = Path("/pgs/pgs_domains/domains/blockchain/registry/registry/workflows/WF_CREATE_WALLET_V0.md")
        >>> extract_domain_from_path(p)
        'blockchain'

        >>> p = Path("/pgs/pgs_governance/registry/registry/concerns/CONSTITUTION_WORKFLOW_V0.md")
        >>> extract_domain_from_path(p)
        None
    """
    parts = artifact_path.parts

    try:
        # Find 'domains' directory in path
        domains_idx = parts.index('domains')

        # Domain name is the next part after 'domains'
        if domains_idx + 1 < len(parts):
            domain_name = parts[domains_idx + 1]

            # Validate domain name (no special chars, reasonable length)
            if _is_valid_domain_name(domain_name):
                return domain_name

    except ValueError:
        # 'domains' not in path - not a domain artifact
        pass

    return None


def extract_domain_from_artifact_path(artifact_path: Path) -> str:
    """
    Extract domain name from artifact path (strict version - raises on failure).

    PROTOCOL SURFACE CLOSURE: Domain identity derived from artifact path structure,
    not from string parsing or inference.

    Governed by: INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0

    Args:
        artifact_path: Full filesystem path to domain artifact file

    Returns:
        Domain name (guaranteed non-None)

    Raises:
        RuntimeError: If domain cannot be extracted from path

    Examples:
        >>> p = Path("/pgs/pgs_domains/domains/blockchain/compiled/artifacts/workflows/WF_CREATE_WALLET_V0.json")
        >>> extract_domain_from_artifact_path(p)
        'blockchain'

        >>> p = Path("/pgs/pgs_governance/registry/registry/CONSTITUTION_WORKFLOW_V0.md")
        >>> extract_domain_from_artifact_path(p)
        RuntimeError: DOMAIN_RESOLUTION_FAILED
    """
    domain = extract_domain_from_path(artifact_path)

    if domain is None:
        from compiler.governance_engine.structure.exceptions import DomainResolutionError
        raise DomainResolutionError(
            message="Cannot extract domain from artifact path. "
                    "Domain artifacts MUST have domain resolved from source path. "
                    "This prevents cross-domain isolation violations.",
            details={
                "path": str(artifact_path),
                "governed_by": "INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0"
            }
        )

    return domain


def _is_valid_domain_name(name: str) -> bool:
    """
    Validate domain name follows conventions.

    Rules:
    - Alphanumeric + underscore only
    - Not empty
    - Reasonable length (1-50 chars)

    Args:
        name: Candidate domain name

    Returns:
        True if valid domain name
    """
    if not name:
        return False

    if len(name) > 50:
        return False

    # Allow alphanumeric and underscore
    return all(c.isalnum() or c == '_' for c in name)
