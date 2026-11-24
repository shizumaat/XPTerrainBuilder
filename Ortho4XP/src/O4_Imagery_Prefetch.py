"""Imagery downloads while the vector step builds the airport patch (#1002).

The texture SET is mesh-derived, so the imagery step cannot start before
the mesh.  But a tile built before names its textures already: the live
``terrain/*.ter`` files are named after their texture
(``<til_y>_<til_x>_<provider><zoom>[_water|_sea][_overlay].ter``,
``O4_DSF_Utils.create_terrain_file``).  The texture GRID is the zoom
level's and the same for every imagery source, so that list, re-keyed to
the source this build uses, is the best pre-mesh guess at what the
imagery step will download (plan: docs/findings/imagery-prefetch-plan-622.md).

:func:`candidates` derives that list.  A tile never built has none, so
:func:`_first_build_plan` names the set from the tile, its zoom and its water
(``O4_Imagery_Plan``) once those are on disk.

ONE JOB PER TILE, independent of the build step (#2254, owner
2026-11-23T16:52Z).  :func:`open_job` starts it with the vector step; it
keeps downloading through the solve, the mesh and the masks, and the imagery
step adopts it (:func:`adopt_job`).  A worker child may start it without an
imagery token: the parent lends one the moment the imagery class has room
(:func:`grant_token`), and the job hands it back when it drains or is
adopted.  The parent's class count stays the only owner of those tokens,
and each request still takes a slot of its server's ``net:`` class, so a
flight's imagery goes first (``O4_Machine_Slots.hold_net_for_flight``).

DOWNLOADS ONLY: an orthophoto lands in the imagery cache exactly where the
imagery step looks for it; no conversion runs here (the DDS conversion
needs the colour-harmonization field and the masks).  The imagery step is
unchanged: it finds what arrived and downloads only the rest, joining an
orthophoto still in flight on its file lock, so nothing is requested twice.
Its download count, its bar share (#653) and the measured rate count only
what IT downloaded.

Bounds: the imagery step's own orthophotos at once
(:func:`airport_download_slots`).  Stop (``UI.red_flag``) ends the job after
the orthophoto in flight; what arrived stays (orthophotos are cache, not
scenery: the #598 stop rule).  Only a WHOLE orthophoto is kept -- a part the
provider did not answer leaves no file, so the imagery step downloads that
texture itself.  The ``default_xplane`` texture mode and a combined source
fetch nothing ahead.

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
never added.  It downloads :func:`airport_download_slots` orthophotos at
once — the imagery step's own ``max_download_slots`` (#2082) — and the
background prefetch starts no new orthophoto while it runs, so the patch
never waits behind a non-airport photo.  The vector step hands it only the
airports this build patches (#2082).
"""

from __future__ import annotations

import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Imagery_Plan as PLAN
import O4_Step_Wait as STEP_WAIT
import O4_Tile_Staging as STAGING
import O4_UI_Utils as UI

__all__ = ["candidates", "Prefetch", "open_job",
           "grant_token", "adopt_job", "end_job", "vector_ended",
           "fetch_airport_imagery", "cached_airport_imagery", "AIRPORT_MARGIN_M",
           "airport_download_slots"]

#: How long a job told to stop waits for the orthophoto in flight.  It
#: starts nothing new; a provider request that outlives this is abandoned
#: to its daemon thread.
STOP_WAIT_SECONDS = 120.0
#: ... and how long a Stop waits: a part request ends at the flag, so this
#: only covers an orthophoto being written.
USER_STOP_WAIT_SECONDS = 15.0
#: How often the plan looks for the layers it reads.
PLAN_RETRY_SECONDS = 2.0

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


def _fetch_for_imagery_step(tile, texture):
    """One WHOLE orthophoto where the imagery step will look for it (a
    placeholder build reads a coarser tier, #1992); 1 or 0."""
    import O4_Imagery_Utils as IMG

    (folder, name, drop) = IMG.imagery_step_source(tile, *texture)
    path = os.path.join(folder, name)
    with _DOWNLOAD_LOCKS_GUARD:
        lock = _DOWNLOAD_LOCKS.setdefault(path, threading.Lock())
    with lock:
        if os.path.exists(path):
            return 1
        return IMG.download_orthophoto_once(
            folder, name, *texture, require_complete=True, drop=drop)


