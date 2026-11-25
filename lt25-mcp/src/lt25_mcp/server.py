"""stdio MCP server for a Fender Mustang LT25.

Run with the amp plugged in over USB and the Fender Tone app closed:

    python -m lt25_mcp
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lt25_mcp.preset import TONE_GUIDE
from lt25_mcp.session import AmpSession

mcp = FastMCP("lt25", instructions=TONE_GUIDE)
session = AmpSession()


@mcp.tool()
def connect() -> dict:
    """Open the LT25 USB HID link, sync, and start the one-second heartbeat.

    Close the Fender Tone desktop app before calling this. Both programs
    need the same HID device.
    """
    return session.connect()


@mcp.tool()
def disconnect() -> dict:
    """Stop the heartbeat and release the USB HID device."""
    return session.disconnect()


@mcp.tool()
def status() -> dict:
    """Report whether the amp session and heartbeat are running."""
    return session.status()


@mcp.tool()
def list_presets(start: int = 1, end: int = 30) -> list[dict]:
    """Summarize saved preset slots. Slots are 1-60. Default reads 1-30.

    Each item includes the display name and the FenderId of every DSP node.
    Copy those ids when building a new tone. Empty or unread slots include
    an error field instead of a name.
    """
    return session.list_presets(start, end)


@mcp.tool()
def get_preset(slot: int) -> dict:
    """Return the full preset JSON for one slot (1-60), plus a short summary."""
    return session.get_preset(slot)


@mcp.tool()
def load_preset(slot: int) -> dict:
    """Load a saved preset slot (1-60) on the amp."""
    return session.load_preset(slot)


@mcp.tool()
def current_preset() -> dict:
    """Read the preset the amp is currently playing."""
    return session.current_preset()


@mcp.tool()
def audition_tone(preset_json: str) -> dict:
    """Temporarily play a preset JSON string without writing a saved slot.

    Build the JSON from a preset returned by get_preset. Keep nodes named
    stomp, mod, amp, delay, and reverb. Set bypass true on unused effects.
    displayName must be 16 characters or fewer. Missing connections are
    filled with the standard preset -> stomp -> mod -> amp -> delay ->
    reverb -> preset chain.
    """
    return session.audition_tone(preset_json)


@mcp.tool()
def exit_audition() -> dict:
    """Leave the temporary audition and return to the loaded preset slot."""
    return session.exit_audition()


@mcp.tool()
def set_usb_gain(db: float) -> dict:
    """Set the USB recording gain in decibels, from -15.0 to 15.0."""
    return session.set_usb_gain(db)


@mcp.resource("lt25://tone-guide")
def tone_guide() -> str:
    """How to turn a plain-English tone request into LT25 preset JSON."""
    return TONE_GUIDE


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
