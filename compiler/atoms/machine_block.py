"""
The machine block of a protocol artifact: the YAML under its `## Machine` heading.

A declaration's prose may carry YAML of its own, as an example or as a picture of what a rule
realizes, and a machine block may carry backticks inside a value. A reader that takes the first
fenced block, or stops at the first fence, reads the wrong YAML for such an artifact. Every
compiler reader takes the block this one rule finds, so they cannot disagree.

`transformation.machine_block` states the same rule for the transformation compilers, which may
not import the compiler; `.github/process/frontmatter_fidelity.py` checks the two agree.
"""

import re

MACHINE_BLOCK = re.compile(r"^## Machine\s*\n+```yaml\s*\n(?P<machine_yaml>.*?)\n```", re.MULTILINE | re.DOTALL)


def machine_yaml(text: str) -> str | None:
    """The YAML source of a document's machine block, or None where it has none."""
    found = MACHINE_BLOCK.search(text)
    return found.group("machine_yaml") if found else None
