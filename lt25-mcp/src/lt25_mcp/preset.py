"""Preset JSON helpers for Mustang LT audition payloads.

The amp stores each tone as JSON. The signal chain is fixed in factory
presets: preset -> stomp -> mod -> amp -> delay -> reverb -> preset.
FenderId values come from presets already on the amp. Copy them with
get_preset instead of inventing ids.
"""

from __future__ import annotations

import json
from typing import Any

SLOT_MIN = 1
SLOT_MAX = 60
DISPLAY_NAME_MAX = 16

NODE_ORDER = ("stomp", "mod", "amp", "delay", "reverb")

# Published example from the maneline LT JSON notes. Use these only as
# shapes. Real ids on a given amp should be copied from retrieve_preset.
EXAMPLE_FENDER_IDS = {
    "stomp": "DUBS_Overdrive",
    "mod": "DUBS_Vibratone",
    "amp": "DUBS_Deluxe57",
    "delay": "DUBS_ReverseDelay",
    "reverb": "DUBS_SmallRoomReverb",
}

TONE_GUIDE = """
Build Mustang LT25 tones as preset JSON and send them with audition_tone.
Audition is temporary. This server does not save over the amp's 60 slots.

Workflow:
1. connect. Close the Fender Tone desktop app first. It holds the same USB HID device.
2. get_preset on a factory slot (1-30 are usually filled) and copy its FenderId values.
3. Edit dspUnitParameters. Keep the five nodes: stomp, mod, amp, delay, reverb.
4. Bypass an effect you do not want with dspUnitParameters.bypass = true.
5. audition_tone with the JSON. exit_audition returns to the slot that was loaded.
6. displayName is at most 16 characters. The amp shows it as two lines of 8.

Chain: preset -> stomp -> mod -> amp -> delay -> reverb -> preset.
Parameter values are floats, ints, bools, or strings already used by that model.
Do not invent FenderId strings. Copy them from a retrieved preset.
USB gain is decibels from -15.0 to 15.0.
""".strip()


def standard_connections() -> list[dict[str, Any]]:
    chain = ("preset", *NODE_ORDER, "preset")
    connections = []
    for source, dest in zip(chain, chain[1:]):
        for index in (0, 1):
            connections.append(
                {
                    "input": {"nodeId": source, "index": index},
                    "output": {"nodeId": dest, "index": index},
                }
            )
    return connections


def parse_preset(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Preset is not valid JSON: {exc}") from exc
    elif isinstance(payload, dict):
        parsed = payload
    else:
        raise ValueError("Preset must be a JSON object or a JSON string.")
    if not isinstance(parsed, dict):
        raise ValueError("Preset JSON must be an object.")
    return parsed


def prepare_preset(payload: str | dict[str, Any]) -> str:
    """Validate a tone and return the compact JSON string the amp expects."""
    preset = parse_preset(payload)
    preset.setdefault("nodeType", "preset")
    preset.setdefault("nodeId", "preset")
    preset.setdefault("version", "1.1")
    preset.setdefault("numInputs", 2)
    preset.setdefault("numOutputs", 2)

    if preset.get("nodeId") != "preset" or preset.get("nodeType") != "preset":
        raise ValueError('Preset nodeId and nodeType must both be "preset".')

    info = preset.get("info")
    if not isinstance(info, dict):
        raise ValueError("Preset info must be an object.")
    name = info.get("displayName", "")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("info.displayName is required.")
    if len(name) > DISPLAY_NAME_MAX:
        raise ValueError(
            f"info.displayName must be at most {DISPLAY_NAME_MAX} characters."
        )
    info.setdefault("product_id", "mustang-lt")
    info.setdefault("bpm", 0)

    graph = preset.get("audioGraph")
    if not isinstance(graph, dict):
        raise ValueError("audioGraph is required.")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("audioGraph.nodes must list the DSP units.")

    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Each audioGraph node must be an object.")
        node_id = node.get("nodeId")
        if node_id not in NODE_ORDER:
            raise ValueError(
                f"Unknown nodeId {node_id!r}. Expected one of {', '.join(NODE_ORDER)}."
            )
        if node_id in seen:
            raise ValueError(f"Duplicate nodeId {node_id!r}.")
        seen.add(node_id)
        fender_id = node.get("FenderId")
        if not isinstance(fender_id, str) or not fender_id.strip():
            raise ValueError(f"Node {node_id} needs a FenderId copied from the amp.")
        if not isinstance(node.get("dspUnitParameters"), dict):
            raise ValueError(f"Node {node_id} needs a dspUnitParameters object.")
        node.setdefault("nodeType", "dspUnit")

    missing = [node_id for node_id in NODE_ORDER if node_id not in seen]
    if missing:
        raise ValueError(
            "Preset is missing nodes: " + ", ".join(missing) + ". Bypass unused effects instead of omitting them."
        )

    if not graph.get("connections"):
        graph["connections"] = standard_connections()

    return json.dumps(preset, separators=(",", ":"))


def summarize_preset(payload: str | dict[str, Any] | None) -> dict[str, Any]:
    if payload is None or payload == "":
        return {"displayName": None, "nodes": []}
    try:
        preset = parse_preset(payload)
    except ValueError as exc:
        return {"displayName": None, "nodes": [], "error": str(exc)}

    info = preset.get("info") if isinstance(preset.get("info"), dict) else {}
    graph = preset.get("audioGraph") if isinstance(preset.get("audioGraph"), dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    summary_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        params = node.get("dspUnitParameters")
        params = params if isinstance(params, dict) else {}
        summary_nodes.append(
            {
                "nodeId": node.get("nodeId"),
                "fenderId": node.get("FenderId"),
                "bypass": params.get("bypass"),
            }
        )
    return {
        "displayName": info.get("displayName"),
        "bpm": info.get("bpm"),
        "nodes": summary_nodes,
    }


def unwrap_retrieved(raw: Any) -> tuple[int | None, str | dict[str, Any] | None]:
    """Normalize ltamp retrieve/current-preset results to (slot, payload)."""
    if isinstance(raw, dict) and "data" in raw:
        index = raw.get("index")
        slot = int(index) if isinstance(index, int) else None
        return slot, raw.get("data")
    if isinstance(raw, str):
        return None, raw
    return None, None
