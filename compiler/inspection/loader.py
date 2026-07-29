"""
Loader — read-only access to the materialized snapshot projections.

The workspace root is explicit: --workspace flag or PGS_WORKSPACE env var.
No cwd guessing, no relative traversal. The loader refuses to answer from
an invalid snapshot (snapshot_status.json gate) and exposes zero write APIs.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from compiler.inspection.errors import (
    ProjectionMissing,
    SnapshotInvalid,
    WorkspaceNotDeclared,
)

# Schema contracts this consumer understands.
_SUPPORTED_INDEX_SCHEMA_VERSIONS = frozenset({"v0"})
_SUPPORTED_EVIDENCE_PROJECTION_SCHEMA_VERSIONS = frozenset({"v0"})

# Behavior Logic tree. In an assembled snapshot this is domain-scoped:
#   behavior_logic/<domain>/<wf_code>/<wf_code>.{graph.json,projection.png}
_BEHAVIOR_LOGIC_ROOT = "behavior_logic"

# Declared MD header fields (mandated header format in every authoring doc).
_HEADER_FIELD_RE = re.compile(r"^- \*\*(?P<label>[A-Za-z ]+):\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE)

# Artifact kind → kind_index section.
# Single source of truth: the ArtifactKindRegistry (replaces the legacy hardcoded map).
from compiler.governance_engine.artifact_kinds import REGISTRY as _KIND_REGISTRY

INDEX_SECTION_BY_KIND = _KIND_REGISTRY.index_sections()


class Workspace:
    """
    Read-only handle over one pgs_workspace snapshot set.

    All projections are lazy-loaded and cached per instance.
    """

    def __init__(self, root: Path):
        self.root = root
        self._cache: dict[str, Any] = {}

    @classmethod
    def open(cls, workspace: str | None) -> "Workspace":
        """
        Resolve the workspace root and gate on snapshot validity.

        Resolution order: explicit argument, then PGS_WORKSPACE env var.
        Neither present → hard error. Snapshot not VALID → hard error.
        """
        declared = workspace or os.environ.get("PGS_WORKSPACE")
        if not declared:
            raise WorkspaceNotDeclared(
                "no workspace declared — pass --workspace <abs path> "
                "or set PGS_WORKSPACE"
            )
        root = Path(declared)
        if not root.is_absolute():
            raise WorkspaceNotDeclared(
                f"workspace must be an absolute path, got: {declared}"
            )
        if not root.is_dir():
            raise WorkspaceNotDeclared(f"workspace not found: {root}")

        ws = cls(root)
        status = ws.snapshot_status
        if status.get("status") != "VALID":
            raise SnapshotInvalid(
                f"snapshot is not VALID (status: {status.get('status', 'UNKNOWN')}, "
                f"reason: {status.get('reason', 'n/a')}) — "
                f"rebuild with: compiler.cli build --workspace {root}"
            )
        return ws

    # ── projections (all read-only) ──────────────────────────────

    @property
    def snapshot_status(self) -> dict[str, Any]:
        return self._load_json(
            "snapshot_status.json",
            hint="workspace has no snapshot_status.json — not a built workspace",
        )

    @property
    def manifest(self) -> dict[str, Any]:
        return self._load_json("manifest.json", hint="workspace has no manifest.json")

    @property
    def artifact_index(self) -> dict[str, Any]:
        index = self._load_json(
            "artifact_index/index.json",
            hint="artifact index not materialized — rebuild with compiler.cli build",
        )
        version = index.get("schema_version")
        if version not in _SUPPORTED_INDEX_SCHEMA_VERSIONS:
            raise ProjectionMissing(
                f"artifact index schema_version '{version}' not supported "
                f"(supported: {sorted(_SUPPORTED_INDEX_SCHEMA_VERSIONS)})"
            )
        return index

    @property
    def scopes(self) -> list[str]:
        """Structure scopes (e.g. blockchain) declared by the artifact index."""
        return sorted(self.artifact_index["structures"])

    def evidence(self, scope: str) -> dict[str, Any]:
        """Artifact-level semantic graph (nodes + typed edges) for one scope."""
        metadata = self._load_json(
            f"evidence_snapshot/{scope}/metadata.json",
            hint=f"evidence projection metadata missing for scope '{scope}'",
        )
        version = metadata.get("projection_schema_version")
        if version not in _SUPPORTED_EVIDENCE_PROJECTION_SCHEMA_VERSIONS:
            raise ProjectionMissing(
                f"evidence projection schema_version '{version}' not supported "
                f"for scope '{scope}' "
                f"(supported: {sorted(_SUPPORTED_EVIDENCE_PROJECTION_SCHEMA_VERSIONS)})"
            )
        return self._load_json(
            f"evidence_snapshot/{scope}/evidence.json",
            hint=f"evidence projection missing for scope '{scope}'",
        )

    def evidence_metadata(self, scope: str) -> dict[str, Any]:
        return self._load_json(
            f"evidence_snapshot/{scope}/metadata.json",
            hint=f"evidence projection metadata missing for scope '{scope}'",
        )

    def vocabulary_reverse(self, scope: str) -> dict[str, str]:
        """FQDN → address for one scope's address space."""
        return self._load_json(
            f"vocabulary_snapshot/{scope}/reverse.json",
            hint=f"vocabulary reverse.json missing for scope '{scope}'",
        )

    @property
    def kind_index(self) -> dict[str, Any]:
        return self._load_json(
            "kind_index/index.json",
            hint="kind index not materialized — rebuild the snapshot with the assembler",
        )

    def kind_index_entry(self, fqdn: str, kind: str) -> dict[str, Any]:
        """Snapshot-index entry for an FQDN, located via its declared kind."""
        section = INDEX_SECTION_BY_KIND.get(kind)
        if section is None:
            raise ProjectionMissing(
                f"artifact kind '{kind}' has no authoring surface "
                f"(covered kinds: {sorted(INDEX_SECTION_BY_KIND)})"
            )
        entry = self.kind_index.get(section, {}).get(fqdn)
        if entry is None:
            raise ProjectionMissing(f"'{fqdn}' not present in index section '{section}'")
        return entry

    def canonical_artifact(self, index_entry: dict[str, Any]) -> dict[str, Any]:
        """Load the canonical artifact named by an index entry."""
        return self._load_json(
            index_entry["canonical_path"],
            hint=f"canonical artifact missing: {index_entry['canonical_path']}",
        )

    @property
    def store_index(self) -> dict[str, Any]:
        index = self._load_json(
            "artifact_index/stores.json",
            hint="store index not materialized — rebuild with compiler.cli build",
        )
        version = index.get("schema_version")
        if version not in _SUPPORTED_INDEX_SCHEMA_VERSIONS:
            raise ProjectionMissing(
                f"store index schema_version '{version}' not supported "
                f"(supported: {sorted(_SUPPORTED_INDEX_SCHEMA_VERSIONS)})"
            )
        return index

    @property
    def conformance_results(self) -> dict[str, Any]:
        return self._load_json(
            "conformance_results.json",
            hint="conformance results not materialized — rebuild with compiler.cli build",
        )

    # ── Behavior Logic ───────────────────────────────────────────

    def behavior_logic_codes(self) -> list[str]:
        """Workflow codes with a materialized behavior logic projection, across all domains."""
        root = self.root / _BEHAVIOR_LOGIC_ROOT
        if not root.is_dir():
            raise ProjectionMissing(f"behavior logic tree not found: {root}")
        return sorted(
            wf.name
            for domain in root.iterdir() if domain.is_dir()
            for wf in domain.iterdir() if wf.is_dir()
        )

    def _behavior_logic_dir(self, wf_code: str) -> Path:
        """Locate a workflow's behavior-logic directory under its owning domain.

        The projection is domain-scoped, but the query surface is keyed by wf_code alone.
        A code present in two domains is ambiguous and fails hard rather than resolving
        to an arbitrary one.
        """
        root = self.root / _BEHAVIOR_LOGIC_ROOT
        if not root.is_dir():
            raise ProjectionMissing(f"behavior logic tree not found: {root}")
        found = sorted(d / wf_code for d in root.iterdir() if (d / wf_code).is_dir())
        if not found:
            raise ProjectionMissing(f"behavior logic not materialized for '{wf_code}'")
        if len(found) > 1:
            domains = ", ".join(p.parent.name for p in found)
            raise ProjectionMissing(
                f"'{wf_code}' is ambiguous — present in domains: {domains}"
            )
        return found[0]

    def behavior_logic_graph(self, wf_code: str) -> dict[str, Any]:
        path = self._behavior_logic_dir(wf_code) / f"{wf_code}.graph.json"
        return self._load_json(
            str(path.relative_to(self.root)),
            hint=f"behavior logic graph not materialized for '{wf_code}'",
        )

    def behavior_logic_png_path(self, wf_code: str) -> Path:
        path = self._behavior_logic_dir(wf_code) / f"{wf_code}.projection.png"
        if not path.is_file():
            raise ProjectionMissing(f"behavior logic PNG not materialized: {path}")
        return path

    # ── internal ─────────────────────────────────────────────────

    def _load_json(self, relative: str, hint: str) -> Any:
        return _load_json_file(self.root, relative, hint, self._cache)


