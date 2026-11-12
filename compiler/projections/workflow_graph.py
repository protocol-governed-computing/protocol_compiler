"""
workflow_graph.py — the behaviour-logic projection: one execution graph per compiled workflow.

Each workflow is written as `behavior_logic/<WF>/<WF>.graph.json`: its nodes, the routes between
them, the capability each contract binds, and every execution path from the start node to an
ending. The runtime correlates traces with it, and the inspector and the clients draw from it.

The graph is data. Drawing it is a consumer's act: the inspector's workflow page draws it in the
browser. A picture rendered here would make the snapshot depend on whichever renderer the build
machine happened to have, and every file written here is a sealed constituent of the snapshot.
"""

import json
from pathlib import Path
from typing import Any


def build_graph(wf_artifact: dict[str, Any], cc_artifacts: dict[str, Any]) -> dict[str, Any]:
    """The execution graph a workflow declares, with each contract node's capability binding."""
    wf_code = wf_artifact.get("artifact_code")
    core = wf_artifact.get("frontmatter", {}).get("core", {})
    start_node = core.get("start_node")
    nodes_spec = core.get("nodes", {})

    nodes = []
    for node_id, node_spec in nodes_spec.items():
        node_type = node_spec.get("type")
        node: dict[str, Any] = {"id": node_id, "type": node_type}

        if node_type == "CC":
            cc_code = node_spec.get("code")
            if cc_code:
                node["cc_code"] = cc_code
                cc_artifact = cc_artifacts.get(cc_code, {})
                pipeline = cc_artifact.get("frontmatter", {}).get("core", {}).get("pipeline", [])
                # The first step's capability labels the node.
                if pipeline:
                    capability_fqdn = pipeline[0].get("transform") or pipeline[0].get("side_effect")
                    if capability_fqdn:
                        node["capability"] = capability_fqdn
                        if "::CT_" in capability_fqdn or capability_fqdn.startswith("CT_"):
                            node["capability_type"] = "CT"
                        elif "::CS_" in capability_fqdn or capability_fqdn.startswith("CS_"):
                            node["capability_type"] = "CS"
                cc_projection = cc_artifact.get("cc_projection")
                if cc_projection:
                    node["projection"] = cc_projection

            # The workflow's input bindings, as structural references, so data flow into a node
            # reads beside its routes.
            wf_inputs = node_spec.get("inputs")
            if wf_inputs:
                node["input_bindings"] = {
                    "type": "wf_boundary",
                    "bindings": {k: _normalize_binding(v) for k, v in wf_inputs.items()},
                }

        nodes.append(node)

    edges = [
        {"from": node_id, "to": target_id, "condition": condition}
        for node_id, node_spec in nodes_spec.items()
        for condition, target_id in node_spec.get("next", {}).items()
    ]

    return {
        "wf_id": wf_code,
        "entry": start_node,
        "nodes": nodes,
        "edges": edges,
        "execution_paths": _extract_paths(start_node, nodes_spec),
    }


def write_graph(graph: dict[str, Any], behavior_logic_root: Path) -> Path:
    """Write one workflow's graph under the behaviour-logic root; return the path written."""
    wf_dir = behavior_logic_root / graph["wf_id"]
    wf_dir.mkdir(parents=True, exist_ok=True)
    path = wf_dir / f"{graph['wf_id']}.graph.json"
    with open(path, "w") as f:
        json.dump(graph, f, indent=2)
    return path


def _normalize_binding(value: Any) -> Any:
    """A binding as a structural reference: `$.payload.f` → `IN.f`, `$.results.N.f` → `N.f`.

    A literal, or any value that is not a string, is unchanged.
    """
    if not isinstance(value, str):
        return value
    if value.startswith("$.payload."):
        return "IN." + value[len("$.payload."):]
    if value.startswith("$.results."):
        return value[len("$.results."):]
    return value


def _extract_paths(start_node: str, nodes_spec: dict[str, Any]) -> list[list[str]]:
    """Every path from the start node to an ending, by depth-first search; a cycle is not re-entered."""
    paths: list[list[str]] = []
    visited: set[str] = set()

    def dfs(node_id: str, path: list[str]) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        path = path + [node_id]
        node_spec = nodes_spec.get(node_id, {})
        if node_spec.get("type") == "EXIT" or not node_spec.get("next"):
            paths.append(path)
        else:
            for target_id in node_spec.get("next", {}).values():
                dfs(target_id, path)
        visited.remove(node_id)

    dfs(start_node, [])
    return paths
