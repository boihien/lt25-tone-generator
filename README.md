# LT25 MCP server

Plain-English tone control for a Fender Mustang LT25. This is a stdio MCP server. It talks to the amp over USB HID through [`ltamp`](https://pypi.org/project/ltamp/), which is tested against the LT25.

The amp is not MIDI. Close the Fender Tone desktop app before connecting. Tone and this server both need the same HID device. A heartbeat runs once a second for as long as the session is open.

`audition_tone` plays a preset without writing one of the 60 saved slots. Saving back to a slot is not implemented in `ltamp` yet.

## Setup

From this directory, on Python 3.10+:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest
```

The project MCP config at `.cursor/mcp.json` launches `.venv\Scripts\python.exe`. Create the venv before enabling the server in Cursor. Plug in the LT25 with a USB data cable.

## Tools

| Tool | Purpose |
| --- | --- |
| `connect` | Open HID, send sync, start the heartbeat |
| `disconnect` | Stop the heartbeat and release USB |
| `status` | Session and heartbeat state |
| `list_presets` | Names and FenderIds for a slot range (default 1–30) |
| `get_preset` | Full JSON for one slot |
| `load_preset` | Recall a saved slot |
| `current_preset` | Whatever the amp is playing |
| `audition_tone` | Play generated preset JSON temporarily |
| `exit_audition` | Leave the temporary tone |
| `set_usb_gain` | USB record level, −15 dB to +15 dB |

To make a tone, call `get_preset` on a factory slot and copy its `FenderId` values. Edit `dspUnitParameters`, set `bypass` on effects you do not want, and pass the JSON to `audition_tone`. `displayName` is at most 16 characters. The server fills the standard chain if `connections` is omitted:

`preset → stomp → mod → amp → delay → reverb → preset`

The `lt25://tone-guide` resource repeats those rules for the model.