def _still_missing(tile, texture, imagery):
    if _texture_is_built(tile, texture):
        return False
    (folder, name, _drop) = imagery.imagery_step_source(tile, *texture)
    return not os.path.exists(os.path.join(folder, name))


def _first_build_plan(tile, imagery=None, predict=PLAN.predicted_textures):
    """What a build with no usable last texture list will use: ``[]`` when
    :func:`candidates` can answer, ``None`` until the layers the prediction
    reads are on disk."""
    live = _live_textures(tile)
    if live and (Counter(t[2] for t in live).most_common(1)[0][0]
                 == int(getattr(tile, "default_zl", 0) or 0)):
        return []
    found = predict(tile)
    if found is None:
        return None
    if imagery is None:
        import O4_Imagery_Utils as imagery
    return [t for t in found if _still_missing(tile, t, imagery)]


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


def airport_download_slots():
    """Orthophotos the airport fetch downloads at once: the imagery step's
    own count (``O4_Tile_Utils.max_download_slots`` through
    ``effective_download_slots``, #2082) — each still at the provider's
    ``max_threads`` and under the server's session budget (#1236)."""
    from O4_Parallel_Utils import effective_download_slots
    try:
        import O4_Tile_Utils as TILE
        configured = getattr(TILE, "max_download_slots", 0)
    except Exception:
        configured = 0
    return effective_download_slots(configured)


