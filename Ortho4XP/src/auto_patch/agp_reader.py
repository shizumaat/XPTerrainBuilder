"""Resolve and parse X-Plane AGP (AutoGen Point) building footprints.

Unlike ``.fac`` facades — which X-Plane places in the DSF as full
draped POLYGONs whose ring geometry the ``dsf_reader`` walks directly —
an ``.agp`` building is placed as a single ``OBJECT`` point plus a
heading (the "handle").  The footprint is NOT in the DSF at all; it is
encoded inside the ``.agp`` sidecar file, which we must locate (via the
X-Plane ``library.txt`` virtual→physical map) and parse ourselves.

This module owns that work, kept independent of the DSF reader so it is
unit-testable in isolation:

  1. ``get_library_index(xplane_root)`` — build (once, memoized
     in-process AND on disk) the ``library.txt`` ``EXPORT`` table
     mapping a virtual library path (e.g.
     ``lib/airport/Common_Elements/Hangars/Lg_Maint_Gray.agp``) to the
     absolute path of the physical resource on disk.
  2. ``parse_agp(path)`` — read (once, memoized) an ``.agp`` file and
     return its footprint as a polygon in LOCAL METERS relative to the
     placement anchor, before any placement heading is applied.
  3. ``agp_footprint_lonlat(...)`` — given a placement (virtual path,
     handle lon/lat, heading) project the local footprint to a
     lon/lat ring ready to hand to the building pipeline.

Footprint geometry (per design decision 2026-06-17): the encoded
``CROP_POLY`` (the draped ground polygon), falling back to the ``TILE``
rectangle, scaled from texture pixels to meters via
``TEXTURE_WIDTH/HEIGHT ÷ TEXTURE_SCALE`` and re-centred on ``ANCHOR_PT``
(the pixel that lands on the DSF handle; defaults to the tile centre
when absent).
"""
from __future__ import annotations

import math
import os
import threading
from collections import namedtuple


# Parsed footprint of one .agp: ``local_poly`` is a list of (x, y) in
# meters relative to the anchor (x = texture S / east, y = texture T /
# north) BEFORE the placement heading; ``rotation`` is the tile's own
# internal ROTATION (degrees, almost always 0) which combines with the
# placement heading at projection time.
AgpFootprint = namedtuple("AgpFootprint", ["local_poly", "rotation"])


# Memoized library index, keyed by absolute xplane_root.  Built once per
# process and shared by every airport / caller — scanning the thousands
# of library.txt EXPORT entries is the one genuinely expensive disk step
# and must not repeat per-airport.  Across processes the merged index is
# served from a disk sidecar instead (see ``_library_index_sidecar``);
# this in-process memo stays keyed on the root ALONE so the millions of
# ``resolve_library_path`` lookups a build makes never pay a stat.
_LIB_INDEX_CACHE: dict[str, dict[str, str]] = {}

# One lock per absolute xplane_root: concurrent threads that miss the
# memo would otherwise each re-parse every library.txt (the object
# readers' per-DSF lock precedent, commit a4133d8).
_LIB_INDEX_LOCKS: dict[str, threading.Lock] = {}
_LIB_INDEX_LOCKS_GUARD = threading.Lock()

# Memoized .agp parse results, keyed by absolute physical path.  An .agp
# referenced by many placements / many airports is read and parsed from
# disk exactly once; footprint geometry is immutable so no invalidation.
_AGP_CACHE: dict[str, AgpFootprint | None] = {}


