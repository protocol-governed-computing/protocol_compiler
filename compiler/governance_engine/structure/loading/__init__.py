"""
structure.loading — Protocol artifact loading runtime

This package provides all runtime functionality for loading protocol artifacts:
- Filesystem reading (fs_reader)
- Protocol orchestration (protocol_loader)
- Trace loading (trace_reader)
- Test case loading (test_case_provider)
- Markdown parsing (markdown_parser)
- YAML parsing (yaml_parser)
- Vocabulary loading (vocabulary_loader)

ARCHITECTURAL BOUNDARY:
- Structure layer: Provides runtime loading/parsing (this package)
- Governance layer: Uses structure for loading, adds validation/schemas
- Builder/Authoring: Uses structure for artifact discovery
- Execution: Uses structure for protocol loading

No component should implement file I/O or parsing outside this package.
"""

from compiler.governance_engine.structure.loading.fs_reader import ProtocolFSReader
from compiler.governance_engine.structure.loading.protocol_loader import ProtocolLoader
from compiler.governance_engine.structure.loading.trace_reader import (
    TraceLoadError,
    load_trace,
    load_trace_safe,
)
from compiler.governance_engine.structure.loading.test_case_provider import (
    TestCase,
    TestCaseLoadError,
    load_test_cases,
    load_test_cases_safe,
)
from compiler.governance_engine.structure.loading.markdown_parser import (
    MarkdownParseError,
    extract_yaml_block,
    extract_yaml_block_from_file,
    extract_frontmatter,
    split_frontmatter_and_body,
)
from compiler.governance_engine.structure.loading.yaml_parser import (
    YAMLParseError,
    parse_yaml_simple,
    parse_yaml_to_dict,
    extract_metadata,
    extract_categories,
)
from compiler.governance_engine.structure.loading.vocabulary_loader import (
    VocabularyCategory,
    VocabularyEntry,
    VocabularyLoadResult,
    load_vocabulary_md,
    load_vocabulary_md_from_path,
)

__all__ = [
    # Existing
    "ProtocolFSReader",
    "ProtocolLoader",
    # Trace loading
    "TraceLoadError",
    "load_trace",
    "load_trace_safe",
    # Test case loading
    "TestCase",
    "TestCaseLoadError",
    "load_test_cases",
    "load_test_cases_safe",
    # Markdown parsing
    "MarkdownParseError",
    "extract_yaml_block",
    "extract_yaml_block_from_file",
    "extract_frontmatter",
    "split_frontmatter_and_body",
    # YAML parsing
    "YAMLParseError",
    "parse_yaml_simple",
    "parse_yaml_to_dict",
    "extract_metadata",
    "extract_categories",
    # Vocabulary loading
    "VocabularyCategory",
    "VocabularyEntry",
    "VocabularyLoadResult",
    "load_vocabulary_md",
    "load_vocabulary_md_from_path",
]
