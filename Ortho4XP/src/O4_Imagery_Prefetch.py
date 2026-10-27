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

THE AIRPORT'S OWN PHOTOS COME FIRST (#1359; owner RULINGS 2026-10-26y:
"the patch waits for the airport's own photos, so the same inputs always
give the same patch").  :func:`airport_textures` names, before the mesh,
the textures this build will texture each airport with —
``O4_DSF_Utils.zone_list_to_ortho_dico``'s own assignment (base zoom,
custom zones, the airport cover zoom) over the airport's boundary plus
:data:`AIRPORT_MARGIN_M` — and :func:`fetch_airport_imagery` downloads the
missing ones SYNCHRONOUSLY before the patches build, so the terrain
witness reads the same pixels on every build of the same inputs.  These
are textures the imagery step downloads anyway: the work is moved earlier,
never added.  The background prefetch puts the highest zoom (the airport
cover) first and shares one download lock with it.
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

__all__ = ["candidates", "Prefetch", "alongside", "TEXTURES_IN_FLIGHT",
           "airport_textures", "fetch_airport_imagery", "cached_airport_imagery",
           "AIRPORT_MARGIN_M"]

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

#: The witness reads the imagery this far beyond an airport's boundary (a
#: runway's safety area and its graded band run past the boundary).
AIRPORT_MARGIN_M = 500.0

#: One download at a time per orthophoto, shared by the background prefetch
#: and the airport fetch the patch waits for (two writers of one file).
_DOWNLOAD_LOCKS: dict = {}
_DOWNLOAD_LOCKS_GUARD = threading.Lock()


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
    # the highest zoom first: the airport cover textures (#1359, 26y)
    return sorted(wanted, key=lambda t: (-t[2], t[1], t[0], t[3]))


def download_orthophoto(tile, texture):
    """Download one WHOLE orthophoto into the imagery cache; 1 or 0."""
    import O4_Imagery_Utils as IMG

    path = _orthophoto_path(tile, texture, IMG)
    with _DOWNLOAD_LOCKS_GUARD:
        lock = _DOWNLOAD_LOCKS.setdefault(path, threading.Lock())
    with lock:
        if os.path.exists(path):
            return 1
        return IMG.download_orthophoto_once(
            os.path.dirname(path), os.path.basename(path), *texture,
            require_complete=True)


def airport_textures(tile, dico_airports, imagery=None, ortho_dico=None):
    """``{airport: [texture]}``: the plain-source textures this build will
    texture each airport (and :data:`AIRPORT_MARGIN_M` around its
    boundary) with, sorted; ``{}`` in the ``default_xplane`` texture mode.
    The assignment is ``O4_DSF_Utils.zone_list_to_ortho_dico``'s (a twin
    passes ``ortho_dico``, its ``{(til_x, til_y): texture}`` at
    ``tile.mesh_zl``); a combined source's texture is left out (its mask
    layer is not one photo: the witness abstains there)."""
    if getattr(tile, "texture_mode", "full_ortho") == "default_xplane":
        return {}
    if imagery is None:
        import O4_Imagery_Utils as imagery
    if ortho_dico is None:
        import O4_DSF_Utils as DSF
        ortho_dico = DSF.zone_list_to_ortho_dico(tile)
    zl = int(tile.mesh_zl)
    out = {}
    for name, entry in (dico_airports or {}).items():
        boundary = entry.get("boundary") if isinstance(entry, dict) else None
        if boundary is None or boundary.is_empty:
            continue
        xmin, ymin, xmax, ymax = boundary.bounds
        dlat = AIRPORT_MARGIN_M * GEO.m_to_lat
        dlon = AIRPORT_MARGIN_M * GEO.m_to_lon(tile.lat)
        (x0, y0) = GEO.wgs84_to_orthogrid(tile.lat + ymax + dlat, tile.lon + xmin - dlon, zl)
        (x1, y1) = GEO.wgs84_to_orthogrid(tile.lat + ymin - dlat, tile.lon + xmax + dlon, zl)
        found = set()
        for til_x in range(x0, x1 + 1, 16):
            for til_y in range(y0, y1 + 1, 16):
                texture = ortho_dico.get((til_x, til_y))
                if texture is not None and _is_plain_source(texture[3], imagery):
                    found.add(tuple(texture))
        if found:
            out[name] = sorted(found, key=lambda t: (-t[2], t[1], t[0], t[3]))
    return out


