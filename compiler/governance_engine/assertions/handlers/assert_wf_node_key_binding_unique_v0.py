"""
ASSERT_WF_NODE_KEY_BINDING_UNIQUE_V0 Handler

Enforces INVARIANT_WF_NODE_KEY_BINDING_UNIQUE_V0 at compile time.

Validates that within every WF, when the same CC fqdn_id is used more than once,
each usage declares distinct inputs — making each binding context uniquely
addressable by node_key. This is the source-level check that makes dispatch
binding fidelity contractually verifiable.

Rule: two CC nodes in the same WF may share a fqdn_id ONLY IF their input
bindings differ. Identical fqdn_id + identical inputs = indistinguishable
binding contexts = dispatch collapse = violation.

This exposes the invariant to future compiler implementations: node_key is
the mandatory binding discriminator; CC address is not a valid binding key.
"""

import json
from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify WF node_key binding uniqueness across shared CC fqdn_id usages.

    Args:
        artifacts:           All validated artifacts from the graph.
        compilation_context: Compilation context including wf_execution_graphs.

    Returns:
        {"assert_count": int, "violations": list[dict], "status": str}
    """
    violations = []
    wf_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_count += 1
        wf_fqdn = artifact.get("fqdn_id", "unknown")
        core = artifact.get("frontmatter", {}).get("core", {})
        if not isinstance(core, dict):
            continue

        nodes_dict = core.get("nodes", {})
        if not isinstance(nodes_dict, dict):
            continue

        # For each CC fqdn_id used in this WF, collect all (node_key, inputs_fingerprint) pairs.
        # If two node_keys share the same fqdn_id and the same inputs fingerprint,
        # they are indistinguishable under address-based keying — binding collapse violation.
        fqdn_binding_contexts: dict[str, list[tuple[str, str]]] = {}

        for node_key, node_data in nodes_dict.items():
            if not isinstance(node_data, dict):
                continue
            if node_data.get("type") != "CC":
                continue

            fqdn_id = node_data.get("fqdn_id", "")
            if not fqdn_id:
                continue

            raw_inputs = node_data.get("inputs")
            if not isinstance(raw_inputs, dict) or not raw_inputs:
                continue  # No inputs declared — no binding context to collapse

            # Stable fingerprint of inputs for collision detection
            inputs_fingerprint = json.dumps(raw_inputs, sort_keys=True)

            if fqdn_id not in fqdn_binding_contexts:
                fqdn_binding_contexts[fqdn_id] = []
            fqdn_binding_contexts[fqdn_id].append((node_key, inputs_fingerprint))

        # Check for collisions: same fqdn_id + same inputs fingerprint = indistinguishable
        for fqdn_id, usages in fqdn_binding_contexts.items():
            if len(usages) < 2:
                continue  # Only one usage — no collision possible

            seen_fingerprints: dict[str, str] = {}  # fingerprint → node_key
            for node_key, fingerprint in usages:
                if fingerprint in seen_fingerprints:
                    first_nk = seen_fingerprints[fingerprint]
                    violations.append({
                        "fqdn": wf_fqdn,
                        "rule": "workflow::INVARIANT_WF_NODE_KEY_BINDING_UNIQUE_V0",
                        "message": (
                            f"WF '{wf_fqdn}' uses CC '{fqdn_id}' in two nodes "
                            f"('{first_nk}' and '{node_key}') with identical inputs. "
                            f"Under address-based binding keying these are indistinguishable. "
                            f"Either give each node distinct inputs or merge into a single node."
                        ),
                        "fix": (
                            f"Differentiate the inputs for '{first_nk}' vs '{node_key}', "
                            f"or remove one of the duplicate CC usages."
                        ),
                    })
                else:
                    seen_fingerprints[fingerprint] = node_key

    return {
        "assert_count": wf_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
