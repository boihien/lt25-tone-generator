import json

import pytest

from lt25_mcp.preset import prepare_preset, summarize_preset

MINIMAL = {
    "info": {"displayName": "Edge Deluxe"},
    "audioGraph": {
        "nodes": [
            {
                "nodeId": "stomp",
                "FenderId": "DUBS_Overdrive",
                "dspUnitParameters": {"bypass": True, "bypassType": "Post"},
            },
            {
                "nodeId": "mod",
                "FenderId": "DUBS_Vibratone",
                "dspUnitParameters": {"bypass": True, "bypassType": "Post"},
            },
            {
                "nodeId": "amp",
                "FenderId": "DUBS_Deluxe57",
                "dspUnitParameters": {"gain": 0.4, "bass": 0.5, "mid": 0.5, "treb": 0.6},
            },
            {
                "nodeId": "delay",
                "FenderId": "DUBS_ReverseDelay",
                "dspUnitParameters": {"bypass": True, "bypassType": "Pre"},
            },
            {
                "nodeId": "reverb",
                "FenderId": "DUBS_SmallRoomReverb",
                "dspUnitParameters": {"bypass": False, "level": 0.3},
            },
        ]
    },
}


def test_prepare_fills_chain_and_identity():
    encoded = prepare_preset(MINIMAL)
    preset = json.loads(encoded)
    assert preset["nodeId"] == "preset"
    assert preset["info"]["product_id"] == "mustang-lt"
    assert len(preset["audioGraph"]["connections"]) == 12
    assert preset["audioGraph"]["nodes"][2]["FenderId"] == "DUBS_Deluxe57"


def test_prepare_rejects_long_name_and_missing_node():
    broken = json.loads(json.dumps(MINIMAL))
    broken["info"]["displayName"] = "this name is too long"
    with pytest.raises(ValueError, match="16"):
        prepare_preset(broken)

    broken = json.loads(json.dumps(MINIMAL))
    broken["audioGraph"]["nodes"] = broken["audioGraph"]["nodes"][:4]
    with pytest.raises(ValueError, match="reverb"):
        prepare_preset(broken)


def test_summarize_reads_nodes():
    summary = summarize_preset(json.dumps(MINIMAL))
    assert summary["displayName"] == "Edge Deluxe"
    assert summary["nodes"][0]["bypass"] is True
    assert summary["nodes"][2]["fenderId"] == "DUBS_Deluxe57"
