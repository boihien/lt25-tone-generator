"""USB session for one Mustang LT amplifier.

ltamp does not keep the link alive by itself. The amp drops the session
unless it receives a heartbeat about once a second, so this session owns
that loop and serializes HID calls around it.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from lt25_mcp.preset import (
    SLOT_MAX,
    SLOT_MIN,
    prepare_preset,
    summarize_preset,
    unwrap_retrieved,
)

AmpFactory = Callable[[], Any]


def _default_amp() -> Any:
    from ltamp import LtAmp

    return LtAmp()


class AmpSession:
    def __init__(
        self,
        amp_factory: AmpFactory | None = None,
        heartbeat_interval: float = 1.0,
    ) -> None:
        self._factory = amp_factory or _default_amp
        self._heartbeat_interval = heartbeat_interval
        self._amp: Any | None = None
        self._lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self.firmware: str | None = None

    @property
    def connected(self) -> bool:
        return self._amp is not None

    def connect(self) -> dict[str, Any]:
        with self._lock:
            if self._amp is not None:
                return {
                    "connected": True,
                    "alreadyConnected": True,
                    "firmware": self.firmware,
                }
            amp = self._factory()
            try:
                amp.connect()
                amp.send_sync_begin()
                amp.send_sync_end()
            except Exception:
                try:
                    amp.disconnect()
                except Exception:
                    pass
                raise
            self._amp = amp
            self._heartbeat_stop.clear()
            try:
                self.firmware = amp.request_firmware_version()
            except Exception as exc:
                self.firmware = None
                firmware_error = str(exc)
            else:
                firmware_error = None
        self._start_heartbeat()
        result: dict[str, Any] = {"connected": True, "firmware": self.firmware}
        if firmware_error:
            result["firmwareError"] = firmware_error
        return result

    def disconnect(self) -> dict[str, Any]:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self._lock:
            amp = self._amp
            self._amp = None
            self._heartbeat_thread = None
            if amp is not None:
                amp.disconnect()
        return {"connected": False}

    def status(self) -> dict[str, Any]:
        thread = self._heartbeat_thread
        return {
            "connected": self.connected,
            "firmware": self.firmware,
            "heartbeat": bool(thread and thread.is_alive()),
        }

    def list_presets(self, start: int = SLOT_MIN, end: int = SLOT_MAX) -> list[dict[str, Any]]:
        self._check_range(start, end)
        results: list[dict[str, Any]] = []
        for slot in range(start, end + 1):
            try:
                with self._lock:
                    amp = self._require()
                    raw = amp.retrieve_preset(slot)
            except Exception as exc:
                results.append({"slot": slot, "error": str(exc)})
                continue
            reported_slot, payload = unwrap_retrieved(raw)
            results.append(
                {
                    "slot": reported_slot if reported_slot is not None else slot,
                    **summarize_preset(payload),
                }
            )
        return results

    def get_preset(self, slot: int) -> dict[str, Any]:
        self._check_slot(slot)
        with self._lock:
            amp = self._require()
            raw = amp.retrieve_preset(slot)
        reported_slot, payload = unwrap_retrieved(raw)
        if isinstance(payload, str):
            import json

            try:
                body: Any = json.loads(payload)
            except json.JSONDecodeError:
                body = payload
        else:
            body = payload
        return {
            "slot": reported_slot if reported_slot is not None else slot,
            "preset": body,
            "summary": summarize_preset(payload),
        }

    def load_preset(self, slot: int) -> dict[str, Any]:
        self._check_slot(slot)
        with self._lock:
            amp = self._require()
            amp.set_preset(slot)
        return {"loaded": slot}

    def current_preset(self) -> dict[str, Any]:
        with self._lock:
            amp = self._require()
            raw = amp.request_current_preset()
        reported_slot, payload = unwrap_retrieved(raw)
        return {
            "slot": reported_slot,
            "preset": payload,
            "summary": summarize_preset(payload),
        }

    def audition_tone(self, preset_json: str | dict[str, Any]) -> dict[str, Any]:
        encoded = prepare_preset(preset_json)
        with self._lock:
            amp = self._require()
            amp.audition_preset(encoded)
        return {"auditioning": True, "summary": summarize_preset(encoded)}

    def exit_audition(self) -> dict[str, Any]:
        with self._lock:
            amp = self._require()
            amp.exit_audition()
        return {"auditioning": False}

    def set_usb_gain(self, db: float) -> dict[str, Any]:
        gain = float(db)
        if not -15.0 <= gain <= 15.0:
            raise ValueError("USB gain must be between -15.0 and 15.0 dB.")
        with self._lock:
            amp = self._require()
            amp.set_usb_gain(gain)
        return {"usbGainDb": gain}

    def _require(self) -> Any:
        if self._amp is None:
            raise RuntimeError("Amp is not connected. Call connect first, with Fender Tone closed.")
        return self._amp

    def _start_heartbeat(self) -> None:
        thread = threading.Thread(target=self._heartbeat_loop, name="lt25-heartbeat", daemon=True)
        self._heartbeat_thread = thread
        thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_interval):
            with self._lock:
                amp = self._amp
                if amp is None:
                    return
                try:
                    amp.send_heartbeat()
                except Exception:
                    continue

    @staticmethod
    def _check_slot(slot: int) -> None:
        if not isinstance(slot, int) or isinstance(slot, bool) or not SLOT_MIN <= slot <= SLOT_MAX:
            raise ValueError(f"Preset slot must be an integer from {SLOT_MIN} to {SLOT_MAX}.")

    @classmethod
    def _check_range(cls, start: int, end: int) -> None:
        cls._check_slot(start)
        cls._check_slot(end)
        if start > end:
            raise ValueError("Preset range start must be less than or equal to end.")
