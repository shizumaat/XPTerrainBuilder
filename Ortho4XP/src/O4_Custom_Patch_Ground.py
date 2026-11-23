"""An airport on its custom patch stands on the elevation the patch was
made for (#2179 option (a) "as made"; owner RULINGS 2026-11-19n (2)).

A custom patch (a manual ``*.patch.osm`` other than the patch editor's own
``<ICAO>_edited.patch.osm``) states absolute heights its author laid over
SOME elevation source -- almost always the base raster of a plain Ortho4XP
build.  The owner (2026-11-19T13:44Z): "if they choose to use the custom
patch, we use the matching elevation source for the area around that
airport", and every auto-patched airport on the same tile keeps its lidar.

For each airport of the tile using its custom patch, :func:`grounds` finds
the patch's REFERENCE by the 19b fit (``O4_Custom_Patch_Source._pick_reference``:
the smallest median |patch - source| over the patch's height points, among
the base raster and each of the airport's OWN cached insets, read from
disk before any composite exists).  Then:

* reference = the base raster: the airport's own sub-DEMs -- its insets
  and its approach rings -- are LEFT OUT of the build (:func:`left_out`),
  whole, so around the airport the tile is the base raster exactly as a
  plain Ortho4XP build makes it.  ONE list, read by
  ``O4_Airport_Elevation_Insets.bake_candidate_inset_paths`` (the query
  composite, the ``.alt`` bake, the threshold plan and every later reader
  of "which insets does this raster carry") and by
  ``O4_Elevation_Level.resolve_approach_ring_plan`` (ring holders; another
  airport's ring region is cut back from the patch hull grown by
  :data:`HULL_MARGIN_M`, and its existing feather ramps it there);
* reference = one of its own insets: the lidar stays (the patch was made
  on it).

Either way the patch is meshed as authored (the 19b re-base and band are
retired, RULINGS 2026-11-23d).  Only an airport that uses its custom patch
"As made" is asked (``O4_Custom_Patch_Use``); one on "Our auto patch" keeps
its insets like any auto-patched airport.  Decisions are disk-state driven (patch files, cached insets, the
base raster), so the vector step, the mesh step, the frame check and a
pool child all derive the same list; a process keeps them in a memo keyed
by that state.  The working-grid ballot still counts every cached inset,
so the tile's posting -- and every other airport's raster -- is unchanged.
"""

from __future__ import annotations

import os

import numpy
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

__all__ = ["HULL_MARGIN_M", "grounds", "left_out"]

#: The patch hull is grown by this much (metres) to cut ANOTHER airport's
#: approach-ring region back from it (spec custom-patch-choice-2179 §2.4,
#: §3): the ground the author's world reaches past the outermost ring.
HULL_MARGIN_M = 150.0
#: The reference name of the base raster when the airport holds no inset
#: (no fit is needed: the base is the only source there is).
_BASE = "base elevation"

_MEMO: dict = {}


def _custom_files(lat, lon):
    """``{ICAO: [path]}`` of the tile's custom patches used "As made"
    (``O4_Custom_Patch_Use``, #2179: an airport on "Our auto patch" keeps
    its lidar).  An airport that also carries the patch editor's
    ``_edited`` patch is left out: that one was made on this build's own
    elevation."""
    import O4_Custom_Patch_Use as CUSTOM_USE

    directory = FNAMES.patch_dir(lat, lon)
    edited = {FNAMES.patch_file_icao(name)
              for name in CUSTOM_USE.applied_manual_files(directory)
              if name == FNAMES.edited_patch_name(FNAMES.patch_file_icao(name))}
    return {icao: [os.path.join(directory, name) for name in names]
            for (icao, names) in CUSTOM_USE.as_made_files(directory).items()
            if icao not in edited}


def _own_insets(tile, icao):
    import O4_Airport_Elevation_Insets as INSETS

    return INSETS.cached_inset_paths_for_airport(tile, icao)


def _stamp(paths):
    out = []
    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            continue
        out.append((path, st.st_mtime_ns, st.st_size))
    return tuple(out)


def _base_token(tile):
    import O4_DEM_Utils as DEM

    return (DEM.drop_missing_pinned_files(getattr(tile, "custom_dem", "")
                                          or "") or "").split(";")[0]


def _key(tile, files):
    import O4_DEM_Utils as DEM

    insets = {icao: _own_insets(tile, icao) for icao in files}
    key = (int(tile.lat), int(tile.lon), _base_token(tile),
           str(getattr(tile, "elevation_level", "auto")),
           str(getattr(tile, "fill_nodata", "")), DEM.is_cached(tile),
           tuple((icao, _stamp(files[icao]), _stamp(insets[icao]))
                 for icao in sorted(files)))
    return key, insets


