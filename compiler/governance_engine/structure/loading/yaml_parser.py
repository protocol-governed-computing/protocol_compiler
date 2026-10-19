"""
yaml_parser.py — Simple YAML parsing (structure runtime)

This module provides simple YAML parsing without external dependencies.
Handles the specific YAML structures used in PGS registry artifacts.

ARCHITECTURAL BOUNDARY:
- Structure: Implements YAML parsing (this file)
- Governance: Defines YAML schemas and validation rules

Moved from registry/vocabulary/builder/reserved.py to establish clean separation.

NOTE: This is a SIMPLE parser for the specific YAML format used in vocabulary
files. It does NOT handle full YAML spec. For complex YAML, use PyYAML.
"""

from __future__ import annotations

from typing import Dict, List, Any


class YAMLParseError(ValueError):
    """Raised when YAML parsing fails."""
    pass


def parse_yaml_simple(yaml_text: str) -> Dict[str, Any]:
    """
    Parse simple YAML structure without external dependencies.

    Handles the specific vocabulary YAML format used in PGS:
    - Top-level keys with scalar values
    - Category blocks with casing, entries list, and deprecated list
    - Two-space indentation

    LIMITATIONS:
    - Only handles subset of YAML used in vocabulary files
    - Does not handle: aliases, anchors, complex nesting, multiline strings
    - For complex YAML, use PyYAML instead

    Format handled:
    ```yaml
    vocabulary_id: VOCAB_EXAMPLE_V0
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

    Args:
        yaml_text: YAML content as string.

    Returns:
        Parsed YAML as nested dict.

    Raises:
        YAMLParseError: If YAML structure is invalid or unsupported.
    """
    result: Dict[str, Any] = {}
    current_key: str | None = None
    current_block: Dict[str, Any] | None = None
    current_list: List[str] | None = None
    current_list_key: str | None = None
    indent_stack: List[int] = [0]

    lines = yaml_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Calculate indentation
        indent = len(line) - len(stripped)

        # Check for list item
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if current_list is not None:
                current_list.append(value)
            else:
                raise YAMLParseError(f"List item outside of list context: {line}")
            i += 1
            continue

        # Check for key-value pair
        if ":" in stripped:
            key_part, _, value_part = stripped.partition(":")
            key = key_part.strip()
            value = value_part.strip()

            if value:
                # Simple key: value
                if current_block is not None and indent > 0:
                    # Inside a block, add to current block
                    current_block[key] = value
                else:
                    # Top-level scalar
                    result[key] = value
            else:
                # Key with nested content
                if indent == 0:
                    # Top-level category block
                    current_key = key
                    current_block = {}
                    current_list = None
                    result[key] = current_block
                    indent_stack = [0]
                elif indent > 0 and current_block is not None:
                    # Nested key inside a block
                    if key in ("entries", "deprecated"):
                        # Start a list within the current block
                        current_list = []
                        current_block[key] = current_list
                    else:
                        # Some other nested key - ignore for now
                        pass
                else:
                    # Unexpected structure
                    raise YAMLParseError(f"Unexpected key at indent {indent}: {line}")

        i += 1

    return result


def parse_yaml_to_dict(yaml_text: str) -> Dict[str, Any]:
    """
    Parse YAML to dict, alias for parse_yaml_simple.

    Provided for API consistency with other parsers.

    Args:
        yaml_text: YAML content as string.

    Returns:
        Parsed YAML as dict.

    Raises:
        YAMLParseError: If parsing fails.
    """
    return parse_yaml_simple(yaml_text)


def extract_metadata(parsed: Dict[str, Any], required_keys: List[str]) -> Dict[str, str]:
    """
    Extract metadata fields from parsed YAML.

    Args:
        parsed: Parsed YAML dict.
        required_keys: List of required metadata keys.

    Returns:
        Dict of metadata key-value pairs.

    Raises:
        YAMLParseError: If any required key is missing.
    """
    metadata: Dict[str, str] = {}

    for key in required_keys:
        value = parsed.get(key)
        if not value:
            raise YAMLParseError(f"Missing required metadata key: {key}")
        metadata[key] = value

    return metadata


def extract_categories(
    parsed: Dict[str, Any],
    exclude_keys: set[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract category blocks from parsed YAML.

    Category blocks are nested dicts that are not in the exclude list.
    Typically excludes metadata keys like vocabulary_id, version, etc.

    Args:
        parsed: Parsed YAML dict.
        exclude_keys: Set of keys to exclude (metadata keys).

    Returns:
        Dict of category_name -> category_data.
    """
    if exclude_keys is None:
        exclude_keys = set()

    categories: Dict[str, Dict[str, Any]] = {}

    for key, value in parsed.items():
        if key in exclude_keys:
            continue
        if isinstance(value, dict):
            categories[key] = value

    return categories
