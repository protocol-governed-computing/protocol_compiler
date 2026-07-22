"""ArtifactKindRegistry — the single source of truth for artifact-kind metadata.

The compiler owns *how to process* artifact kinds; it must not scatter *what kinds exist* across a
handful of disconnected dictionaries. This module replaces five maps that had drifted apart
(`_TYPE_TO_KIND`, `_GOVERNANCE_PREFIXES`, the directory `type_map`, `PPS_SECTION_BY_KIND`, and the
per-build `artifact_types` whitelist) with one `ArtifactKindDescriptor` per type-prefix.

Every consumer asks the registry a question instead of indexing a raw map:

    registry.descriptor("ENTITY").materialization_directory   # "entities"
    registry.node_kind("ENTITY")                              # "GOVERNANCE"
    registry.canonical_type("GOVERNANCE", "ENTITY_BLOCK_V0")  # "ENTITY"

Disposition separates the two axes `NodeKind` was conflating:
  * EXECUTABLE  — participates in the execution topology (WF/CC/CT/CS/IN/RB/EV/AC/TI/TE)
  * DECLARATIVE — inert definition the topology references (ENTITY/STRUCTURE/SCHEMA/CONSTITUTION/…)

`node_kind` is a *string* (the `NodeKind` value), so this governance-layer module never imports the
compiler's enum (dependency layering: compiler ← governance). The compiler maps the string to its
`NodeKind` at its own boundary.

This is `BuiltInArtifactRegistry` — the substrate bootstrap, exactly as a C compiler ships built-in
lexical grammar. Step 4 promotes it to a governed protocol artifact: a `CompiledArtifactRegistry`
loads the same `ArtifactKindDescriptor`s from the protocol surface, and *nothing downstream changes*
— consumers still ask the registry the same questions. The descriptor fields below ARE that registry's
schema, revealed by the first entity integration.
"""

from __future__ import annotations

from dataclasses import dataclass

EXECUTABLE = "EXECUTABLE"
DECLARATIVE = "DECLARATIVE"


@dataclass(frozen=True)
class ArtifactKindDescriptor:
    """Everything the pipeline needs to know about one artifact kind. One object, not five maps."""
    prefix: str                         # the artifact-code type token, e.g. "ENTITY", "CC", "STRUCTURE"
    node_kind: str                      # NodeKind value (string): the topology classification
    disposition: str                    # EXECUTABLE | DECLARATIVE
    materialization_directory: str | None = None   # output dir under artifacts/, or None if not materialized here
    pps_section: str | None = None      # PPS authoring-surface section, or None if not source-inspectable
    canonical_keeps_prefix: bool = True # in canonical projection: keep this prefix vs collapse to node_kind

    @property
    def inspectable_source(self) -> bool:
        return self.pps_section is not None


def _d(prefix, node_kind, disposition, directory=None, pps=None, keeps_prefix=True):
    return ArtifactKindDescriptor(prefix, node_kind, disposition, directory, pps, keeps_prefix)


