"""ArtifactKindRegistry — the single source of truth for artifact-kind metadata.

The compiler owns *how to process* artifact kinds; it must not scatter *what kinds exist* across a
handful of disconnected dictionaries. This module replaces five maps that had drifted apart
(`_TYPE_TO_KIND`, `_GOVERNANCE_PREFIXES`, the directory `type_map`, `INDEX_SECTION_BY_KIND`, and the
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

# Governance Ontology (spec fragment 03) — both axes are CLOSED per ontology version.
# §4 primary Semantic Category: exactly one per kind.
DEFINITIONAL, NORMATIVE, CONTRACTUAL = "Definitional", "Normative", "Contractual"
OPERATIONAL, PARTICIPATORY, EVIDENTIAL = "Operational", "Participatory", "Evidential"
SEMANTIC_CATEGORIES = (DEFINITIONAL, NORMATIVE, CONTRACTUAL, OPERATIONAL, PARTICIPATORY, EVIDENTIAL)
# §6 provenance: how the element came to exist. Semantic, not physical.
AUTHORED, DERIVED, PRODUCED = "authored", "derived", "produced"
PROVENANCES = (AUTHORED, DERIVED, PRODUCED)
# §7 runtime disposition is a CATEGORY CONTRACT property, never stored per kind — it is derived
# from the category so the two can never disagree. Distinct from the `disposition` field below,
# which answers a different question (topology participation).
_RUNTIME_DISPOSITION = {
    DEFINITIONAL:  "not executable",
    NORMATIVE:     "not executable",
    CONTRACTUAL:   "not independently executable",
    OPERATIONAL:   "executable",
    PARTICIPATORY: "participates in execution",
    EVIDENTIAL:    "produced by execution",
}


@dataclass(frozen=True)
class ArtifactKindDescriptor:
    """Everything the pipeline needs to know about one artifact kind. One object, not five maps."""
    prefix: str                         # the artifact-code type token, e.g. "ENTITY", "CC", "STRUCTURE"
    node_kind: str                      # NodeKind value (string): the topology classification
    disposition: str                    # EXECUTABLE | DECLARATIVE — TOPOLOGY PARTICIPATION only.
                                        # Not ontology §7 runtime disposition (see runtime_disposition).
    materialization_directory: str | None = None   # output dir under artifacts/, or None if not materialized here
    index_section: str | None = None    # kind_index section for this kind, or None if not indexed
    canonical_keeps_prefix: bool = True # in canonical projection: keep this prefix vs collapse to node_kind
    artifact_kind: str | None = None    # canonical in-block discriminator (Kind Vocabulary); None = not yet authorized
    semantic_category: str | None = None  # Governance Ontology §4 primary category; None = kind not authorized
    provenance: str | None = None         # Governance Ontology §6 provenance; None = kind not authorized

    @property
    def inspectable_source(self) -> bool:
        return self.index_section is not None

    @property
    def runtime_disposition(self) -> str | None:
        """Ontology §7 runtime disposition — derived from the category, never stored.

        Distinct from `disposition`: a CAPABILITY_CONTRACT participates in the execution
        topology (disposition == EXECUTABLE) yet is "not independently executable" (§7).
        """
        return _RUNTIME_DISPOSITION.get(self.semantic_category)


def _d(prefix, node_kind, disposition, directory=None, index_section=None, keeps_prefix=True, ak=None,
       category=None, provenance=None):
    return ArtifactKindDescriptor(prefix, node_kind, disposition, directory, index_section, keeps_prefix, ak,
                                  category, provenance)


# The complete built-in table. Values are the EXACT union of the five legacy maps, so the registry is
# behavior-identical. EXECUTABLE kinds keep their prefix in canonical (node_kind == prefix); DECLARATIVE
# kinds that ride NodeKind.GOVERNANCE keep their prefix only when listed (the old _GOVERNANCE_PREFIXES),
# else they collapse to "GOVERNANCE".
_DESCRIPTORS: tuple[ArtifactKindDescriptor, ...] = (
    # EXECUTABLE — execution topology
    _d("WF", "WF", EXECUTABLE, "workflows", "workflows", ak="WORKFLOW",
       category=OPERATIONAL, provenance=AUTHORED),
    _d("CC", "CC", EXECUTABLE, "capability_contracts", "capability_contracts", ak="CAPABILITY_CONTRACT",
       category=CONTRACTUAL, provenance=AUTHORED),
    _d("CT", "CT", EXECUTABLE, "capability_transforms", "capability_transforms", ak="CAPABILITY_TRANSFORM",
       category=OPERATIONAL, provenance=AUTHORED),
    _d("CS", "CS", EXECUTABLE, "capability_side_effects", "capability_side_effects", ak="CAPABILITY_SIDE_EFFECT",
       category=OPERATIONAL, provenance=AUTHORED),
    _d("IN", "IN", EXECUTABLE, "intents", "intents", ak="INTENT",
       category=OPERATIONAL, provenance=AUTHORED),
    _d("TI", "TI", EXECUTABLE, "ingress_intents", ak="TRANSPORT_INGRESS",
       category=CONTRACTUAL, provenance=AUTHORED),
    _d("TE", "TE", EXECUTABLE, "transport/egress", ak="TRANSPORT_EGRESS",
       category=CONTRACTUAL, provenance=AUTHORED),
    _d("RB", "RB", EXECUTABLE, "runtime_bindings", "runtime_bindings", ak="RUNTIME_BINDING",
       category=OPERATIONAL, provenance=AUTHORED),
    # EVENT: the *kind* is an authored declaration of an event type (schema + trigger). The
    # produced elements — event occurrences and trace records — belong to the runtime evidence
    # model, not the artifact-kind ontology, so no kind carries provenance `produced`.
    _d("EV", "EV", EXECUTABLE, "events", ak="EVENT",
       category=EVIDENTIAL, provenance=AUTHORED),
    _d("AC", "AC", EXECUTABLE, "actors", ak="ACTOR",
       category=PARTICIPATORY, provenance=AUTHORED),
    # DECLARATIVE — own NodeKind
    _d("ASSERT", "ASSERT", DECLARATIVE, "assertions", ak="ASSERT",
       category=NORMATIVE, provenance=DERIVED),
    _d("TEST_DATA", "TEST_DATA", DECLARATIVE),
    # DECLARATIVE — ride NodeKind.GOVERNANCE, keep their prefix (old _GOVERNANCE_PREFIXES)
    _d("INVARIANT", "GOVERNANCE", DECLARATIVE, "invariants", ak="INVARIANT",
       category=NORMATIVE, provenance=AUTHORED),
    _d("VOCAB", "GOVERNANCE", DECLARATIVE, "vocabulary", ak="VOCABULARY",
       category=DEFINITIONAL, provenance=AUTHORED),
    _d("CONSTITUTION", "GOVERNANCE", DECLARATIVE, "concerns", ak="CONSTITUTION",
       category=NORMATIVE, provenance=AUTHORED),
    _d("SCHEMA", "GOVERNANCE", DECLARATIVE, "schemas"),
    _d("STRUCTURE", "GOVERNANCE", DECLARATIVE, "structures", ak="STRUCTURE",
       category=DEFINITIONAL, provenance=AUTHORED),
    _d("SURFACE", "GOVERNANCE", DECLARATIVE, "surface_contracts", ak="SURFACE_CONTRACT",
       category=CONTRACTUAL, provenance=AUTHORED),
    _d("ENTITY", "GOVERNANCE", DECLARATIVE, "entities", "entities", ak="ENTITY"),
    # DECLARATIVE — ride NodeKind.GOVERNANCE, collapse to "GOVERNANCE" in canonical (not in old prefixes)
    _d("LAYER", "GOVERNANCE", DECLARATIVE, keeps_prefix=False),
    _d("GOVERNANCE", "GOVERNANCE", DECLARATIVE, keeps_prefix=False),
)


class BuiltInArtifactRegistry:
    """The substrate bootstrap registry. Step 4 swaps in a CompiledArtifactRegistry with the same API."""

    def __init__(self, descriptors: tuple[ArtifactKindDescriptor, ...] = _DESCRIPTORS):
        self._by_prefix = {d.prefix: d for d in descriptors}
        # Authoritative index: canonical artifact_kind -> descriptor (Machine Block §6).
        self._by_kind = {d.artifact_kind: d for d in descriptors if d.artifact_kind}

    def descriptor(self, prefix: str) -> ArtifactKindDescriptor | None:
        return self._by_prefix.get(prefix)

    def descriptor_for_kind(self, artifact_kind: str) -> ArtifactKindDescriptor | None:
        """Resolve a descriptor by its canonical `artifact_kind` — the authoritative discriminator."""
        return self._by_kind.get(artifact_kind)

    def node_kind_for_kind(self, artifact_kind: str) -> str | None:
        """NodeKind (string) for a canonical `artifact_kind`; None if the kind is unknown."""
        d = self._by_kind.get(artifact_kind)
        return d.node_kind if d else None

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

    def semantic_category(self, artifact_kind: str) -> str | None:
        """Governance Ontology §4 primary category for a canonical `artifact_kind`."""
        d = self._by_kind.get(artifact_kind)
        return d.semantic_category if d else None

    def provenance(self, artifact_kind: str) -> str | None:
        """Governance Ontology §6 provenance for a canonical `artifact_kind`."""
        d = self._by_kind.get(artifact_kind)
        return d.provenance if d else None

    def runtime_disposition(self, artifact_kind: str) -> str | None:
        """Ontology §7 runtime disposition for a canonical `artifact_kind`."""
        d = self._by_kind.get(artifact_kind)
        return d.runtime_disposition if d else None

    def ontology_coverage(self) -> dict[str, tuple[str | None, str | None]]:
        """Every authorized kind → (category, provenance). Ontology §11 conformance input."""
        return {k: (d.semantic_category, d.provenance) for k, d in sorted(self._by_kind.items())}

    def index_section(self, prefix: str) -> str | None:
        d = self._by_prefix.get(prefix)
        return d.index_section if d else None

    def index_sections(self) -> dict[str, str]:
        """Prefix → kind_index section, for every indexed kind."""
        return {p: d.index_section for p, d in self._by_prefix.items() if d.index_section}

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
