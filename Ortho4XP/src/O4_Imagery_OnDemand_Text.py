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

__all__ = ["PIN_TITLE", "UNPIN_TITLE", "FAVORITE_TITLE",
           "PINNED_STATE", "PINNED_BADGE", "PIN_HELP", "STAR_ADD_HELP",
           "STAR_REMOVE_HELP", "star_help", "MAKE_LOW_RES_TITLE",
           "MAKE_LOW_RES_NONE", "PINS_LINE", "CORES_LINE", "OLDER_SHARP_NOTE",
           "FOLLOW_START_TITLE", "FOLLOW_STOP_TITLE", "FOLLOW_TEMPLATES",
           "FOLLOW_DETAIL", "WAITING_REASON", "FOLLOW_NO_TILES",
           "RELOAD_SCENERY_TITLE", "RELOAD_OFFER_IMAGERY", "RELOAD_OFFER_TILES",
           "RELOAD_OFFER_COVERAGE",
           "make_low_res_message", "reload_offer_line",
           "pins_line", "pin_done", "follow_lines", "follow_headline",
           "size_text"]

# --- Favorites (spec §7: the Library's tile menu, the star beside the tile
# pane's title and on the Build map's built cells, #2033; "pin" renamed
# Favorite by RULINGS 2026-11-10c (1); the identifiers and the engine wire
# keep "pin" / ``pinned``).  A Favorite is STORAGE PRIORITY (owner
# 2026-11-13T01:45Z): any built tile, set any time, a build running or
# not; its sharp imagery is the last made low-res when storage is tight.
PIN_TITLE = "Add to Favorites"
UNPIN_TITLE = "Remove from Favorites"
#: The star's accessible name.
FAVORITE_TITLE = "Favorite"
PINNED_STATE = "Favorite: its sharp imagery is kept longest"
#: After a favorite tile's name in the Library.
PINNED_BADGE = "Favorite"
PIN_HELP = ("A favorite tile keeps its sharp imagery longest: when storage "
            "is tight, its high-resolution imagery is the last made "
            "low-res again.")
#: The star's tooltip, outlined (not a favorite) and filled (one).
STAR_ADD_HELP = ("Make this tile a favorite: its sharp imagery is the last "
                 "made low-res when storage is tight.")
STAR_REMOVE_HELP = ("A favorite: its sharp imagery is the last made low-res "
                    "when storage is tight. Click to remove it from "
                    "Favorites.")


def star_help(pinned: bool) -> str:
    """The star's tooltip for a tile that is (or is not) a favorite."""
    return STAR_REMOVE_HELP if pinned else STAR_ADD_HELP


# --- Storage (spec §6.3 / §7: the ondemand row and its pins line) ---
MAKE_LOW_RES_TITLE = "Make all low-res again"
MAKE_LOW_RES_NONE = "No sharp imagery to make low-res again."
PINS_LINE = "Favorites: {bytes} in {files} texture(s), made low-res last"
#: The row's airport cores (spec §6.1): counted, made low-res last.
CORES_LINE = "{files} of them near airports, made low-res last"
#: Added to "Clear cache files not used for…" when the sweep reaches the
#: sharp imagery: it is made low-res again, never deleted.
OLDER_SHARP_NOTE = ("Sharp imagery near flown areas is made low-res again, "
                    "not deleted, and fetched again when you fly near; "
                    "favorites are kept.")

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
                 "{reloads} reload offers")
WAITING_REASON = "its Web API is not answering"
#: The reload offer under the follow line (#2019, owner 2026-11-12T14:34Z:
#: "Never ask x-plane to reload unless the user requests it."): the line
#: per ``ImageryFollowStatus.reload_offer`` code, and the button that
#: sends ``scenery_reload``.  Swift: ``O4OnDemandText.reloadOffer*``.
RELOAD_SCENERY_TITLE = "Reload scenery"
RELOAD_OFFER_IMAGERY = ("Sharper imagery landed after X-Plane loaded this "
                        "area: reload the scenery to see it.")
RELOAD_OFFER_TILES = ("New tiles replaced ones X-Plane had already loaded: "
                      "reload the scenery to see them.")
RELOAD_OFFER_COVERAGE = ("The World pack now covers more of the world: "
                         "reload the scenery (or restart X-Plane) once so "
                         "X-Plane can use it.")
#: The first sentence while the job follows (or waits) with no on-demand
#: texture in its index: nothing it could sharpen.
FOLLOW_NO_TILES = ("No on-demand tiles to follow yet: build a tile with "
                   "imagery on demand, or convert one in the Library")
#: The states whose first sentence that replaces.
NO_TILES_STATES = ("waiting", "following")
XPLANE_ANSWERING = "answering"
XPLANE_SILENT = "not answering"
BUFFER_NONE = "nothing queued"
BUFFER_AHEAD = "{seconds} s ahead"
#: Metres per second to knots.
KNOTS_PER_MS = 1.943844


def size_text(nbytes) -> str:
    """``12.3 MB`` / ``1.25 GB`` (decimal), the same in both apps."""
    value = float(nbytes or 0)
    if value >= 1e9:
        return "%.2f GB" % (value / 1e9)
    return "%.1f MB" % (value / 1e6)


def make_low_res_message(freed_bytes, textures: int) -> str:
    """The "Make all low-res again" confirmation: the space it frees."""
    return ("This makes %d sharp texture(s) low-res again and frees %s. "
            "They are fetched again when you fly near; favorites are "
            "kept." % (int(textures), size_text(freed_bytes)))


def pins_line(pinned_bytes, pinned_files: int, core_files: int = 0) -> str:
    """The Storage row's extra lines: the airport cores among the counted
    textures (when any), then the favorites, inside the ortho budget."""
    pins = PINS_LINE.format(bytes=size_text(pinned_bytes),
                            files=int(pinned_files))
    if not core_files:
        return pins
    return CORES_LINE.format(files=int(core_files)) + "\n" + pins


def pin_done(result: Mapping) -> str:
    """One sentence for an ``imagery_pin`` reply."""
    tile = result.get("tile", "The tile")
    if not result.get("pinned"):
        return "%s is no longer a favorite." % tile
    served, to_fetch = (int(result.get("served", 0) or 0),
                        int(result.get("to_fetch", 0) or 0))
    if not served and not to_fetch:
        return "%s is a favorite." % tile
    return ("%s is a favorite: %d texture(s) sharp now, %d to fetch."
            % (tile, served, to_fetch))


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
        "bytes_landed": size_text(num("bytes_landed")),
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
    if state in NO_TILES_STATES and values["textures"] == "0":
        template = FOLLOW_NO_TILES
    return template.format(**values), FOLLOW_DETAIL.format(**values)


def follow_headline(status, running: bool) -> str:
    """The line's headline beside the Follow / Stop button (``running``):
    the status's own while the two agree; else -- before the job's first
    status, or a stale one -- "Starting..." or "Not following", so the
    line never reads "Not following X-Plane" beside "Stop Following"
    (#2028).  Swift: ``O4OnDemandText.followHeadline``."""
    if status:
        state = str(status.get("state") or "starting")
        if (state not in ("stopped", "error")) == bool(running):
            return follow_lines(status)[0]
    return FOLLOW_TEMPLATES["starting" if running else "stopped"]


def reload_offer_line(code: str) -> str:
    """The reload offer's line for an ``ImageryFollowStatus.reload_offer``
    code; empty when none is pending (the row is hidden)."""
    return {"imagery": RELOAD_OFFER_IMAGERY, "tiles": RELOAD_OFFER_TILES,
            "coverage": RELOAD_OFFER_COVERAGE}.get(code or "", "")
