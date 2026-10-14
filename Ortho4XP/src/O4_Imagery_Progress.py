"""What the imagery step says it is doing: downloading imagery, or
reusing the cached imagery (#622).

The owner, 2026-10-12: "progress bars need to identify if imagery is
downloaded or not".  The imagery step queues every texture whose DDS is
not on disk; each queued texture's orthophoto is then either read from
the imagery cache or downloaded (``O4_Imagery_Utils
.note_orthophoto_download`` counts the downloads on the tile).  This
module turns those counts into the step's detail label and measures the
download phase for the time model (``download_seconds``,
``textures_downloaded`` on the tile's build record).

Pure text and arithmetic; no UI import.
"""

from __future__ import annotations

import time

__all__ = ["begin", "label", "download_rate", "finish"]

#: the row's detail for a tile textured with X-Plane's own textures
DEFAULT_TEXTURES = "X-Plane default textures · no imagery to download"


def begin(tile) -> None:
    """The imagery step starts: zero the tile's download counters."""
    tile.imagery_downloads = 0
    tile.imagery_first_download_at = None
    tile.imagery_download_seconds = 0.0


def download_rate(tile, now=None):
    """Orthophotos downloaded per second since the first one, or None."""
    first = getattr(tile, "imagery_first_download_at", None)
    count = getattr(tile, "imagery_downloads", 0)
    if first is None or count < 2:
        return None
    span = (now if now is not None else time.time()) - first
    return count / span if span > 0 else None


def label(tile, finished: int, queued: int, now=None) -> str:
    """The detail for ``finished`` of ``queued`` textures done."""
    downloads = getattr(tile, "imagery_downloads", 0)
    if not queued:
        return "reusing cached imagery"
    if not downloads:
        return "reusing cached imagery · %d of %d textures" % (finished,
                                                                queued)
    text = "downloading imagery · %d of %d textures, %d downloaded" % (
        finished, queued, downloads)
    rate = download_rate(tile, now)
    if rate:
        text += " (%.1f/min)" % (rate * 60.0)
    return text


def finish(tile) -> str:
    """The download phase is over: record its wall seconds on the tile
    and return the detail for the conversion tail."""
    # From the first download to now: the scenery-file render runs
    # alongside and is local work, not download time.
    first = getattr(tile, "imagery_first_download_at", None)
    tile.imagery_download_seconds = (
        max(0.0, time.time() - first) if first is not None else 0.0)
    downloads = getattr(tile, "imagery_downloads", 0)
    if downloads:
        return "converting textures · %d orthophotos downloaded" % downloads
    return "converting textures · cached imagery reused"