# ── library.txt resolution ───────────────────────────────────────────
def _scenery_pack_order(xplane_root: str) -> list[str]:
    """Custom Scenery pack directory names in LOW→HIGH library priority.

    X-Plane resolves library paths with packs listed FIRST in
    ``Custom Scenery/scenery_packs.ini`` taking priority.  We return the
    packs lowest-priority-first so a caller can overwrite into a dict and
    let the highest-priority provider win.  Packs absent from the ini (or
    when the ini is missing) are appended in sorted order at the lowest
    priority for determinism.
    """
    custom = os.path.join(xplane_root, "Custom Scenery")
    if not os.path.isdir(custom):
        return []
    on_disk = {d for d in os.listdir(custom)
               if os.path.isdir(os.path.join(custom, d))}
    ordered_high_to_low: list[str] = []
    ini = os.path.join(custom, "scenery_packs.ini")
    if os.path.isfile(ini):
        try:
            with open(ini, "r", encoding="utf-8",
                      errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith("SCENERY_PACK"):
                        continue
                    rest = line.split(None, 1)[1] if " " in line else ""
                    rest = rest.strip().rstrip("/")
                    # "Custom Scenery/<pack>" → "<pack>"
                    name = os.path.basename(rest)
                    if name in on_disk and name not in ordered_high_to_low:
                        ordered_high_to_low.append(name)
        except OSError:
            pass
    # Append any on-disk packs the ini didn't mention (sorted, lowest).
    for name in sorted(on_disk):
        if name not in ordered_high_to_low:
            ordered_high_to_low.append(name)
    # Reverse → low priority first (so dict-overwrite leaves high last).
    return list(reversed(ordered_high_to_low))


def _parse_library_txt(lib_path: str, index: dict[str, str]) -> None:
    """Merge the ``EXPORT*`` directives of one ``library.txt`` into
    ``index`` (virtual-path → absolute physical-path).  Later calls
    overwrite earlier ones, so callers must visit lower-priority
    libraries first."""
    lib_dir = os.path.dirname(lib_path)
    try:
        with open(lib_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tok = line.split()
        directive = tok[0]
        # EXPORT / EXPORT_EXTEND / EXPORT_BACKUP: <virtual> <physical...>
        # EXPORT_RATIO: <ratio> <virtual> <physical...>  (skip the ratio)
        if directive in ("EXPORT", "EXPORT_EXTEND", "EXPORT_BACKUP"):
            args = tok[1:]
        elif directive == "EXPORT_RATIO":
            args = tok[2:]
        else:
            continue
        if len(args) < 2:
            continue
        virtual = args[0]
        # The physical path is the remainder; it may contain spaces, so
        # re-split the original line off the virtual token rather than
        # trusting whitespace tokenization beyond it.
        physical = line.split(virtual, 1)[1].strip()
        if not physical:
            continue
        phys_abs = os.path.normpath(
            os.path.join(lib_dir, physical.replace("\\", "/")))
        index[virtual] = phys_abs
        # Case-insensitive fallback key (some packs differ only in case
        # from the DSF reference); the exact key above wins on lookup.
        index.setdefault(virtual.lower(), phys_abs)


def _library_source_files(xplane_root: str) -> list[str]:
    """Every ``library.txt`` this install contributes, in the order
    :func:`get_library_index` merges them — LOWEST library priority
    first, so a later parse overwrites an earlier one.

    Default scenery leads (custom packs override it), then the custom
    packs in reverse ``scenery_packs.ini`` order.  Discovery is cheap
    (a listdir per root plus one ``isfile`` per candidate); PARSING the
    files is what costs, so this list doubles as the exact input set the
    disk cache fingerprints."""
    sources: list[str] = []
    default_root = os.path.join(xplane_root, "Resources", "default scenery")
    if os.path.isdir(default_root):
        for entry in sorted(os.listdir(default_root)):
            cand = os.path.join(default_root, entry, "library.txt")
            if os.path.isfile(cand):
                sources.append(cand)
    custom_root = os.path.join(xplane_root, "Custom Scenery")
    for pack in _scenery_pack_order(xplane_root):
        cand = os.path.join(custom_root, pack, "library.txt")
        if os.path.isfile(cand):
            sources.append(cand)
    return sources


# ── persistent (cross-process) merged-index cache ────────────────────
#
# Building the merged index means parsing EVERY library.txt of the
# install: 337 files / ~135 k EXPORT entries / ~0.57 s on the reference
# X-Plane 12 install (measured 2026-07-24).  The in-process memo above
# pays that once per PROCESS — but a per-airport auto_patch build is a
# fresh process, so every cold build paid it again, against a 60 s
# per-airport budget whose 1 % tripwire is 0.6 s (CLAUDE.md item 6).
# The merged dict is a pure function of the library.txt files consulted,
# so it is cached to a sidecar keyed on an EXACT fingerprint of those
# inputs and re-served in ~15 ms.
#
# Bump when the parse changes shape in a way that would make an old
# cached index wrong (e.g. a new EXPORT directive, a different key
# scheme) — invalidates every sidecar.
_LIB_INDEX_CACHE_VERSION = 1

# Sidecar name prefix; the full name carries a digest of the absolute
# xplane_root so two installs never collide.  Lives beside the object
# readers' per-pack sidecars under the data root's ``Airport_mod_cache/``
# (user ruling 2026-07-15: Ortho4XP caches never clutter scenery packs);
# this one is install-wide, not pack-scoped, so it sits at that root.
_LIB_INDEX_SIDECAR_PREFIX = "o4_library_index"


def _vprint(message: str) -> None:
    """Verbosity-1 progress line, best effort — this module stays
    importable (and unit-testable) without the Ortho4XP UI module on
    ``sys.path``."""
    try:
        import O4_UI_Utils as UI
    except ImportError:
        return
    UI.vprint(1, message)


def _library_index_lock(key: str) -> threading.Lock:
    """One lock per absolute ``xplane_root``."""
    with _LIB_INDEX_LOCKS_GUARD:
        lock = _LIB_INDEX_LOCKS.get(key)
        if lock is None:
            lock = _LIB_INDEX_LOCKS[key] = threading.Lock()
    return lock


def _library_index_sidecar(
    xplane_root: str,
    sources: list[str],
) -> tuple[str | None, str | None]:
    """Sidecar path + input fingerprint for the merged library index.

    The fingerprint (sha1, same style as the object readers' pack
    sidecars) covers, and therefore invalidates on ANY change to:

    * :data:`_LIB_INDEX_CACHE_VERSION` and the absolute ``xplane_root``;
    * ``Custom Scenery/scenery_packs.ini`` — its (size, mtime), or an
      explicit "absent" marker.  The ini decides pack PRIORITY, and a
      reorder that changes nothing else still changes who wins a virtual
      path;
    * the ordered list of every ``library.txt`` consulted, each as
      ``(path, size, mtime)``.  Mtimes are taken in NANOSECONDS: a file
      rewritten within the same microsecond as its predecessor and to
      the same length must still miss.  The ORDER is digested too (it
      is the merge order), so a reprioritised ini invalidates even in
      the impossible case where its own stat is unchanged.  A pack
      added or removed, or a library.txt created, deleted or edited,
      changes this list — there is no path by which the merged dict can
      differ while the fingerprint matches.

    Returns ``(None, None)`` — no read, no write, exactly the
    pre-cache behaviour — when ``O4_LIBRARY_INDEX_CACHE=0``, when no
    Ortho4XP data root is resolvable (this module is importable without
    the rest of the app), or when a stat fails mid-fingerprint."""
    if os.environ.get("O4_LIBRARY_INDEX_CACHE", "1") != "1":
        return None, None
    try:
        import O4_File_Names as _FNAMES
    except ImportError:
        return None, None

    import hashlib
    root_abs = os.path.abspath(xplane_root)
    digest = hashlib.sha1()
    try:
        digest.update(f"{_LIB_INDEX_CACHE_VERSION}:{root_abs}".encode())
        ini = os.path.join(xplane_root, "Custom Scenery",
                           "scenery_packs.ini")
        try:
            ini_stat = os.stat(ini)
            digest.update(
                f"|ini:{ini_stat.st_size}:{ini_stat.st_mtime_ns}".encode())
        except OSError:
            digest.update(b"|ini:absent")
        for source in sources:
            source_stat = os.stat(source)
            digest.update(
                f"|lib:{source}:{source_stat.st_size}"
                f":{source_stat.st_mtime_ns}".encode())
    except OSError:
        return None, None

    # ``data_path`` follows the current working directory in a source
    # checkout — resolve it at call time, never at import time.
    cache_directory = _FNAMES.data_path("Airport_mod_cache")
    root_key = hashlib.sha1(root_abs.encode()).hexdigest()[:16]
    return (
        os.path.join(cache_directory,
                     f"{_LIB_INDEX_SIDECAR_PREFIX}_{root_key}.cache"),
        digest.hexdigest(),
    )


def _read_library_index_sidecar(
    sidecar_path: str | None,
    fingerprint: str | None,
) -> dict[str, str] | None:
    """Load the merged index from its sidecar on a fingerprint match,
    else ``None`` (missing, stale, corrupt or unreadable — the caller
    rebuilds and rewrites)."""
    import pickle
    if not (sidecar_path and fingerprint and os.path.isfile(sidecar_path)):
        return None
    try:
        with open(sidecar_path, "rb") as sidecar_file:
            payload = pickle.load(sidecar_file)
        if payload.get("fingerprint") != fingerprint:
            _vprint("   [library] index sidecar cache STALE (X-Plane "
                    "libraries changed since it was written) - rebuilding")
            return None
        index = payload["index"]
        if not isinstance(index, dict):
            return None
        _vprint("   [library] index read from the sidecar cache "
                f"(fingerprint match, {len(index)} entries)")
        return index
    except Exception:
        return None


def _write_library_index_sidecar(
    sidecar_path: str | None,
    fingerprint: str | None,
    index: dict[str, str],
) -> None:
    """Persist the merged index for the next cold build of this
    unchanged install.

    Written to a unique temp file in the cache directory and moved into
    place with ``os.replace`` (the ``apt_dat_reader`` persistence
    pattern): concurrent auto_patch PROCESSES may build the same index
    at the same time, and an atomic rename is what makes every reader
    see either the old file or a complete new one, never a torn write.
    A write failure must never break a build (read-only volume, out of
    space) — swallow it and let the next run rebuild.  An EMPTY index is
    not persisted: it means no ``library.txt`` was found at all (a bogus
    or not-yet-installed root), and rebuilding nothing is free."""
    if not (sidecar_path and fingerprint and index):
        return
    import pickle
    import tempfile
    cache_directory = os.path.dirname(sidecar_path)
    temporary_path = None
    try:
        os.makedirs(cache_directory, exist_ok=True)
        handle_fd, temporary_path = tempfile.mkstemp(
            dir=cache_directory, prefix=".o4_library_index_", suffix=".tmp")
        with os.fdopen(handle_fd, "wb") as sidecar_file:
            pickle.dump({"fingerprint": fingerprint, "index": index},
                        sidecar_file, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temporary_path, sidecar_path)
        temporary_path = None
        _vprint("   [library] index written to the sidecar cache "
                f"({os.path.basename(sidecar_path)})")
    except Exception:
        pass
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


def get_library_index(xplane_root: str) -> dict[str, str]:
    """Return the memoized virtual→physical ``library.txt`` map for an
    X-Plane install.  Built once per ``xplane_root`` and shared across
    all callers in the process.

    On a memo miss the merged index comes from the disk sidecar when its
    fingerprint still matches the install's ``library.txt`` set (see
    :func:`_library_index_sidecar`), so a cold build re-serves it in
    milliseconds instead of re-parsing every ``library.txt``; on any
    mismatch it is rebuilt from the files and rewritten.
    ``O4_LIBRARY_INDEX_CACHE=0`` disables the sidecar entirely (no read,
    no write)."""
    key = os.path.abspath(xplane_root)
    cached = _LIB_INDEX_CACHE.get(key)
    if cached is not None:
        return cached

    # Concurrent threads that miss the memo wait for the first build
    # rather than each parsing all 337 library.txt files.
    with _library_index_lock(key):
        cached = _LIB_INDEX_CACHE.get(key)
        if cached is not None:
            return cached

        sources = _library_source_files(xplane_root)
        sidecar_path, fingerprint = _library_index_sidecar(
            xplane_root, sources)
        index = _read_library_index_sidecar(sidecar_path, fingerprint)
        if index is None:
            index = {}
            # Lowest priority first, so a higher-priority EXPORT of the
            # same virtual path overwrites it.
            for source in sources:
                _parse_library_txt(source, index)
            _write_library_index_sidecar(sidecar_path, fingerprint, index)

        _LIB_INDEX_CACHE[key] = index
        return index


def resolve_library_path(virtual_path: str,
                         xplane_root: str) -> str | None:
    """Resolve a virtual library path to an absolute physical file, or
    None if no ``EXPORT`` provides it / the file is missing."""
    index = get_library_index(xplane_root)
    phys = index.get(virtual_path) or index.get(virtual_path.lower())
    if phys and os.path.isfile(phys):
        return phys
    return None


# ── .agp parsing ─────────────────────────────────────────────────────
def _crop_or_tile_pixels(tile, crop):
    """Return the footprint vertices in texture pixels: the CROP_POLY
    pairs when present, else the four TILE corners.  ``tile`` is
    (left, bottom, right, top); ``crop`` is a flat list of pixel
    coords."""
    if crop and len(crop) >= 6:
        pts = [(crop[i], crop[i + 1])
               for i in range(0, len(crop) - 1, 2)]
        if len(pts) >= 3:
            return pts
    if tile is not None:
        left, bottom, right, top = tile
        return [(left, bottom), (right, bottom),
                (right, top), (left, top)]
    return None


def parse_agp(path: str) -> AgpFootprint | None:
    """Parse an ``.agp`` file into a local-meter footprint polygon
    (memoized by absolute path).  Returns None when the file is missing
    or lacks the fields needed to derive a metric footprint."""
    key = os.path.abspath(path)
    if key in _AGP_CACHE:
        return _AGP_CACHE[key]

    result: AgpFootprint | None = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        _AGP_CACHE[key] = None
        return None

    scale_s = scale_t = None
    tex_w = tex_h = None
    tile = None
    crop = None
    anchor = None
    rotation = 0.0
    # Use the FIRST TILE / CROP_POLY block (an .agp may list several tile
    # variants chosen randomly by the sim; for hangars they share one
    # footprint extent, and the first is representative).
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        tok = line.split()
        kw = tok[0]
        try:
            if kw == "TEXTURE_SCALE" and len(tok) >= 3:
                scale_s, scale_t = float(tok[1]), float(tok[2])
            elif kw == "TEXTURE_WIDTH" and len(tok) >= 2:
                tex_w = float(tok[1])
            elif kw == "TEXTURE_HEIGHT" and len(tok) >= 2:
                tex_h = float(tok[1])
            elif kw == "TILE" and tile is None and len(tok) >= 5:
                tile = (float(tok[1]), float(tok[2]),
                        float(tok[3]), float(tok[4]))
            elif kw == "CROP_POLY" and crop is None and len(tok) >= 7:
                crop = [float(v) for v in tok[1:]]
            elif kw == "ANCHOR_PT" and anchor is None and len(tok) >= 3:
                anchor = (float(tok[1]), float(tok[2]))
            elif kw == "ROTATION" and len(tok) >= 2:
                rotation = float(tok[1])
        except (ValueError, IndexError):
            continue

    # Need a pixel→meter scale and a footprint outline to proceed.
    if not scale_s or tex_w is None:
        _AGP_CACHE[key] = None
        return None
    if tex_h is None:           # assume square pixels when height absent
        tex_h = tex_w
        scale_t = scale_t or scale_s
    if not scale_t:
        scale_t = scale_s
    mpp_x = tex_w / scale_s
    mpp_y = tex_h / scale_t

    pixels = _crop_or_tile_pixels(tile, crop)
    if not pixels:
        _AGP_CACHE[key] = None
        return None
    if anchor is None:
        if tile is not None:
            left, bottom, right, top = tile
            anchor = ((left + right) / 2.0, (bottom + top) / 2.0)
        else:
            xs = [p[0] for p in pixels]
            ys = [p[1] for p in pixels]
            anchor = ((min(xs) + max(xs)) / 2.0,
                      (min(ys) + max(ys)) / 2.0)

    ax, ay = anchor
    local = [((px - ax) * mpp_x, (py - ay) * mpp_y) for px, py in pixels]
    result = AgpFootprint(local_poly=local, rotation=rotation)
    _AGP_CACHE[key] = result
    return result


# ── placement → lon/lat ──────────────────────────────────────────────
_LAT_M_PER_DEG = 111320.0


def _rotate_clockwise(x_east: float, y_north: float,
                      heading_deg: float) -> tuple[float, float]:
    """Rotate a local (east, north) point by an X-Plane heading
    (degrees clockwise from true north)."""
    if heading_deg % 360.0 == 0.0:
        return x_east, y_north
    th = math.radians(heading_deg)
    s, c = math.sin(th), math.cos(th)
    east = x_east * c + y_north * s
    north = -x_east * s + y_north * c
    return east, north


def agp_footprint_lonlat(virtual_path: str,
                         lon: float, lat: float, heading_deg: float,
                         xplane_root: str) -> list[tuple[float, float]] | None:
    """Resolve + parse the ``.agp`` for a placement and return its
    footprint as an (unclosed) list of (lon, lat).  None when the
    resource can't be resolved or parsed."""
    phys = resolve_library_path(virtual_path, xplane_root)
    if phys is None:
        return None
    fp = parse_agp(phys)
    if fp is None or len(fp.local_poly) < 3:
        return None
    # The tile's own ROTATION combines with the DSF placement heading.
    total_heading = heading_deg + fp.rotation
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        return None
    ring: list[tuple[float, float]] = []
    for x_east, y_north in fp.local_poly:
        east, north = _rotate_clockwise(x_east, y_north, total_heading)
        plon = lon + east / (_LAT_M_PER_DEG * cos_lat)
        plat = lat + north / _LAT_M_PER_DEG
        ring.append((plon, plat))
    return ring


def is_agp_building_def(path: str) -> bool:
    """True when an ``OBJECT_DEF`` path is a hangar ``.agp`` we admit as
    a building footprint — restricted (per the initial scope) to the
    ``lib/airport/Common_Elements/Hangars/`` virtual prefix."""
    p = path.lower()
    return (p.endswith(".agp")
            and p.startswith("lib/airport/common_elements/hangars/"))
