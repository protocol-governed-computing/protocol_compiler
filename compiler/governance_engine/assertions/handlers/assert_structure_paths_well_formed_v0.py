"""
ASSERT_STRUCTURE_PATHS_WELL_FORMED_V0 Handler

STRUCTURE artifacts are the sole authority for where things live. Checks:

  1. no path value is absolute
  2. no path value escapes its layer via ".."
  3. every path-valued key carries a non-empty string
  4. every referenced layer code resolves to a declaration

Rule 4 is cross-artifact — layers are declared in the discovery master or in a build
manifest's own layer_definitions, and referenced from elsewhere — which is why this is a
handler rather than a per-artifact schema constraint.
"""

from typing import Any

RULE = "fb.topology::INVARIANT_STRUCTURE_PATHS_WELL_FORMED_V0"

# Keys whose value is a path in its own right (as opposed to a value that merely
# contains a slash, e.g. a description).
PATH_KEYS = frozenset({"path", "base_path", "subpath", "root", "registry_module"})


def _is_path_key(key: str) -> bool:
    return key in PATH_KEYS or key.endswith("_path") or key.endswith("_dir")


def _walk(data: Any, path: str = ""):
    """Yield (dotted_path, key, value) for every scalar in the tree."""
    if isinstance(data, dict):
        for k, v in data.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                yield from _walk(v, here)
            else:
                yield here, str(k), v
    elif isinstance(data, list):
        for i, item in enumerate(data):
            here = f"{path}[{i}]"
            if isinstance(item, (dict, list)):
                yield from _walk(item, here)
            else:
                yield here, path.rsplit(".", 1)[-1], item


def _declared_layers(structures: list[dict]) -> set[str]:
    declared: set[str] = set()
    for s in structures:
        fm = s.get("frontmatter", {}) or {}
        layers = (fm.get("discovery", {}) or {}).get("layers")
        if isinstance(layers, dict):
            declared.update(layers)
        own = fm.get("layer_definitions")
        if isinstance(own, dict):
            declared.update(own)
    return declared


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []
    structures = [a for a in artifacts if a.get("artifact_type") == "STRUCTURE"]

    def flag(fqdn: str, message: str, fix: str) -> None:
        violations.append({"fqdn": fqdn, "rule": RULE, "message": message, "fix": fix})

    for s in structures:
        fqdn = s.get("fqdn_id", "unknown")
        fm = s.get("frontmatter", {}) or {}

        for dotted, key, value in _walk(fm):
            if not _is_path_key(key):
                # Rules 1 and 2 still apply to any value that is a path in substance.
                if isinstance(value, str) and "/" in value and not value.startswith("http"):
                    if value.startswith("/"):
                        flag(fqdn, f"absolute path at '{dotted}': {value}",
                             "Express the path relative to its declared layer")
                    if ".." in value.split("/"):
                        flag(fqdn, f"layer escape at '{dotted}': {value}",
                             "Remove the '..' segment; paths may not escape their layer")
                continue

            if value is None or (isinstance(value, str) and not value.strip()):
                flag(fqdn, f"path-valued key '{dotted}' is empty",
                     "Declare the path explicitly; an absent path is an implicit default")
                continue
            if isinstance(value, str):
                if value.startswith("/"):
                    flag(fqdn, f"absolute path at '{dotted}': {value}",
                         "Express the path relative to its declared layer")
                if ".." in value.split("/"):
                    flag(fqdn, f"layer escape at '{dotted}': {value}",
                         "Remove the '..' segment; paths may not escape their layer")

    # --- Rule 4: referenced layers resolve to a declaration ---
    declared = _declared_layers(structures)
    if declared:
        for s in structures:
            fqdn = s.get("fqdn_id", "unknown")
            fm = s.get("frontmatter", {}) or {}
            referenced: set[str] = set()
            disc = fm.get("artifact_discovery", {}) or {}
            referenced.update(disc.get("search_layers") or [])
            outputs = (fm.get("output_configuration", {}) or {}).get("layer_outputs")
            if isinstance(outputs, dict):
                referenced.update(outputs)
            for _dotted, key, value in _walk(fm):
                if key == "layer" and isinstance(value, str):
                    referenced.add(value)
            for layer in sorted(referenced - declared):
                flag(fqdn, f"references undeclared layer '{layer}'",
                     "Declare it in discovery.layers or in this manifest's layer_definitions")

    return {
        "assert_count": len(structures),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
