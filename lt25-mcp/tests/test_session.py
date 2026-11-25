import json
import time

import pytest

from lt25_mcp.preset import prepare_preset
from lt25_mcp.session import AmpSession
from tests.test_preset import MINIMAL


class FakeAmp:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.heartbeats = 0
        self.fail_connect = False
        self.closed = False

    def connect(self) -> None:
        self.calls.append("connect")
        if self.fail_connect:
            raise RuntimeError("LT amp not found")

    def disconnect(self) -> None:
        self.calls.append("disconnect")
        self.closed = True

    def send_sync_begin(self) -> None:
        self.calls.append("sync_begin")

    def send_sync_end(self) -> None:
        self.calls.append("sync_end")

    def send_heartbeat(self) -> None:
        self.heartbeats += 1

    def request_firmware_version(self) -> str:
        return "2.1.4"

    def retrieve_preset(self, slot: int) -> dict:
        if slot == 2:
            raise TimeoutError("empty")
        body = json.loads(json.dumps(MINIMAL))
        body["info"]["displayName"] = f"Slot{slot}"
        return {"data": json.dumps(body), "index": slot}

    def set_preset(self, slot: int) -> None:
        self.calls.append(("load", slot))

    def request_current_preset(self) -> dict:
        return {"data": json.dumps(MINIMAL), "index": 4}

    def audition_preset(self, preset_json: str) -> None:
        self.calls.append(("audition", preset_json))

    def exit_audition(self) -> None:
        self.calls.append("exit")

    def set_usb_gain(self, gain: float) -> None:
        if not isinstance(gain, float):
            raise ValueError("gain must be float")
        self.calls.append(("gain", gain))


def _session(**kwargs) -> tuple[AmpSession, FakeAmp]:
    amp = FakeAmp()
    session = AmpSession(amp_factory=lambda: amp, heartbeat_interval=0.05, **kwargs)
    return session, amp


def test_connect_syncs_and_heartbeats():
    session, amp = _session()
    result = session.connect()
    assert result["firmware"] == "2.1.4"
    assert amp.calls[:3] == ["connect", "sync_begin", "sync_end"]
    time.sleep(0.2)
    assert amp.heartbeats >= 1
    session.disconnect()
    assert amp.closed
    assert session.status()["connected"] is False


def test_connect_failure_releases_device():
    session, amp = _session()
    amp.fail_connect = True
    with pytest.raises(RuntimeError, match="not found"):
        session.connect()
    assert amp.closed
    assert session.connected is False


def test_list_and_audition():
    session, amp = _session()
    session.connect()
    listed = session.list_presets(1, 2)
    assert listed[0]["displayName"] == "Slot1"
    assert listed[1]["error"] == "empty"

    tone = json.dumps(MINIMAL)
    audition = session.audition_tone(tone)
    assert audition["summary"]["displayName"] == "Edge Deluxe"
    sent = next(call for call in amp.calls if isinstance(call, tuple) and call[0] == "audition")
    assert json.loads(sent[1])["info"]["product_id"] == "mustang-lt"

    session.load_preset(7)
    assert ("load", 7) in amp.calls
    assert session.current_preset()["slot"] == 4
    session.set_usb_gain(1)
    assert ("gain", 1.0) in amp.calls
    session.exit_audition()
    session.disconnect()


def test_rejects_bad_slot_and_gain_before_touching_amp():
    session, amp = _session()
    session.connect()
    with pytest.raises(ValueError, match="1 to 60"):
        session.load_preset(0)
    with pytest.raises(ValueError, match="-15.0"):
        session.set_usb_gain(20)
    session.disconnect()
    assert ("load", 0) not in amp.calls


def test_tools_require_a_connection():
    session, _amp = _session()
    with pytest.raises(RuntimeError, match="connect"):
        session.audition_tone(prepare_preset(MINIMAL))