def parse_header_fields(content: str) -> dict[str, str]:
    """
    Parse the mandated MD header block of a canonical artifact's content.

    Returns declared fields (e.g. 'Status', 'Supersedes', 'Version') keyed
    by label. Declared facts only — no defaults are synthesized.
    """
    return {
        m.group("label").strip(): m.group("value").strip()
        for m in _HEADER_FIELD_RE.finditer(content)
    }


# Degraded lifecycle classification (until the AR_ retirement model lands):
# explicit map over the declared header status — anything undeclared or
# unmapped is UNKNOWN, never guessed.
_LIFECYCLE_BY_DECLARED_STATUS = {
    "canonical": "ACTIVE",
    "active": "ACTIVE",
    "retired": "RETIRED",
}


def classify_lifecycle(declared_status: str | None) -> str:
    """Declared header status → ACTIVE / RETIRED / UNKNOWN."""
    return _LIFECYCLE_BY_DECLARED_STATUS.get((declared_status or "").lower(), "UNKNOWN")


def _load_json_file(root: Path, relative: str, hint: str, cache: dict[str, Any]) -> Any:
    if relative in cache:
        return cache[relative]
    path = root / relative
    if not path.is_file():
        raise ProjectionMissing(f"{hint} ({path})")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectionMissing(f"not valid JSON: {path}\n{exc}") from exc
    cache[relative] = data
    return data
