"""
vocabulary_loader.py — Vocabulary file loading (structure runtime)

This module provides runtime vocabulary file loading.
Governance layer uses this for vocabulary building and validation.

ARCHITECTURAL BOUNDARY:
- Structure: Implements vocabulary file loading (this file)
- Governance: Defines vocabulary schemas and validation rules

Moved from registry/vocabulary/builder/reserved.py to establish clean separation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Callable

from compiler.governance_engine.structure.loading.markdown_parser import extract_yaml_block
from compiler.governance_engine.structure.loading.yaml_parser import parse_yaml_simple


# Type alias for file reader
FileReader = Callable[[Path], str]


@dataclass(frozen=True)
class VocabularyCategory:
    """
    A vocabulary category with casing and entries.

    Used for: node_types, artifact_kinds, result_status, etc.
    """
    casing: str  # "UPPER_SNAKE" or "lower_snake"
    entries: list[str]


@dataclass(frozen=True)
class VocabularyEntry:
    """
    A vocabulary entry loaded from a .md file.

    Contains metadata and category definitions.
    """
    vocab_id: str
    version: str
    governed_by: str
    categories: Dict[str, VocabularyCategory]

    def get_entries(self, category: str) -> set[str]:
        """Get entries for a category as a set."""
        cat = self.categories.get(category)
        if cat:
            return set(cat.entries)
        return set()


@dataclass(frozen=True)
class VocabularyLoadResult:
    """
    Result of loading a vocabulary .md file with active and deprecated entries.

    Contains:
    - entry: Main vocabulary entry with active terms
    - deprecated_categories: Categories containing deprecated terms
    """
    entry: VocabularyEntry
    deprecated_categories: Dict[str, VocabularyCategory]


def load_vocabulary_md(path: Path, read_file: FileReader) -> VocabularyLoadResult:
    """
    Load a vocabulary .md file and parse its YAML Machine section.

    Vocabulary file format:
    ```markdown
    # Vocabulary Title

    Human-readable description...

    ## Machine

    ```yaml
    vocab_id: VOCAB_EXAMPLE_V0
    version: 1
    governed_by: CONSTITUTION_VOCABULARY_V0

    category_name:
      casing: UPPER_SNAKE
      entries:
        - ENTRY_ONE
        - ENTRY_TWO
      deprecated:
        - OLD_ENTRY
    ```
    ```

    Args:
        path: Path to vocabulary .md file.
        read_file: File reader function.

    Returns:
        VocabularyLoadResult with active entry and deprecated categories.

    Raises:
        ValueError: If file is missing, malformed, or missing required fields.
    """
    if not path.exists():
        raise ValueError(f"Missing vocabulary file: {path}")

    content = read_file(path)
    yaml_text = extract_yaml_block(content, section="Machine")
    parsed = parse_yaml_simple(yaml_text)

    # Extract metadata
    vocab_id = parsed.get("vocab_id")
    version = parsed.get("version")
    governed_by = parsed.get("governed_by")

    if not vocab_id:
        raise ValueError(f"Missing vocab_id in {path}")
    if not version:
        raise ValueError(f"Missing version in {path}")
    if not governed_by:
        raise ValueError(f"Missing governed_by in {path}")

    # Extract categories (everything except metadata keys)
    metadata_keys = {"vocab_id", "version", "governed_by"}
    categories: Dict[str, VocabularyCategory] = {}
    deprecated_categories: Dict[str, VocabularyCategory] = {}

    for key, value in parsed.items():
        if key in metadata_keys:
            continue
        if isinstance(value, dict):
            casing = value.get("casing", "UPPER_SNAKE")
            entries = value.get("entries", [])
            deprecated = value.get("deprecated", [])

            categories[key] = VocabularyCategory(casing=casing, entries=entries)

            if deprecated:
                deprecated_categories[key] = VocabularyCategory(casing=casing, entries=deprecated)

    entry = VocabularyEntry(
        vocab_id=vocab_id,
        version=version,
        governed_by=governed_by,
        categories=categories,
    )

    return VocabularyLoadResult(entry=entry, deprecated_categories=deprecated_categories)


def load_vocabulary_md_from_path(path: Path) -> VocabularyLoadResult:
    """
    Load vocabulary .md file using standard file reading.

    Convenience function that doesn't require a file reader callback.

    Args:
        path: Path to vocabulary .md file.

    Returns:
        VocabularyLoadResult with active and deprecated terms.

    Raises:
        ValueError: If file missing, malformed, or invalid.
    """
    def default_reader(p: Path) -> str:
        return p.read_text(encoding="utf-8")

    return load_vocabulary_md(path, default_reader)
