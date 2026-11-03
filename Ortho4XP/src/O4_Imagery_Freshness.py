"""Is a built tile's imagery what its provider serves now? (#1666)

The tile info's "Imagery check" row.  A tile keeps the orthophoto JPEGs it
was built from in the imagery cache, and a rebuild reuses them without
asking the server, so newer imagery from the same source is never seen.
This module answers, cheaply, whether the provider now serves something
else:

* SAMPLE.  Up to :data:`MAX_TEXTURES` of the tile's textures (spread over
  its grid, only those whose JPEG is still cached), two provider tiles
  inside each (:func:`_sample_parts`) — at most 16 requests.
* FIRST LOOK.  A sample with no record is fetched and compared with the
  matching pixels of the JPEG on disk (:func:`_pixels_match`: both reduced
  to 32 px, mean absolute difference under :data:`SAME_PIXEL_MAD`), so a
  tile built before this check existed is read the same way.  The answer
  is kept next to the JPEG (``<name>.jpg.src.json``, :func:`_record_path`)
  with the server's ``etag`` / ``last-modified`` and the body's SHA-1.
* LATER LOOKS.  A conditional GET (``If-None-Match`` /
  ``If-Modified-Since``): ``304`` keeps the recorded answer; a ``200``
  whose body hash is the recorded one keeps it too (a CDN that changed the
  ETag for the same bytes), and only a new body is compared again.
* CACHE.  A record younger than :data:`CHECK_TTL_S` is the answer without
  any request, so browsing the map does not hit providers; ``force``
  checks anyway.  A record whose JPEG's size or mtime changed is ignored.

Keys are the provider-tile position ``zl/x/y``, never the URL, so a token
or key in a URL never enters a record.  Requests go through the build's
fetcher (``O4_Imagery_Async.fetch_parts``: its host limits, pushback and
timeouts).  Only web-mercator grid sources downloaded at their own level
are checked; others answer ``unknown`` with the reason.  A build never
reads the records.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import O4_Custom_Scenery as PACKS

__all__ = [
    "UP_TO_DATE", "NEWER", "UNKNOWN", "NOT_CHECKED",
    "UPDATE_CONFIRM_TITLE", "UPDATE_CONFIRM_TEXT",
    "tile_freshness", "discard_tile_imagery",
]

UP_TO_DATE = "up_to_date"
NEWER = "newer"
UNKNOWN = "unknown"
NOT_CHECKED = "not_checked"

#: A recorded answer is reused without a request for this long.
CHECK_TTL_S = 7 * 86400
#: Textures sampled per tile (two provider tiles each: <= 16 requests).
MAX_TEXTURES = 8
#: Mean absolute difference (0-255, at 32 px) under which a provider tile
#: and the JPEG's pixels are the same imagery: JPEG re-encoding stays near
#: 1-3, a re-flown area differs by tens.
SAME_PIXEL_MAD = 8.0
_REDUCED = (32, 32)
#: The two provider tiles inside a texture's 16 x 16 grid that are sampled:
#: interior, away from the texture's edges and from each other.
_SAMPLE_OFFSETS = ((4, 4), (11, 11))
_FETCH_CAP = 4

#: The "Update Imagery" confirmation, both apps' words.
UPDATE_CONFIRM_TITLE = "Update this tile's imagery?"
UPDATE_CONFIRM_TEXT = (
    "The imagery downloaded for this tile is removed and the tile is "
    "rebuilt with what its source serves now. Until the build finishes, "
    "X-Plane shows this tile without its imagery.")

LABELS = {
    UP_TO_DATE: "Up to date",
    NEWER: "Newer imagery available",
    UNKNOWN: "Unknown",
    NOT_CHECKED: "Not checked yet",
}


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------
def _tile_textures(build_dir: str, provider: str, zl: int) -> List[Tuple[int, int]]:
    """``(til_x_left, til_y_top)`` of the tile's base textures of
    ``provider`` at ``zl`` (``textures/*.dds``, no suffix), sorted."""
    try:
        names = os.listdir(os.path.join(build_dir, "textures"))
    except OSError:
        return []
    found = set()
    for name in names:
        if not name.lower().endswith(".dds"):
            continue
        parsed = PACKS.texture_stem_attributes(name[:-4])
        if parsed and parsed[2] == provider and parsed[3] == zl and not parsed[4]:
            found.add((parsed[1], parsed[0]))
    return sorted(found)


def _spread(items: Sequence[Any], count: int) -> List[Any]:
    """``count`` items evenly spaced over ``items`` (all when fewer)."""
    if len(items) <= count:
        return list(items)
    step = len(items) / count
    return [items[int(i * step + step / 2)] for i in range(count)]


def _sample_parts(til_x_left: int, til_y_top: int) -> List[Tuple[int, int, int, int]]:
    """``(til_x, til_y, dx, dy)`` of the provider tiles sampled in one
    texture: their grid position and their place in its 16 x 16 parts."""
    return [(til_x_left + dx, til_y_top + dy, dx, dy) for dx, dy in _SAMPLE_OFFSETS]


def _checkable_reason(provider: Optional[dict], zl: int) -> str:
    """"" when ``provider``'s textures can be checked tile by tile, else
    the sentence why not."""
    if not provider:
        return "This source is a combination of sources; it can't be checked."
    if provider.get("grid_type") != "webmercator" or provider.get(
            "request_type") not in ("tms", "wmts"):
        return "This source gives no tile grid to compare against."
    if int(provider.get("super_resol_factor", 1) or 1) != 1 or (
            "max_zl" in provider and zl > int(provider["max_zl"])):
        return "This source's imagery is resampled when it is downloaded."
    return ""


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
def _record_path(jpeg_path: str) -> str:
    """The check record kept beside one cached orthophoto."""
    return jpeg_path + ".src.json"


def _jpeg_stamp(jpeg_path: str) -> Optional[List[float]]:
    try:
        st = os.stat(jpeg_path)
    except OSError:
        return None
    return [st.st_size, round(st.st_mtime, 3)]


def _read_record(jpeg_path: str) -> Dict[str, Any]:
    """The JPEG's samples (``{key: record}``); empty when absent,
    unreadable or written for another version of the JPEG."""
    try:
        with open(_record_path(jpeg_path), encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(record, dict) or record.get("jpeg") != _jpeg_stamp(jpeg_path):
        return {}
    parts = record.get("parts")
    return parts if isinstance(parts, dict) else {}


def _write_record(jpeg_path: str, parts: Dict[str, Any]) -> None:
    """Replace the JPEG's record (atomic; a denied folder is not an error)."""
    record = {"jpeg": _jpeg_stamp(jpeg_path), "parts": parts}
    path = _record_path(jpeg_path)
    with contextlib.suppress(OSError):
        with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
            json.dump(record, f, indent=1, sort_keys=True)
        os.replace(path + ".tmp", path)


# ---------------------------------------------------------------------------
# Judging one sample
# ---------------------------------------------------------------------------
def _jpeg_part(jpeg_path: str, dx: int, dy: int):
    """The JPEG's pixels of grid part ``(dx, dy)`` (1/16 of its side), or None."""
    from PIL import Image
    try:
        with Image.open(jpeg_path) as image:
            side = image.size[0] // 16
            return image.crop((dx * side, dy * side, (dx + 1) * side,
                               (dy + 1) * side)).convert("RGB")
    except Exception:
        return None


def _pixels_match(body: bytes, part) -> Optional[bool]:
    """True when ``body`` (one provider tile) shows the imagery of ``part``
    (:func:`_jpeg_part`), False when it does not, None when it is no image."""
    import numpy
    from PIL import Image
    try:
        with Image.open(io.BytesIO(body)) as served:
            reduced = served.convert("RGB").resize(_REDUCED, Image.Resampling.BOX)
    except Exception:
        return None
    ours = part.resize(_REDUCED, Image.Resampling.BOX)
    diff = numpy.abs(numpy.asarray(reduced, dtype=numpy.int16)
                     - numpy.asarray(ours, dtype=numpy.int16))
    return float(diff.mean()) < SAME_PIXEL_MAD


def _conditional_headers(base: Optional[dict], known: Optional[dict]) -> Dict[str, str]:
    """The request's headers, plus the validators ``known`` recorded."""
    headers = dict(base or {})
    if known and known.get("etag"):
        headers["If-None-Match"] = known["etag"]
    if known and known.get("last_modified"):
        headers["If-Modified-Since"] = known["last_modified"]
    return headers


def _judge_sample(known: Optional[dict], status: int, headers: Dict[str, str],
                 body: bytes, part_of_jpeg: Callable[[], Any],
                 now: float, placeholder: bool = False) -> Optional[dict]:
    """The sample's new record (``matches`` True / False), or None when the
    answer says nothing (no answer, an error, the server's no-imagery tile,
    a body that is no image).

    ``known`` is the recorded one; ``headers`` lower-cased;
    ``part_of_jpeg()`` gives the JPEG's pixels, read only when needed.
    """
    if status == 304 and known and "matches" in known:
        return {**known, "checked_at": now}
    if status != 200 or not body or placeholder:
        return None
    sha1 = hashlib.sha1(body).hexdigest()
    if known and known.get("sha1") == sha1 and "matches" in known:
        matches = known["matches"]
    else:
        part = part_of_jpeg()
        matches = _pixels_match(body, part) if part is not None else None
        if matches is None:
            return None
    return {"etag": headers.get("etag", ""),
            "last_modified": headers.get("last-modified", ""),
            "sha1": sha1, "matches": bool(matches), "checked_at": now}


# ---------------------------------------------------------------------------
# The tile
# ---------------------------------------------------------------------------
def _answer(status: str, detail: str, **extra) -> Dict[str, Any]:
    return {"status": status, "label": LABELS[status], "detail": detail, **extra}


def _verdict(records: Sequence[dict], source: str) -> Dict[str, Any]:
    """The tile's answer from its samples' records."""
    if not records:
        return _answer(UNKNOWN, "%s answered none of the sampled spots with "
                       "imagery; try again later." % source)
    checked_at = min(r.get("checked_at", 0) for r in records)
    when = time.strftime("%Y-%m-%d", time.localtime(checked_at))
    changed = sum(1 for r in records if not r.get("matches"))
    counts = {"sampled": len(records), "changed": changed, "checked_at": checked_at}
    if changed:
        return _answer(NEWER, "%d of %d sampled spots differ from what %s "
                       "serves now (checked %s). Update Imagery downloads "
                       "this tile's imagery again and rebuilds it."
                       % (changed, len(records), source, when), **counts)
    return _answer(UP_TO_DATE, "The %d sampled spots match what %s serves now "
                   "(checked %s). A rebuild keeps the imagery already "
                   "downloaded." % (len(records), source, when), **counts)


def _plan(lat, lon, build_dir, provider_code, zl, provider):
    """``[(jpeg_path, [(key, til_x, til_y, dx, dy), ...]), ...]`` to sample."""
    import O4_File_Names as FNAMES
    folder = FNAMES.jpeg_file_dir_from_attributes(lat, lon, zl, provider)
    textures = []
    for til_x, til_y in _tile_textures(build_dir, provider_code, zl):
        path = os.path.join(folder, FNAMES.jpeg_file_name_from_attributes(
            til_x, til_y, zl, provider_code))
        if os.path.isfile(path):
            textures.append((path, [("%d/%d/%d" % (zl, x, y), x, y, dx, dy)
                                    for x, y, dx, dy in _sample_parts(til_x, til_y)]))
    return _spread(textures, MAX_TEXTURES)


@dataclass
class _Answer:
    """One threaded answer, shaped as the fetcher's ``FetchResult``."""

    status: int
    body: bytes
    headers: Dict[str, str]


def _fetch(provider, requests_, should_stop):
    """``{key: answer}`` through the build's fetcher: the async one
    (``fetch_parts``: host limits, pushback, timeouts), else — with
    ``O4_IMAGERY_FETCHER=threads``, the test suite's choice — plain GETs."""
    import O4_Imagery_Async as FETCH_ASYNC
    import O4_Imagery_Utils as IMG
    timeout = IMG.provider_timeout(provider.get("timeout"))
    if FETCH_ASYNC.fetcher_choice() == "async":
        return FETCH_ASYNC.fetch_parts(
            requests_, provider.get("code", ""), _FETCH_CAP, should_stop=should_stop,
            timeout_s=timeout, host_limit=IMG.host_request_limit(provider))
    import requests

    def get(item):
        key, url, headers = item
        if should_stop():
            return key, None
        try:
            r = requests.get(url, headers=headers, timeout=timeout or 20)
        except requests.RequestException:
            return key, None
        return key, _Answer(r.status_code, r.content,
                            {k.lower(): v for k, v in r.headers.items()})

    with ThreadPoolExecutor(max_workers=_FETCH_CAP) as pool:
        return {key: answer for key, answer in pool.map(get, requests_) if answer}


def _requests_for(plan, known, provider, zl, now, force):
    """The conditional GETs of the samples without a fresh record, and
    their URLs (for the placeholder test)."""
    import O4_Imagery_Utils as IMG
    requests_, urls = [], {}
    for path, parts in plan:
        for key, til_x, til_y, _dx, _dy in parts:
            rec = known[path].get(key)
            if rec and not force and now - rec.get("checked_at", 0) < CHECK_TTL_S:
                continue
            request = IMG.wmts_request(zl, til_x, til_y, provider)
            if request is not None:
                urls[(path, key)] = request[0]
                requests_.append(((path, key), request[0],
                                  _conditional_headers(request[1], rec)))
    return requests_, urls


def _probe(plan, provider, zl, now, force, fetch, should_stop):
    """Every sample's record, from the cache or the server; writes them."""
    import O4_Imagery_Utils as IMG
    known = {path: _read_record(path) for path, _ in plan}
    requests_, urls = _requests_for(plan, known, provider, zl, now, force)
    results = fetch(provider, requests_, should_stop) if requests_ else {}
    records = []
    for path, parts in plan:
        updated = dict(known[path])
        for key, _x, _y, dx, dy in parts:
            result = results.get((path, key))
            if result is not None:
                headers = dict(result.headers or {})
                new = _judge_sample(
                    updated.get(key), int(result.status or 0), headers,
                    result.body or b"", lambda p=path, a=dx, b=dy: _jpeg_part(p, a, b),
                    now, placeholder=IMG.is_placeholder_tile(urls[(path, key)], headers))
                if new is not None:
                    updated[key] = new
            if "matches" in updated.get(key, {}):
                records.append(updated[key])
        if updated != known[path]:
            _write_record(path, updated)
    return records


def _cached_answer(plan, source, now):
    """The answer from fresh records alone, or "not checked yet"."""
    wanted = [(path, part[0]) for path, parts in plan for part in parts]
    stored = {path: _read_record(path) for path, _ in plan}
    fresh = [stored[path].get(key) for path, key in wanted]
    if not all(rec and "matches" in rec and now - rec.get("checked_at", 0) < CHECK_TTL_S
               for rec in fresh):
        return _answer(NOT_CHECKED, "%s has not been asked yet." % source)
    return _verdict(fresh, source)


def tile_freshness(lat: int, lon: int, build_dir: str, provider_code: str, zl: int,
                   *, force: bool = False, cached_only: bool = False,
                   providers: Optional[dict] = None, fetch=None,
                   should_stop: Callable[[], bool] = lambda: False,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """The tile's imagery check: ``status`` (:data:`UP_TO_DATE`,
    :data:`NEWER`, :data:`UNKNOWN`, :data:`NOT_CHECKED`), its ``label``
    and ``detail`` sentence, and ``sampled`` / ``changed`` /
    ``checked_at`` when samples were judged.

    ``cached_only`` never sends a request (a sample without a fresh record
    makes the answer "not checked yet"); ``providers`` and ``fetch`` are
    the registry and the network, replaced by tests.
    """
    if providers is None:
        import O4_Imagery_Utils as IMG
        providers = IMG.providers_dict
    now = time.time() if now is None else now
    if not provider_code or not zl:
        return _answer(UNKNOWN, "This tile's imagery source is not known.")
    provider = providers.get(provider_code)
    reason = _checkable_reason(provider, int(zl))
    if reason:
        return _answer(UNKNOWN, reason)
    plan = _plan(lat, lon, build_dir, provider_code, int(zl), provider)
    if not plan:
        return _answer(UNKNOWN, "The imagery this tile was built from is no "
                       "longer in the imagery cache, so there is nothing to compare.")
    source = str(provider.get("name") or provider_code)
    if cached_only:
        return _cached_answer(plan, source, now)
    try:
        records = _probe(plan, provider, int(zl), now, force, fetch or _fetch, should_stop)
    except Exception as error:      # the answer says so; the caller lives on
        return _answer(UNKNOWN, "The check could not reach %s (%s)." % (source, error))
    return _verdict(records, source)


def discard_tile_imagery(lat: int, lon: int, build_dir: str, provider_code: str,
                         zl: int, providers: Optional[dict] = None) -> Dict[str, int]:
    """"Update Imagery": remove the tile's cached orthophotos of
    ``provider_code`` at ``zl`` (with their records) and its converted
    base textures, so the rebuild that follows downloads them again.
    ``{"jpegs": n, "textures": m}`` removed."""
    import O4_File_Names as FNAMES
    if providers is None:
        import O4_Imagery_Utils as IMG
        providers = IMG.providers_dict
    provider = providers.get(provider_code)
    removed = {"jpegs": 0, "textures": 0}
    if not provider or not zl:
        return removed
    folder = FNAMES.jpeg_file_dir_from_attributes(lat, lon, int(zl), provider)
    for til_x, til_y in _tile_textures(build_dir, provider_code, int(zl)):
        jpeg = os.path.join(folder, FNAMES.jpeg_file_name_from_attributes(
            til_x, til_y, int(zl), provider_code))
        dds = os.path.join(build_dir, "textures", FNAMES.dds_file_name_from_attributes(
            til_x, til_y, int(zl), provider_code))
        for path, kind in ((jpeg, "jpegs"), (_record_path(jpeg), ""), (dds, "textures")):
            try:
                os.remove(path)
            except OSError:
                continue
            if kind:
                removed[kind] += 1
    return removed
