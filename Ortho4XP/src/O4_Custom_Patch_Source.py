"""Which elevation a custom patch was made for (#2179; the fit of owner
RULINGS 2026-11-19b (2), kept when its re-base and band were retired by
2026-11-23d).

A custom patch (a manual ``*.patch.osm`` other than the patch editor's own
``<ICAO>_edited.patch.osm``) states absolute heights authored over SOME
elevation source -- almost always the coarse base raster of a plain
Ortho4XP build.  Its REFERENCE is found by fit: every source the build
holds is sampled at the patch's height points (pads: closed ways with
``altitude``; ramps: ``altitude_high``/``altitude_low``, matched to the
end edges in the better order) and the smallest median |patch - source|
wins (:func:`_pick_reference`; ``O4_Custom_Patch_Ground`` asks the same
fit to decide which insets an "As made" airport leaves out).

The patch itself is meshed exactly as authored.  The reference is recorded
per file in the build folder (:data:`SOURCES_RECORD`) by
:func:`remember_source`, which ``O4_Vector_Map.include_patches`` calls for
each custom patch it applies; both apps then tell the user once which
elevation the patch was built for, and that higher-resolution elevation
needs our auto patch (``O4_Custom_Patches``).
"""

from __future__ import annotations

import json
import os

import numpy
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

__all__ = ["BUILD_SOURCE", "SOURCES_RECORD", "remember_source"]

#: The name the build's own DEM goes by among the candidates.
BUILD_SOURCE = "build DEM"
#: A source must cover this share of the height points to be a candidate.
_MIN_COVER = 0.8
#: The build folder's record of which elevation each custom patch was
#: built for (#2179), ``{file: {"source", "signature"}}``.
SOURCES_RECORD = "custom_patch_sources.json"