def fetch_airport_imagery(tile, dico_airports, fetch=None, find=airport_textures,
                          download=True):
    """THE PATCH WAITS FOR THE AIRPORT'S OWN PHOTOS (26y): download every
    missing texture of :func:`airport_textures` now, one at a time, and
    return ``{airport: (orthophoto path, ...)}`` of those in the cache
    afterwards.  A texture whose download fails is left out (the witness
    abstains there, and the patch's ``o4_imagery`` stamp says so).  Stop
    (``UI.red_flag``) ends it; never raises.

    DOWNLOADS ONLY UNDER AN IMAGERY TOKEN: the session calls it with
    ``download=True`` only through :meth:`Prefetch.fetch_airports` (the
    token its parent lent the vector step's prefetch); otherwise
    ``download=False`` reads the cache and fetches nothing."""
    try:
        wanted = find(tile, dico_airports)
    except Exception as error:
        UI.vprint(1, "    Airport imagery skipped:", error)
        return {}
    if not wanted:
        return {}
    import O4_Imagery_Utils as IMG
    fetch = fetch or download_orthophoto
    textures = sorted({t for ts in wanted.values() for t in ts},
                      key=lambda t: (-t[2], t[1], t[0], t[3]))
    missing = [t for t in textures
               if not os.path.exists(_orthophoto_path(tile, t, IMG))] if download else []
    if missing:
        UI.vprint(1, "    * Downloading", len(missing), "orthophotos of the "
                  "airports first: the patches are fitted to them.")
    for texture in missing:
        if UI.red_flag:
            break
        try:
            fetch(tile, texture)
        except Exception as error:
            UI.vprint(1, "    Airport orthophoto", texture, "failed:", error)
    out = {}
    for name, ts in wanted.items():
        paths = tuple(p for p in (_orthophoto_path(tile, t, IMG) for t in ts)
                      if os.path.exists(p))
        if paths:
            out[name] = paths
    return out


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
        # #1359 (26y): the vector step's airport fetch rides this token, so
        # the report (which hands the token back) waits for the queue to
        # drain AND for the airport fetch, or for the step's end (stop)
        self._drained = False
        self._airports_pending = True
        # one orthophoto in flight under the token, the airport fetch's
        # included (:data:`TEXTURES_IN_FLIGHT`)
        self._in_flight = threading.Lock()

    def start(self):
        """Begin the downloads; with nothing to fetch, the queue is drained
        at once (the report still waits for the airport fetch)."""
        if not self.textures:
            self._drained = True
            self._maybe_finish()
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
                    with self._in_flight:
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
                self._drained = True
        if last:
            self._maybe_finish()

    def _maybe_finish(self):
        """Report once the queue has drained and the airport fetch ran."""
        with self._lock:
            ready = self._drained and not self._airports_pending
        if ready:
            self._finish()

    def fetch_airports(self, dico_airports, find=airport_textures):
        """The vector step's airport fetch (26y) UNDER THIS PREFETCH'S
        TOKEN: :func:`fetch_airport_imagery` with this prefetch's fetcher,
        its downloads counted in the report; then the report may go."""
        def counted(tile, texture):
            with self._in_flight:
                ok = self._fetch(tile, texture)
            with self._lock:
                if ok:
                    self.downloaded += 1
                else:
                    self.failed += 1
            return ok
        try:
            return fetch_airport_imagery(self.tile, dico_airports, fetch=counted, find=find)
        finally:
            with self._lock:
                self._airports_pending = False
            self._maybe_finish()

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
        with self._lock:
            self._airports_pending = False       # the step ended: no fetch comes
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
        if not self._threads or self._drained:
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


def cached_airport_imagery(tile, icao):
    """The airport's photo paths ALREADY in the cache (no download): the
    tile's saved airports dictionary (``FNAMES.apt_file``) read through
    :func:`airport_textures` — the patch editor's staleness check reads
    the same ``o4_imagery`` input the build stamped.  ``()`` when the tile
    has no saved dictionary or the airport no texture."""
    import pickle

    import O4_Imagery_Utils as IMG
    try:
        with open(FNAMES.apt_file(tile), "rb") as handle:
            dico = pickle.load(handle)
        wanted = airport_textures(tile, {k: v for k, v in dico.items()
                                         if str(k).upper() == str(icao).upper()})
    except Exception:
        return ()
    paths = [_orthophoto_path(tile, t, IMG) for ts in wanted.values() for t in ts]
    return tuple(sorted(p for p in paths if os.path.exists(p)))