# The complete built-in table. Values are the EXACT union of the five legacy maps, so the registry is
# behavior-identical. EXECUTABLE kinds keep their prefix in canonical (node_kind == prefix); DECLARATIVE
# kinds that ride NodeKind.GOVERNANCE keep their prefix only when listed (the old _GOVERNANCE_PREFIXES),
# else they collapse to "GOVERNANCE".
_DESCRIPTORS: tuple[ArtifactKindDescriptor, ...] = (
    # EXECUTABLE — execution topology
    _d("WF", "WF", EXECUTABLE, "workflows", "workflows"),
    _d("CC", "CC", EXECUTABLE, "capability_contracts", "capability_contracts"),
    _d("CT", "CT", EXECUTABLE, "capability_transforms", "capability_transforms"),
    _d("CS", "CS", EXECUTABLE, "capability_side_effects", "capability_side_effects"),
    _d("IN", "IN", EXECUTABLE, "intents", "intents"),
    _d("TI", "TI", EXECUTABLE, "ingress_intents"),
    _d("TE", "TE", EXECUTABLE, "transport/egress"),
    _d("RB", "RB", EXECUTABLE, "runtime_bindings", "runtime_bindings"),
    _d("EV", "EV", EXECUTABLE, "events"),
    _d("AC", "AC", EXECUTABLE, "actors"),
    # DECLARATIVE — own NodeKind
    _d("ASSERT", "ASSERT", DECLARATIVE, "assertions"),
    _d("TEST_DATA", "TEST_DATA", DECLARATIVE),
    # DECLARATIVE — ride NodeKind.GOVERNANCE, keep their prefix (old _GOVERNANCE_PREFIXES)
    _d("INVARIANT", "GOVERNANCE", DECLARATIVE, "invariants"),
    _d("VOCAB", "GOVERNANCE", DECLARATIVE, "vocabulary"),
    _d("CONSTITUTION", "GOVERNANCE", DECLARATIVE, "concerns"),
    _d("SCHEMA", "GOVERNANCE", DECLARATIVE, "schemas"),
    _d("STRUCTURE", "GOVERNANCE", DECLARATIVE, "structures"),
    _d("SURFACE", "GOVERNANCE", DECLARATIVE, "surface_contracts"),
    _d("ENTITY", "GOVERNANCE", DECLARATIVE, "entities", "entities"),
    # DECLARATIVE — ride NodeKind.GOVERNANCE, collapse to "GOVERNANCE" in canonical (not in old prefixes)
    _d("LAYER", "GOVERNANCE", DECLARATIVE, keeps_prefix=False),
    _d("GOVERNANCE", "GOVERNANCE", DECLARATIVE, keeps_prefix=False),
)


class BuiltInArtifactRegistry:
    """The substrate bootstrap registry. Step 4 swaps in a CompiledArtifactRegistry with the same API."""

    def __init__(self, descriptors: tuple[ArtifactKindDescriptor, ...] = _DESCRIPTORS):
        self._by_prefix = {d.prefix: d for d in descriptors}

    def descriptor(self, prefix: str) -> ArtifactKindDescriptor | None:
        return self._by_prefix.get(prefix)

    def known(self, prefix: str) -> bool:
        return prefix in self._by_prefix

    def node_kind(self, prefix: str) -> str | None:
        d = self._by_prefix.get(prefix)
        return d.node_kind if d else None

    def directory(self, prefix: str) -> str:
        """Output directory for a type prefix. Raises ValueError (legacy contract) if unmapped."""
        d = self._by_prefix.get(prefix)
        if d is None or d.materialization_directory is None:
            valid = sorted(p for p, x in self._by_prefix.items() if x.materialization_directory)
            raise ValueError(f"Unknown artifact type prefix: {prefix}\nValid prefixes: {', '.join(valid)}")
        return d.materialization_directory

    def pps_section(self, prefix: str) -> str | None:
        d = self._by_prefix.get(prefix)
        return d.pps_section if d else None

    def pps_sections(self) -> dict[str, str]:
        """Prefix → PPS section, for every source-inspectable kind (replaces PPS_SECTION_BY_KIND)."""
        return {p: d.pps_section for p, d in self._by_prefix.items() if d.pps_section}

    def canonical_type(self, node_kind: str, artifact_code: str) -> str:
        """The artifact_type written into the canonical projection (replaces _resolve_artifact_type).

        Non-GOVERNANCE node kinds: the node_kind IS the prefix. GOVERNANCE node kinds: keep the code's
        prefix when the descriptor says so (old _GOVERNANCE_PREFIXES), else collapse to "GOVERNANCE".
        """
        if node_kind != "GOVERNANCE":
            return node_kind
        for d in self._by_prefix.values():
            if d.node_kind == "GOVERNANCE" and d.canonical_keeps_prefix \
                    and artifact_code.startswith(d.prefix + "_"):
                return d.prefix
        return node_kind


# The process-wide built-in registry. Import this; never re-create raw maps.
REGISTRY = BuiltInArtifactRegistry()