def fetch_airport_imagery(tile, dico_airports, fetch=None, find=airport_textures,
                          download=True, slots=None):
    """THE PATCH WAITS FOR THE AIRPORT'S OWN PHOTOS (26y): download every
    missing texture of :func:`airport_textures` now, ``slots`` at a time
    (default :func:`airport_download_slots`), and return
    ``{airport: (orthophoto path, ...)}`` of those in the cache
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
    def one(texture):
        if UI.red_flag:
            return
        try:
            fetch(tile, texture)
        except Exception as error:
            UI.vprint(1, "    Airport orthophoto", texture, "failed:", error)
    if missing:
        workers = max(1, min(int(slots or airport_download_slots()), len(missing)))
        # The step only waits on these downloads: they run under the
        # imagery token and the server's class, its own slots are free.
        with STEP_WAIT.waiting(), ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, missing))   # all done before the patch builds
    out = {}
    for name, ts in wanted.items():
        paths = tuple(p for p in (_orthophoto_path(tile, t, IMG) for t in ts)
                      if os.path.exists(p))
        if paths:
            out[name] = paths
    return out


class Prefetch:
    """One tile's orthophoto job, from the vector step until the imagery
    step adopts it (see the module).  ``token``: the job holds an imagery
    token now; without one it waits for :meth:`grant_token`.  ``plan`` adds
    textures once it can name them (:func:`_first_build_plan`)."""

    def __init__(self, tile, textures, fetch=None, on_done=None, plan=None,
                 token=True, slots=None):
        self.tile = tile
        self.textures = list(textures)
        self.downloaded = 0
        self.failed = 0
        self.fetched = set()
        self._fetch = fetch or _fetch_for_imagery_step
        self._airport_fetch = fetch or download_orthophoto
        self._on_done = on_done
        self._plan = plan
        self._token = bool(token)
        self._slots = slots
        self._stop = threading.Event()
        self._vector_ended = threading.Event()
        # the airports file is whole: the airport fetch ran, or none comes
        self._airports_known = threading.Event()
        self._threads = []
        self._lock = threading.Lock()
        self._pending = list(reversed(self.textures))
        self._queued = set(self.textures)
        self._running = 0
        self._plan_open = plan is not None
        self._plan_started = False
        self._reported = False
        # #1359 (26y): the vector step's airport fetch rides this token, so
        # the report (which hands the token back) waits for the queue to
        # drain AND for the airport fetch, or for the vector step's end
        self._airports_pending = True
        # the background starts no orthophoto while the airport fetch runs
        # (#2082): the patch never waits behind a non-airport photo
        self._airport_fetches = 0
        self._airports_idle = threading.Condition(self._lock)

    @property
    def open(self):
        """Can this job still take a token and download?"""
        return not self._stop.is_set() and not self._reported

    def start(self):
        """Begin the downloads if the job holds a token."""
        if self._token:
            self._begin()
        return self

    def _begin(self):
        if self.textures and not self._threads:
            UI.vprint(1, "    * Downloading", len(self.textures),
                      "orthophotos the last build of this tile used, while "
                      "the tile builds.")
        self._start_plan()
        self._start_workers()
        self._maybe_finish()

    def grant_token(self):
        """The parent lent a token; False when this job can no longer use
        it, and the caller hands it straight back."""
        with self._lock:
            if self._stop.is_set() or self._reported:
                return False
            self._token = True
        self._begin()
        return True

    def _start_plan(self):
        with self._lock:
            if self._plan is None or self._plan_started:
                return
            self._plan_started = True
        threading.Thread(target=self._plan_loop, daemon=True).start()

    def _plan_loop(self):
        """Ask the plan until it answers or the vector step has ended (its
        layers are on disk by then, or will not be)."""
        found = []
        self._airports_known.wait()
        try:
            while not self._stop.is_set():
                last_try = self._vector_ended.is_set()
                with UI.quiet_thread():
                    answer = self._plan(self.tile)
                if answer is not None:
                    found = answer
                    break
                if last_try:
                    break
                self._vector_ended.wait(PLAN_RETRY_SECONDS)
        except Exception as error:
            UI.vprint(1, "    Imagery plan skipped:", error)
        self._extend(found)
        with self._lock:
            self._plan_open = False
        self._start_workers()
        self._maybe_finish()

    def _extend(self, textures):
        with self._lock:
            added = [t for t in textures if t not in self._queued]
            self._queued.update(added)
            self.textures.extend(added)
            self._pending[:0] = list(reversed(added))
        if added:
            UI.vprint(1, "    * Downloading", len(added), "orthophotos this "
                      "tile will use, while it builds.")

    def _start_workers(self):
        slots = max(1, int(self._slots or airport_download_slots()))
        with self._lock:
            if self._stop.is_set() or not self._token:
                return
            count = max(0, min(slots - self._running, len(self._pending)))
            self._running += count
        for _ in range(count):
            thread = threading.Thread(target=self._work, daemon=True)
            self._threads.append(thread)
            thread.start()

    def _next(self):
        with self._lock:
            while self._airport_fetches and not self._stop.is_set():
                self._airports_idle.wait(1.0)
            if self._stop.is_set() or UI.red_flag or not self._pending:
                return None
            return self._pending.pop()

    def _note_result(self, texture, ok):
        with self._lock:
            if ok:
                self.downloaded += 1
                self.fetched.add(tuple(texture))
            else:
                self.failed += 1

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
                self._note_result(texture, ok)
        finally:
            with self._lock:
                self._running -= 1
            self._maybe_finish()

    def _maybe_finish(self):
        """Report once nothing is queued, running or still to be named."""
        with self._lock:
            ready = (self._token and not self._running and not self._pending
                     and not self._plan_open and not self._airports_pending
                     and not self._airport_fetches)
        if ready:
            self._finish()

    def fetch_airports(self, dico_airports, find=airport_textures):
        """The vector step's airport fetch (26y).  UNDER THIS JOB'S TOKEN:
        :func:`fetch_airport_imagery` with its fetcher, the downloads
        counted in the report.  With no token yet it reads the cache."""
        if not self._token:
            with self._lock:
                self._airports_pending = False
            self._airports_known.set()
            return fetch_airport_imagery(self.tile, dico_airports, find=find,
                                         download=False)

        def counted(tile, texture):
            ok = self._airport_fetch(tile, texture)
            self._note_result(texture, ok)
            return ok
        with self._lock:
            self._airport_fetches += 1
        try:
            return fetch_airport_imagery(self.tile, dico_airports, fetch=counted, find=find)
        finally:
            with self._lock:
                self._airport_fetches -= 1
                self._airports_idle.notify_all()
                self._airports_pending = False
            self._airports_known.set()
            self._maybe_finish()

    def vector_ended(self):
        """The vector step is over: no airport fetch comes, and the plan's
        layers are on disk.  The job itself goes on."""
        self._vector_ended.set()
        self._airports_known.set()
        with self._lock:
            self._airports_pending = False
            self._airports_idle.notify_all()
        self._maybe_finish()

    def _finish(self):
        """Report once, to whoever lent the token (no token, no report)."""
        with self._lock:
            callback, self._on_done = self._on_done, None
            self._reported = True
            held = self._token
        if callback is not None and held:
            try:
                callback(self.downloaded, self.failed)
            except Exception:
                pass

    def stop(self, wait_seconds=STOP_WAIT_SECONDS):
        """Start nothing new, wait up to ``wait_seconds`` for what is in
        flight, and hand the token back.  With 0 the imagery step takes
        over: it joins an orthophoto in flight on its file lock."""
        self._stop.set()
        self._vector_ended.set()
        self._airports_known.set()
        with self._lock:
            self._airports_pending = False
            self._plan_open = False
            self._airports_idle.notify_all()
        if wait_seconds:
            deadline = time.monotonic() + wait_seconds
            for thread in list(self._threads):
                thread.join(max(0.0, deadline - time.monotonic()))
        if self.textures:
            UI.vprint(1, "    * Prefetched", self.downloaded, "of",
                      len(self.textures), "orthophotos",
                      "(%d failed)." % self.failed if self.failed else ".")
        self._finish()

    def report_unused(self, used):
        """Say how many orthophotos fetched ahead the build did not use;
        the count."""
        unused = PLAN.unused(self.fetched, used)
        if self.fetched:
            UI.vprint(1, "    * Fetched ahead:", len(self.fetched),
                      "orthophotos,", len(unused), "not used by this build.")
        return len(unused)


#: this process's open job per tile
_JOBS: dict = {}
_JOBS_GUARD = threading.Lock()


def _job_key(tile):
    return (int(tile.lat), int(tile.lon))


def open_job(tile, on_done=None, token=True, fetch=None, find=candidates,
             plan=_first_build_plan, slots=None):
    """The tile's job, started now, or the one already open (a tile sent
    back to its vector step).  Another tile's job left here ends: a worker
    process builds one tile at a time.  Never raises for the scan."""
    key = _job_key(tile)
    with _JOBS_GUARD:
        job = _JOBS.get(key)
        others = [k for k in _JOBS if k != key]
        ended = [_JOBS.pop(k) for k in others]
    for other in ended:
        other.stop(0)
    if job is not None and job.open:
        if token:
            job.grant_token()
        return job
    try:
        textures = find(tile)
    except Exception as error:
        UI.vprint(1, "    Imagery prefetch skipped:", error)
        textures = []
    job = Prefetch(tile, textures, fetch=fetch, on_done=on_done, plan=plan,
                   token=token, slots=slots)
    with _JOBS_GUARD:
        _JOBS[key] = job
    return job.start()


def grant_token(lat, lon):
    """Hand tile ``(lat, lon)``'s job the token its parent lent; False when
    no open job can use it."""
    with _JOBS_GUARD:
        job = _JOBS.get((int(lat), int(lon)))
    return job.grant_token() if job is not None else False


def vector_ended(tile):
    """The tile's vector step ended well; its job carries on."""
    with _JOBS_GUARD:
        job = _JOBS.get(_job_key(tile))
    if job is not None:
        job.vector_ended()


def adopt_job(tile):
    """The imagery step starts: the job stops taking new orthophotos and
    returns its token; the step downloads what is left."""
    with _JOBS_GUARD:
        job = _JOBS.get(_job_key(tile))
    if job is not None:
        job.stop(0)


def end_job(tile, used=None):
    """The tile's job is over (its imagery step ended, a step failed, or
    Stop).  ``used``: the textures the imagery step asked for, reported
    against what was fetched ahead."""
    with _JOBS_GUARD:
        job = _JOBS.pop(_job_key(tile), None)
    if job is None:
        return
    job.stop(USER_STOP_WAIT_SECONDS if UI.red_flag else 0)
    if used is not None:
        job.report_unused(used)


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
