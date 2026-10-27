"""Imagery downloads while the vector step builds the airport patch (#1002).

The texture SET is mesh-derived, so the imagery step cannot start before
the mesh.  But a tile built before names its textures already: the live
``terrain/*.ter`` files are named after their texture
(``<til_y>_<til_x>_<provider><zoom>[_water|_sea][_overlay].ter``,
``O4_DSF_Utils.create_terrain_file``).  The texture GRID is the zoom
level's and the same for every imagery source, so that list, re-keyed to
the source this build uses, is the best pre-mesh guess at what the
imagery step will download (plan: docs/findings/imagery-prefetch-plan-622.md).

:func:`candidates` derives that list; :func:`alongside` downloads it in
the background for as long as the vector step runs, and stops when the
step ends.  DOWNLOADS ONLY: an orthophoto lands in the imagery cache
exactly where the imagery step looks for it; no conversion runs here
(the DDS conversion needs the colour-harmonization field and the masks).
The imagery step is unchanged: it finds the prefetched orthophotos in the
cache and downloads only the rest, so its download count, its bar share
(#653) and the measured rate count only what IT downloaded.

Bounds: one orthophoto in flight at a time (:data:`TEXTURES_IN_FLIGHT`),
which is one texture's part requests — the same per-provider load one
imagery-step download makes — so the solve keeps the processor.  Stop
(``UI.red_flag``) ends it after the orthophoto in flight; what arrived
stays (orthophotos are cache, not scenery: the #598 stop rule).  Only a
WHOLE orthophoto is kept — a part the provider did not answer leaves no
file, so the imagery step downloads that texture itself.

A first build (no live terrain folder), a changed base zoom, the
``default_xplane`` texture mode and a combined source prefetch nothing.
"""

from __future__ import annotations

import contextlib
import os
import threading
from collections import Counter

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Tile_Staging as STAGING
import O4_UI_Utils as UI

__all__ = ["candidates", "Prefetch", "alongside", "TEXTURES_IN_FLIGHT"]

#: Orthophotos downloaded at once by a prefetch (each is one texture's
#: part requests, at the provider's own ``max_threads``).
TEXTURES_IN_FLIGHT = 1

#: How long the end of the vector step waits for the orthophoto in flight.
#: The prefetch starts nothing new once told to stop; a provider request
#: that outlives this is abandoned to its daemon thread.
STOP_WAIT_SECONDS = 120.0

# A texture's 16x16 grid block must lie within this many degrees of the
# tile for a parsed (provider, zoom) split to be believed.
_TILE_MARGIN_DEGREES = 0.25
_ZOOM_RANGE = range(10, 22)