def _height_points(text: str):
    """``(nodes, pads, ramps)`` of a patch's OSM text.  ``nodes`` maps a
    node id to ``(lon, lat)``; a pad is ``(way id, [node ids], altitude)``;
    a ramp ``(way id, [5 node ids], high, low)`` (the 5-node closed way
    ``include_patches`` reads: high end = nodes 3,0, low end = nodes 1,2)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    nodes = {}
    for node in root.iter("node"):
        nodes[node.get("id")] = (float(node.get("lon")),
                                 float(node.get("lat")))
    pads, ramps = [], []
    for way in root.iter("way"):
        refs = [nd.get("ref") for nd in way.iter("nd")]
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        if (len(refs) < 4 or refs[0] != refs[-1]
                or any(r not in nodes for r in refs)):
            continue
        try:
            if "altitude_high" in tags and "altitude_low" in tags:
                if len(refs) == 5:
                    ramps.append((way.get("id"), refs,
                                  float(tags["altitude_high"]),
                                  float(tags["altitude_low"])))
            elif "altitude" in tags:
                pads.append((way.get("id"), refs, float(tags["altitude"])))
        except ValueError:
            continue
    return nodes, pads, ramps


def _ends(nodes, refs):
    """The high and low end-edge middles of a ramp, ``[(lon, lat)] * 2``."""
    pts = numpy.array([nodes[r] for r in refs[:4]])
    return numpy.array([(pts[3] + pts[0]) / 2, (pts[1] + pts[2]) / 2])


def _match(high, low, z):
    """``(dz_high, dz_low)`` = source - patch at a ramp's two end edges, the
    heights matched to the ends in the better order."""
    if abs(high - z[1]) + abs(low - z[0]) < abs(high - z[0]) + abs(low - z[1]):
        return z[1] - high, z[0] - low
    return z[0] - high, z[1] - low


def _height_gaps(nodes, pads, ramps, sample):
    """``(points, source - patch)`` at every height point (NaN where the
    source has no data): a pad's nodes, a ramp's two end-edge middles."""
    pts, gaps = [], []
    for _, refs, alt in pads:
        ring = numpy.array([nodes[r] for r in refs[:-1]])
        pts.extend(ring)
        gaps.extend(sample(ring) - alt)
    for _, refs, high, low in ramps:
        ends = _ends(nodes, refs)
        pts.extend(ends)
        gaps.extend(_match(high, low, sample(ends)))
    return numpy.array(pts, dtype=float), numpy.array(gaps, dtype=float)


def _pick_reference(nodes, pads, ramps, sources):
    """``(name, {name: (median |d|, median, p10, p90)})`` of d = patch -
    source: the source with the smallest median |d| among those covering
    :data:`_MIN_COVER` of the height points (the build DEM wins a tie).
    ``sources`` maps a name to a sampler ``f(lonlat Nx2) -> z`` (NaN
    outside its data)."""
    stats = {}
    for name, sample in sources.items():
        d = -_height_gaps(nodes, pads, ramps, sample)[1]
        ok = numpy.isfinite(d)
        if not d.size or ok.mean() < _MIN_COVER:
            continue
        d = d[ok]
        stats[name] = (float(numpy.median(numpy.abs(d))),
                       float(numpy.median(d)),
                       float(numpy.percentile(d, 10)),
                       float(numpy.percentile(d, 90)))
    if not stats:
        return None, stats
    return min(stats, key=lambda n: (stats[n][0], n != BUILD_SOURCE)), stats


def _dem_sampler(dem, strict):
    """``f(lonlat) -> z`` over a DEM object, NaN outside a strict sub-DEM's
    data."""
    def sample(lonlat):
        rel = numpy.asarray(lonlat, dtype=float) - [dem.lon, dem.lat]
        if strict:
            z = numpy.ravel(dem.alt_vec_strict(rel)).astype(float)
            z[z == dem.nodata] = numpy.nan
            return z
        return numpy.ravel(dem.alt_vec(rel)).astype(float)
    return sample


def _sources(tile):
    """Every elevation source the build holds for the tile, by name: the
    build DEM, the base raster as read before any inset was baked in, and
    each sub-DEM (airport insets, approach rings)."""
    import O4_DEM_Utils as DEM

    dem = tile.dem
    sources = {BUILD_SOURCE: _dem_sampler(dem, False)}
    base = DEM.DEM(tile.lat, tile.lon,
                   (getattr(dem, "source_path", "") or "").split(";")[0],
                   tile.fill_nodata or "to zero",
                   elevation_level=getattr(dem, "elevation_level", "auto"))
    sources["base elevation (%s)" % DEM.base_source_label(base)] = (
        _dem_sampler(base, False))
    for sub in getattr(dem, "subdems", ()) or ():
        name = os.path.basename(getattr(sub, "source_path", "") or "")
        sources[name or "inset"] = _dem_sampler(sub, True)
    return sources


def _remember(tile, name, path, ref):
    """Record which elevation *name* was built for (#2179) in the build
    folder's :data:`SOURCES_RECORD`, keyed by the file's ``[mtime_ns,
    size]``: the build DEM, when it is only the base raster, goes by the
    base's name.  ``O4_Custom_Patches._elevation_notices`` reads it."""
    if not getattr(tile, "build_dir", None) or ref is None:
        return
    dem = getattr(tile, "dem", None)
    if ref == BUILD_SOURCE and not (getattr(dem, "subdems", None) or ()):
        import O4_DEM_Utils as DEM

        ref = "base elevation (%s)" % DEM.base_source_label(dem)
    record_path = os.path.join(tile.build_dir, SOURCES_RECORD)
    try:
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        record = {}
    try:                        # a notice: never a build failure
        st = os.stat(path)
        record[name] = {"source": ref,
                        "signature": [st.st_mtime_ns, st.st_size]}
        os.makedirs(tile.build_dir, exist_ok=True)
        with open(record_path, "w", encoding="utf-8", newline="") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
    except OSError as exc:
        UI.vprint(2, "   custom patch source not recorded (%s)." % exc)


def _fit(tile, path):
    """``(reference, stats)`` of the patch at *path* over every source the
    build holds (:func:`_pick_reference`), or ``None`` when it states no
    height."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    nodes, pads, ramps = _height_points(text)
    if not pads and not ramps:
        return None
    return _pick_reference(nodes, pads, ramps, _sources(tile))


def _is_custom(name):
    return (FNAMES.is_manual_patch_name(name) and name
            != FNAMES.edited_patch_name(FNAMES.patch_file_icao(name)))


def _ground_record(tile, name):
    """The ``O4_Custom_Patch_Ground.grounds`` record of *name*'s airport,
    or ``None`` when grounds() does not name it."""
    import O4_Custom_Patch_Ground as CUSTOM_GROUND

    return CUSTOM_GROUND.grounds(tile).get(FNAMES.patch_file_icao(name))


def remember_source(tile, patch_dir, name):
    """Record which elevation the custom patch *name* was made for (#2179),
    for the apps' notice: ``O4_Custom_Patch_Ground``'s decision when it has
    one for the airport, else the fit over every source the build holds.
    A non-custom patch is not asked.  Never raises: a notice is never a
    build failure."""
    if not _is_custom(name):
        return
    path = os.path.join(patch_dir, name)
    try:
        ground = _ground_record(tile, name)
        if ground is not None:
            _remember(tile, name, path, ground.get("reference"))
        else:
            fit = _fit(tile, path)
            if fit:
                _remember(tile, name, path, fit[0])
    except Exception as exc:
        UI.vprint(2, "   custom patch source not identified (%s)." % exc)