def _height_points(paths):
    """The 19b reader's ``(nodes, pads, ramps)`` over every file of one
    airport, node ids prefixed by file so two files never share one."""
    import O4_Custom_Patch_Source as REBASE

    nodes, pads, ramps = {}, [], []
    for k, path in enumerate(paths):
        with open(path, encoding="utf-8") as handle:
            n, p, r = REBASE._height_points(handle.read())
        tag = "%d:" % k
        nodes.update({tag + i: xy for i, xy in n.items()})
        pads += [(tag + w, [tag + i for i in refs], z) for w, refs, z in p]
        ramps += [(tag + w, [tag + i for i in refs], hi, lo)
                  for w, refs, hi, lo in r]
    return nodes, pads, ramps


def _sources(tile, insets):
    """``{name: sampler}``: the base raster as a plain build reads it, and
    each of the airport's own insets (NaN outside its data)."""
    import O4_DEM_Utils as DEM
    import O4_Custom_Patch_Source as REBASE

    dem = DEM.DEM(tile.lat, tile.lon, ";".join([_base_token(tile)] + insets),
                  getattr(tile, "fill_nodata", None) or "to zero",
                  elevation_level=getattr(tile, "elevation_level", "auto"))

    def base(lonlat):
        rel = numpy.asarray(lonlat, dtype=float) - [dem.lon, dem.lat]
        return numpy.ravel(dem.alt_vec_nostrict(rel)).astype(float)

    label = DEM.base_source_label(dem)
    sources = {"%s (%s)" % (_BASE, label) if label else _BASE: base}
    for sub in getattr(dem, "subdems", ()) or ():
        name = os.path.basename(getattr(sub, "source_path", "") or "")
        sources[name] = REBASE._dem_sampler(sub, True)
    return sources


def _area(nodes):
    """The patch's hull grown by :data:`HULL_MARGIN_M` (EPSG:4326)."""
    from elevation_access import las_tiles
    from shapely.geometry import MultiPoint

    hull = MultiPoint(list(nodes.values())).convex_hull
    return las_tiles._buffer_geometry_m(hull, HULL_MARGIN_M)


def _decide(tile, icao, paths, insets):
    """One airport's record: ``reference`` (the source name), ``fit``
    (``{name: (median |d|, median, p10, p90)}``), ``left_out`` (True when
    the reference is the base raster), ``area`` (:func:`_area`)."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_DEM_Utils as DEM
    import O4_Custom_Patch_Source as REBASE

    insets = [p for p in insets if not INSETS._declined_on_read(p)]
    nodes, pads, ramps = _height_points(paths)
    if not pads and not ramps:
        return None
    record = {"reference": _BASE, "fit": {}, "area": _area(nodes)}
    if insets:
        if not DEM.is_cached(tile):
            return None         # decided once the base is on disk
        ref, fit = REBASE._pick_reference(nodes, pads, ramps,
                                          _sources(tile, insets))
        if ref is None:
            return None
        record.update(reference=ref, fit=fit)
    record["left_out"] = record["reference"].startswith(_BASE)
    _say(icao, record, insets)
    return record


def _say(icao, record, insets):
    fit = record["fit"]
    ref = record["reference"]
    others = "; ".join("%s %.1f m" % (name, fit[name][0])
                       for name in sorted(fit) if name != ref)
    how = (" (median |d| %.1f m%s)" % (fit[ref][0], "; " + others
                                       if others else "")
           if ref in fit else "")
    if record["left_out"] and insets:
        UI.vprint(0, "   %s: the custom patch was made for the %s%s; the "
                  "airport stands on it: its own elevation inset(s) %s and "
                  "approach rings are left out, the patch is meshed as "
                  "authored.  Other airports keep their lidar."
                  % (icao, ref, how, ", ".join(
                      os.path.basename(p) for p in insets)))
    else:
        UI.vprint(1, "   %s: the custom patch was made for the %s%s; "
                  "meshed as authored on it." % (icao, ref, how))


def grounds(tile) -> dict:
    """``{ICAO: record}`` for every airport of *tile* using its custom
    patch whose reference the fit found (see the module docstring).  An
    airport the fit cannot decide yet (no height in its patch, the base not
    on disk, an unreadable file) is absent: nothing of it is left out.
    Never raises."""
    try:
        files = _custom_files(tile.lat, tile.lon)
        if not files:
            return {}
        key, insets = _key(tile, files)
    except Exception as exc:    # a decision, never a build failure
        UI.vprint(1, "   Custom patch ground: not decided (%s: %s)."
                  % (type(exc).__name__, exc))
        return {}
    if key not in _MEMO:
        out = {}
        for icao in sorted(files):
            try:
                record = _decide(tile, icao, files[icao], insets[icao])
            except Exception as exc:
                UI.vprint(1, "   %s: custom patch ground not decided "
                          "(%s: %s)." % (icao, type(exc).__name__, exc))
                record = None
            if record is not None:
                out[icao] = record
        _MEMO[key] = out
    return _MEMO[key]


def left_out(tile) -> dict:
    """``{ICAO: area}`` of the airports whose own insets and approach
    rings the build leaves out (their custom patch was made for the base
    raster); ``area`` is the patch hull grown by :data:`HULL_MARGIN_M`."""
    return {icao: record["area"] for icao, record in grounds(tile).items()
            if record["left_out"]}
