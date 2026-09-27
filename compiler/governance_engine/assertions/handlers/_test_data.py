"""
Shared reading of test vectors for the conformance assertions.

A vector's cases are governed content and live in its Machine block (`SCHEMA_TEST_DATA_V0`): the
transform it tests as `target`, and `cases`. One reading, so every assertion over vectors agrees on
where a case is — three readers once read three formats and none of them agreed.
"""


def vectors(artifacts: list[dict]) -> list[dict]:
    return [a for a in artifacts if a.get("artifact_type") == "TEST_DATA"]


def target(vector: dict) -> str:
    t = vector.get("frontmatter", {}).get("target", "")
    return t if isinstance(t, str) else ""


def cases(vector: dict) -> list[dict]:
    c = vector.get("frontmatter", {}).get("cases", [])
    return [x for x in c if isinstance(x, dict)] if isinstance(c, list) else []