def _texture_of_terrain_name(file_name, lat, lon):
    """``(til_x, til_y, zoom, provider)`` named by one ``.ter`` file of
    tile ``(lat, lon)``, or None.

    The provider code may end in digits, so the zoom is the one-or-two
    digit split whose texture lies on the tile (a wrong split puts the
    grid block thousands of kilometres away)."""
    if not file_name.endswith(".ter"):
        return None
    stem = file_name[:-4]
    if stem.endswith("_overlay"):
        stem = stem[:-len("_overlay")]
    for suffix in ("_water", "_sea"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    parts = stem.split("_", 2)
    if len(parts) != 3 or not (parts[0].isdigit() and parts[1].isdigit()):
        return None
    til_y, til_x, rest = int(parts[0]), int(parts[1]), parts[2]
    for digits in (2, 1):
        zoom_text, provider = rest[-digits:], rest[:-digits]
        if not provider or not zoom_text.isdigit():
            continue
        zoom = int(zoom_text)
        if zoom not in _ZOOM_RANGE:
            continue
        (centre_lat, centre_lon) = GEO.gtile_to_wgs84(
            til_x + 8, til_y + 8, zoom)
        if (lat - _TILE_MARGIN_DEGREES <= centre_lat
                <= lat + 1 + _TILE_MARGIN_DEGREES
                and lon - _TILE_MARGIN_DEGREES <= centre_lon
                <= lon + 1 + _TILE_MARGIN_DEGREES):
            return (til_x, til_y, zoom, provider)
    return None


def _live_textures(tile):
    """Every texture the tile's live terrain folder names (a set)."""
    folder = os.path.join(tile.build_dir, STAGING.LIVE)
    try:
        names = os.listdir(folder)
    except OSError:
        return set()
    textures = set()
    for name in names:
        texture = _texture_of_terrain_name(name, tile.lat, tile.lon)
        if texture is not None:
            textures.add(texture)
    return textures


def _is_plain_source(provider_code, imagery):
    return (provider_code in imagery.providers_dict
            and provider_code not in imagery.combined_providers_dict
            and provider_code not in imagery.local_combined_providers_dict)


def _orthophoto_path(tile, texture, imagery):
    (til_x, til_y, zoom, provider_code) = texture
    return os.path.join(
        FNAMES.jpeg_file_dir_from_attributes(
            tile.lat, tile.lon, zoom, imagery.providers_dict[provider_code]),
        FNAMES.jpeg_file_name_from_attributes(
            til_x, til_y, zoom, provider_code))


def _texture_is_built(tile, texture):
    return os.path.exists(os.path.join(
        tile.build_dir, "textures",
        FNAMES.dds_file_name_from_attributes(*texture)))


def candidates(tile, imagery=None):
    """The orthophotos this build's imagery step will most likely download.

    The live terrain folder's textures, the previous build's base source
    re-keyed to ``tile.default_website`` (textures of any other source —
    a zone's or an override's — keep theirs), minus the textures whose
    ``.dds`` is already built and the orthophotos already in the imagery
    cache.  Empty when the tile was never built, when its base zoom
    (the most common zoom of the live textures) is not
    ``tile.default_zl``, in the ``default_xplane`` texture mode, or when
    the source is a combined one.  Sorted, never raises on a missing
    folder.  ``imagery`` is the ``O4_Imagery_Utils`` module (twins pass
    a stand-in carrying the three provider dictionaries)."""
    if imagery is None:
        import O4_Imagery_Utils as imagery
    if getattr(tile, "texture_mode", "full_ortho") == "default_xplane":
        return []
    provider = getattr(tile, "default_website", "")
    if not _is_plain_source(provider, imagery):
        return []
    live = _live_textures(tile)
    if not live:
        return []
    zooms = Counter(texture[2] for texture in live)
    base_zoom = zooms.most_common(1)[0][0]
    if base_zoom != int(getattr(tile, "default_zl", 0) or 0):
        return []
    base_source = Counter(
        texture[3] for texture in live if texture[2] == base_zoom
    ).most_common(1)[0][0]
    wanted = set()
    for (til_x, til_y, zoom, source) in live:
        source = provider if source == base_source else source
        if not _is_plain_source(source, imagery):
            continue
        texture = (til_x, til_y, zoom, source)
        if _texture_is_built(tile, texture):
            continue
        if os.path.exists(_orthophoto_path(tile, texture, imagery)):
            continue
        wanted.add(texture)
    return sorted(wanted, key=lambda t: (t[2], t[1], t[0], t[3]))


def download_orthophoto(tile, texture):
    """Download one WHOLE orthophoto into the imagery cache; 1 or 0."""
    import O4_Imagery_Utils as IMG

    path = _orthophoto_path(tile, texture, IMG)
    if os.path.exists(path):
        return 1
    return IMG.download_orthophoto_once(
        os.path.dirname(path), os.path.basename(path), *texture,
        require_complete=True)


class Prefetch:
    """One tile's background orthophoto downloads (see the module)."""

    def __init__(self, tile, textures, fetch=None, on_done=None):
        self.tile = tile
        self.textures = list(textures)
        self.downloaded = 0
        self.failed = 0
        self._fetch = fetch or download_orthophoto
        self._on_done = on_done
        self._stop = threading.Event()
        self._threads = []
        self._lock = threading.Lock()
        self._pending = list(reversed(self.textures))
        self._running = 0

    def start(self):
        """Begin the downloads; with nothing to fetch, report at once."""
        if not self.textures:
            self._finish()
            return self
        UI.vprint(1, "    * Downloading", len(self.textures),
                  "orthophotos the last build of this tile used, while "
                  "the patch builds.")
        workers = max(1, min(TEXTURES_IN_FLIGHT, len(self.textures)))
        self._running = workers
        for _ in range(workers):
            thread = threading.Thread(target=self._work, daemon=True)
            self._threads.append(thread)
            thread.start()
        return self

    def _next(self):
        with self._lock:
            if self._stop.is_set() or UI.red_flag or not self._pending:
                return None
            return self._pending.pop()

    def _work(self):
        try:
            while True:
                texture = self._next()
                if texture is None:
                    break
                try:
                    ok = self._fetch(self.tile, texture)
                except Exception as error:
                    UI.vprint(1, "    Prefetch of", texture, "failed:", error)
                    ok = 0
                with self._lock:
                    if ok:
                        self.downloaded += 1
                    else:
                        self.failed += 1
        finally:
            self._worker_ended()

    def _worker_ended(self):
        with self._lock:
            self._running -= 1
            last = self._running == 0
        if last:
            self._finish()

    def _finish(self):
        """Report once: the queue drained, was stopped or never started."""
        with self._lock:
            callback, self._on_done = self._on_done, None
        if callback is not None:
            try:
                callback(self.downloaded, self.failed)
            except Exception:
                pass

    def stop(self, wait_seconds=STOP_WAIT_SECONDS):
        """Start nothing new; wait for the orthophoto in flight."""
        self._stop.set()
        for thread in self._threads:
            thread.join(wait_seconds)
        if any(thread.is_alive() for thread in self._threads):
            # Abandoned in flight: a report arriving later could be read
            # as another step's signal, and the step's end already
            # returned everything the prefetch held.
            with self._lock:
                self._on_done = None
        if self.textures:
            UI.vprint(1, "    * Prefetched", self.downloaded, "of",
                      len(self.textures), "orthophotos",
                      "(%d failed)." % self.failed if self.failed else ".")
        if not self._threads:
            self._finish()


@contextlib.contextmanager
def alongside(tile, on_done=None, fetch=None, find=candidates):
    """Prefetch the tile's orthophotos for the duration of the block.

    ``on_done(downloaded, failed)`` is called exactly once, when the
    queue drains, the prefetch is stopped, or there is nothing to fetch
    (the parent orchestrator releases the imagery token it lent the
    prefetch there).  Never raises out of the prefetch itself."""
    try:
        textures = find(tile)
    except Exception as error:
        UI.vprint(1, "    Imagery prefetch skipped:", error)
        textures = []
    prefetch = Prefetch(tile, textures, fetch=fetch, on_done=on_done)
    prefetch.start()
    try:
        yield prefetch
    finally:
        prefetch.stop()
