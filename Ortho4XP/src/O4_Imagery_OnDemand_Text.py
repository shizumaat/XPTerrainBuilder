"""The words of imagery on demand in both apps (#1992 spec §7, P4).

The Qt window (``O4_Qt_Imagery_OnDemand``, ``O4_Qt_Library``,
``O4_Qt_Settings_Storage``) reads them here; the Mac app's mirror is
``Sources/SceneryKit/ImageryOnDemandText.swift`` (``O4OnDemandText``),
and ``tests/test_imagery_ondemand_ui.py`` requires the two to say the
same.  The follow status line is a TEMPLATE per job state plus one detail
template; both apps fill the ``{field}`` slots with the same number
formats (:func:`_follow_values`), so every ``ImageryFollowStatus`` field
is shown, worded once.

Pure: no Qt, no engine session.
"""
from __future__ import annotations

from typing import Mapping, Tuple

__all__ = ["PIN_TITLE", "UNPIN_TITLE", "PIN_ROW_TITLE", "LOW_RES_STATE",
           "PINNED_STATE", "PINNED_BADGE", "PIN_HELP", "MAKE_LOW_RES_TITLE",
           "MAKE_LOW_RES_NONE", "PINS_LINE", "CORES_LINE", "OLDER_SHARP_NOTE",
           "FOLLOW_START_TITLE", "FOLLOW_STOP_TITLE", "FOLLOW_TEMPLATES",
           "FOLLOW_DETAIL", "WAITING_REASON", "make_low_res_message",
           "pins_line", "pin_done", "follow_lines"]

# --- Pins (spec §7: the Library's tile menu and the tile's info pane) ---
PIN_TITLE = "Always keep full resolution"
UNPIN_TITLE = "Let it go low-res again"
PIN_ROW_TITLE = "Resolution"
LOW_RES_STATE = "Sharp near the aircraft, low-res elsewhere"
PINNED_STATE = "Always full resolution (pinned)"
#: After a pinned tile's name in the Library.
PINNED_BADGE = "Pinned"
PIN_HELP = ("A pinned tile is fetched whole at full resolution, is never "
            "made low-res again and does not count against the storage "
            "limit.")

# --- Storage (spec §6.3 / §7: the ondemand row and its pins line) ---
MAKE_LOW_RES_TITLE = "Make all low-res again"
MAKE_LOW_RES_NONE = "No sharp imagery to make low-res again."
PINS_LINE = "Pinned tiles: {bytes} in {files} texture(s), never made low-res"
#: The row's airport cores (spec §6.1): counted, made low-res last.
CORES_LINE = "{files} of them near airports, made low-res last"
#: Added to "Clear cache files not used for…" when the sweep reaches the
#: sharp imagery: it is made low-res again, never deleted.
OLDER_SHARP_NOTE = ("Sharp imagery near flown areas is made low-res again, "
                    "not deleted, and fetched again when you fly near; "
                    "pinned tiles are kept.")

# --- The follow status line (spec §7: the activity area) ---
FOLLOW_START_TITLE = "Follow X-Plane"
FOLLOW_STOP_TITLE = "Stop Following"
#: ``ImageryFollowStatus.state`` -> the line's first sentence.
FOLLOW_TEMPLATES = {
    "starting": "Starting to follow X-Plane…",
    "waiting": "Waiting for X-Plane: {reason}",
    "following": ("Following X-Plane: {sharp} of {textures} sharp nearby, "
                  "{in_flight} downloading, {late} late"),
    "paused": "Imagery paused: {reason}",
    "stopped": "Not following X-Plane",
    "error": "Following stopped: {reason}",
}
#: The line's second sentence, every other field of the event.
FOLLOW_DETAIL = ("{queued} queued · {slots} at a time · {buffer} · "
                 "{landed} landed ({bytes_landed}) · {failed} failed · "
                 "X-Plane {xplane} at {lat}, {lon}, {speed} kt, "
                 "track {track}° · {flight_loads} flight loads · {jumps} jumps · "
                 "{reloads} reloads")
WAITING_REASON = "its Web API is not answering"
XPLANE_ANSWERING = "answering"
XPLANE_SILENT = "not answering"
BUFFER_NONE = "nothing queued"
BUFFER_AHEAD = "{seconds} s ahead"
#: Metres per second to knots.
KNOTS_PER_MS = 1.943844


def _size_text(nbytes) -> str:
    """``12.3 MB`` / ``1.25 GB`` (decimal), the same in both apps."""
    value = float(nbytes or 0)
    if value >= 1e9:
        return "%.2f GB" % (value / 1e9)
    return "%.1f MB" % (value / 1e6)


def make_low_res_message(freed_bytes, textures: int) -> str:
    """The "Make all low-res again" confirmation: the space it frees."""
    return ("This makes %d sharp texture(s) low-res again and frees %s. "
            "They are fetched again when you fly near; pinned tiles are "
            "kept." % (int(textures), _size_text(freed_bytes)))


def pins_line(pinned_bytes, pinned_files: int, core_files: int = 0) -> str:
    """The Storage row's extra lines: the airport cores among the counted
    textures (when any), then the pins, outside the cap."""
    pins = PINS_LINE.format(bytes=_size_text(pinned_bytes),
                            files=int(pinned_files))
    if not core_files:
        return pins
    return CORES_LINE.format(files=int(core_files)) + "\n" + pins


def pin_done(result: Mapping) -> str:
    """One sentence for an ``imagery_pin`` reply."""
    if not result.get("pinned"):
        return "%s may go low-res again." % result.get("tile", "The tile")
    return ("%s is pinned: %d texture(s) sharp now, %d to fetch."
            % (result.get("tile", "The tile"), int(result.get("served", 0)),
               int(result.get("to_fetch", 0))))


def _follow_values(status: Mapping) -> dict:
    """The template slots of one ``ImageryFollowStatus`` (its fields as
    the event's JSON keys), formatted as both apps show them."""
    def num(key):
        try:
            return float(status.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    buffer_s = status.get("buffer_s")
    buffer_s = -1.0 if buffer_s is None else float(buffer_s)
    return {
        "reason": str(status.get("reason") or "") or WAITING_REASON,
        "sharp": "%d" % num("sharp"), "textures": "%d" % num("textures"),
        "in_flight": "%d" % num("in_flight"), "late": "%d" % num("late"),
        "queued": "%d" % num("queued"), "slots": "%d" % max(1, num("slots")),
        "buffer": (BUFFER_NONE if buffer_s < 0
                   else BUFFER_AHEAD.format(seconds="%.0f" % buffer_s)),
        "landed": "%d" % num("landed"),
        "bytes_landed": _size_text(num("bytes_landed")),
        "failed": "%d" % num("failed"),
        "xplane": XPLANE_ANSWERING if status.get("xplane") else XPLANE_SILENT,
        "lat": "%.3f" % num("lat"), "lon": "%.3f" % num("lon"),
        "speed": "%.0f" % (num("speed_ms") * KNOTS_PER_MS),
        "track": "%.0f" % num("track_deg"),
        "flight_loads": "%d" % num("flight_loads"),
        "jumps": "%d" % num("jumps"),
        "reloads": "%d" % num("reloads"),
    }


def follow_lines(status: Mapping) -> Tuple[str, str]:
    """``(headline, detail)`` of the status line for one event."""
    values = _follow_values(status)
    state = str(status.get("state") or "starting")
    template = FOLLOW_TEMPLATES.get(state, FOLLOW_TEMPLATES["starting"])
    return template.format(**values), FOLLOW_DETAIL.format(**values)
