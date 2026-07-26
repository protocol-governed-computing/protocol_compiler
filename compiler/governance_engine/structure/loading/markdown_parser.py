"""
markdown_parser.py — Markdown parsing utilities (structure runtime)

This module provides runtime markdown parsing for protocol artifacts.
Governance layer uses this for vocabulary loading and artifact parsing.

ARCHITECTURAL BOUNDARY:
- Structure: Implements markdown/YAML extraction (this file)
- Governance: Defines vocabulary schemas and validation rules

Moved from registry/vocabulary/builder/reserved.py to establish clean separation.
"""

from __future__ import annotations

import re
from pathlib import Path


class MarkdownParseError(ValueError):
    """Raised when markdown parsing fails."""
    pass


def extract_yaml_block(content: str, section: str = "Machine") -> str:
    """
    Extract YAML content from a markdown file section.

    Looks for a section header (e.g., "## Machine") and extracts the
    ```yaml ... ``` code block that follows it.

    This is used for vocabulary files, constitution files, and other
    registry artifacts that embed machine-readable YAML in markdown.

    Args:
        content: Full markdown file content.
        section: Section header to find (default: "Machine").

    Returns:
        YAML content as string (without ```yaml markers).

    Raises:
        MarkdownParseError: If section or YAML block not found.

    Example:
        # Document Title

        Human-readable description...

        ## Machine

        ```yaml
        vocabulary_id: VOCAB_EXAMPLE_V0
        version: 1
        ```

        → Returns: "vocabulary_id: VOCAB_EXAMPLE_V0\nversion: 1\n"
    """
    # Find the section header
    section_pattern = rf"^## {re.escape(section)}\s*$"
    section_match = re.search(section_pattern, content, re.MULTILINE)

    if not section_match:
        raise MarkdownParseError(f"Missing '## {section}' section in markdown")

    after_section = content[section_match.end():]

    # Find the YAML code block
    yaml_match = re.search(r"```yaml\s*\n(.*?)```", after_section, re.DOTALL)

    if not yaml_match:
        raise MarkdownParseError(f"Missing ```yaml block in '{section}' section")

    return yaml_match.group(1)


def extract_yaml_block_from_file(path: Path, section: str = "Machine") -> str:
    """
    Extract YAML block from a markdown file.

    Convenience function that reads file and extracts YAML in one call.

    Args:
        path: Path to markdown file.
        section: Section header to find (default: "Machine").

    Returns:
        YAML content as string.

    Raises:
        MarkdownParseError: If file not found, section missing, or YAML block missing.
    """
    if not path.exists():
        raise MarkdownParseError(f"Markdown file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        raise MarkdownParseError(f"Failed to read {path}: {e}") from e

    return extract_yaml_block(content, section)


def extract_frontmatter(content: str) -> str | None:
    """
    Extract YAML frontmatter from markdown (if present).

    Frontmatter format:
    ---
    key: value
    ---

    Markdown content...

    Args:
        content: Full markdown content.

    Returns:
        YAML frontmatter as string (without --- markers), or None if no frontmatter.
    """
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

    if frontmatter_match:
        return frontmatter_match.group(1)

    return None


def split_frontmatter_and_body(content: str) -> tuple[str | None, str]:
    """
    Split markdown into frontmatter and body.

    Args:
        content: Full markdown content.

    Returns:
        Tuple of (frontmatter, body).
        - frontmatter: YAML string or None if no frontmatter
        - body: Remaining markdown content
    """
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        body = content[frontmatter_match.end():]
        return frontmatter, body

    return None, content
