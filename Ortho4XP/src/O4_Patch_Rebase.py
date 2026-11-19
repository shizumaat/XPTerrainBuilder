"""Re-base a custom patch onto the build's elevation (#2173, owner RULINGS
2026-11-19b).

A custom patch (a manual ``*.patch.osm`` other than the patch editor's own
``<ICAO>_edited.patch.osm``) states absolute heights authored over SOME
elevation source -- KASE's over the coarse base ``.hgt`` -- while the build
may mesh the airport over a 1 m lidar inset that sits metres away.  This
module

1. finds the patch's REFERENCE source by fit: every source the build holds
   is sampled at the patch's height points (pads: closed ways with
   ``altitude``; ramps: ``altitude_high``/``altitude_low``, matched to the
   end edges in the better order) and the smallest median |patch - source|
   wins (:func:`_pick_reference`); the patch is re-based only when that is
   not the build DEM;
2. measures the offset build - patch at the height points and low-passes it
   with a Gaussian of :data:`RADIUS_M` (:class:`_OffsetField`), so the
   author's shapes shorter than the radius are kept and the patch meets the
   build DEM over longer ones (measured at KASE: build - reference, the
   plan's first form, carried the coarse source's own detail into the
   patch and widened its spread against the lidar to -3.2..+2.9 m);
3. adds it to every height -- a pad takes the field's mean over its plan
   (one value: it stays flat), a ramp end the field at its end edge -- and
   writes the re-based COPY into the tile's build folder (the user's file
   is never edited), saying one line in the build log.

Whichever way the setting is, the fit's reference is recorded per file in
the build folder (:data:`SOURCES_RECORD`, #2179): both apps then tell the
user once which elevation the patch was built for
(``O4_Custom_Patches``).

The mesh reads the copy through :func:`mesh_path` (``O4_Vector_Map.
include_patches``).  The tile setting :data:`SETTING_KEY` (default on)
turns it off.  Auto patches and the editor's ``_edited`` patch are never
re-based: they are made on the build's own DEM.
"""

from __future__ import annotations

import json
import os
import re
from math import cos, pi

import numpy
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

__all__ = ["SETTING_KEY", "RADIUS_M", "BUILD_SOURCE", "SOURCES_RECORD",
           "mesh_path", "read_path"]

#: The tile setting (Settings > Elevation & Airports, both apps).
SETTING_KEY = "rebase_custom_patches"
#: The offset field's low-pass radius (Gaussian sigma, metres), chosen by
#: measurement at KASE (RULINGS 2026-11-19b): 200 m keeps the change of
#: the height gap between touching pads/ramps at p90 0.12 m (50 m: 0.43 m,
#: max 4.6 m -- new steps) while the pads meet the lidar at median -0.1 m.
RADIUS_M = 200.0
#: The grid step the offset field is sampled on (metres).
STEP_M = 5.0
#: The name the build's own DEM goes by among the candidates.
BUILD_SOURCE = "build DEM"
#: A source must cover this share of the height points to be a candidate.
_MIN_COVER = 0.8
_FOLDER = "custom_patch_rebase"
#: The build folder's record of which elevation each custom patch was
#: built for (#2179), ``{file: {"source", "signature"}}``.
SOURCES_RECORD = "custom_patch_sources.json"
#: The band stays this far inside the tile (degrees, ~1 m): a foot ring
#: on the tile's own edge would repeat its boundary segments.
_BOX_MARGIN_DEG = 1e-5
_M_PER_DEG = 111120.0


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


class _OffsetField:
    """The offset build - patch measured at the height points (``points``,
    ``gaps``), low-passed by a Gaussian of ``radius_m`` on a metric grid
    and normalised over the points; :meth:`at` samples it bilinearly."""

    def __init__(self, points, gaps, radius_m=RADIUS_M, step_m=STEP_M):
        from scipy import ndimage

        ok = numpy.isfinite(gaps)
        points, gaps = points[ok], gaps[ok]
        (lon0, lat0), (lon1, lat1) = points.min(axis=0), points.max(axis=0)
        margin = 3 * radius_m
        self.kx = _M_PER_DEG * cos((lat0 + lat1) / 2 * pi / 180)
        self.lon0 = lon0 - margin / self.kx
        self.lat0 = lat0 - margin / _M_PER_DEG
        self.step = step_m
        shape = (int(((lat1 - lat0) * _M_PER_DEG + 2 * margin) / step_m) + 2,
                 int(((lon1 - lon0) * self.kx + 2 * margin) / step_m) + 2)
        col, row = self._cell(points)
        cells = (numpy.rint(row).astype(int), numpy.rint(col).astype(int))
        num, den = numpy.zeros(shape), numpy.zeros(shape)
        numpy.add.at(num, cells, gaps)
        numpy.add.at(den, cells, 1.0)
        sigma = radius_m / step_m
        num = ndimage.gaussian_filter(num, sigma, mode="nearest")
        den = ndimage.gaussian_filter(den, sigma, mode="nearest")
        self.grid = numpy.where(den > 1e-9, num / numpy.maximum(den, 1e-9),
                                float(numpy.median(gaps)))

    def _cell(self, lonlat):
        return ((lonlat[:, 0] - self.lon0) * self.kx / self.step,
                (lonlat[:, 1] - self.lat0) * _M_PER_DEG / self.step)

    def at(self, lonlat):
        from scipy import ndimage

        col, row = self._cell(numpy.atleast_2d(
            numpy.asarray(lonlat, dtype=float)))
        return ndimage.map_coordinates(self.grid, [row, col], order=1,
                                       mode="nearest")

    def over(self, ring):
        """The field at the ring's nodes and at the grid posts inside it."""
        from shapely import contains_xy, geometry

        ring = numpy.asarray(ring, dtype=float)
        pol = geometry.Polygon(ring)
        lon0, lat0, lon1, lat1 = pol.bounds
        xs = numpy.arange(lon0, lon1, self.step / self.kx)
        ys = numpy.arange(lat0, lat1, self.step / _M_PER_DEG)
        pts = ring
        if xs.size and ys.size and pol.is_valid:
            gx, gy = numpy.meshgrid(xs, ys)
            inside = contains_xy(pol, gx.ravel(), gy.ravel())
            pts = numpy.vstack([ring, numpy.column_stack(
                [gx.ravel()[inside], gy.ravel()[inside]])])
        return self.at(pts)


_WAY_RE = re.compile(r"<way\b[^>]*\bid=['\"]([^'\"]+)['\"]")
_TAG_RE = re.compile(
    r"(<tag\s+k=['\"](altitude|altitude_high|altitude_low)['\"]\s+"
    r"v=['\"])([^'\"]*)(['\"])")


def _rebase_text(text, field, nodes, pads, ramps):
    """``(new text, stats)``: every pad ``altitude`` plus the field's mean
    over its plan, every ramp's ``altitude_high``/``altitude_low`` plus the
    field at its end edge; every other byte as authored.  ``stats``:
    ``added`` (every added offset), ``pad_spread`` (max - min of the field
    over each pad: how far a pad would tilt if it were not one height)."""
    new, added, spread = {}, [], []
    for wid, refs, alt in pads:
        values = field.over([nodes[r] for r in refs])
        added.append(float(values.mean()))
        spread.append(float(values.max() - values.min()))
        new[wid] = {"altitude": alt + added[-1]}
    for wid, refs, high, low in ramps:
        hi, lo = field.at(_ends(nodes, refs))
        added.extend([hi, lo])
        new[wid] = {"altitude_high": high + hi, "altitude_low": low + lo}

    def swap(current, tag):
        if tag.group(2) not in current:
            return tag.group(0)
        return tag.group(1) + "%.2f" % current[tag.group(2)] + tag.group(4)

    out, current = [], None
    for line in text.splitlines(keepends=True):
        match = _WAY_RE.search(line)
        if match:
            current = new.get(match.group(1))
        if current:
            line = _TAG_RE.sub(lambda t: swap(current, t), line)
        if "</way>" in line:
            current = None
        out.append(line)
    return "".join(out), {"added": numpy.array(added, dtype=float),
                          "pad_spread": numpy.array(spread, dtype=float)}


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
    """``(text, nodes, pads, ramps, sources, reference, stats)`` of the
    patch at *path*, or ``None`` when it states no height."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    nodes, pads, ramps = _height_points(text)
    if not pads and not ramps:
        return None
    sources = _sources(tile)
    ref, stats = _pick_reference(nodes, pads, ramps, sources)
    return text, nodes, pads, ramps, sources, ref, stats


def _is_custom(name):
    return (FNAMES.is_manual_patch_name(name) and name
            != FNAMES.edited_patch_name(FNAMES.patch_file_icao(name)))


def _copy_path(tile, name):
    return os.path.join(tile.build_dir, _FOLDER, name)


def mesh_path(tile, patch_dir, name):
    """The path ``include_patches`` reads *name* from: for a custom patch
    (setting on) the COPY in the build folder -- re-based when its
    reference is not the build DEM, and carrying the blend band around its
    pavement (``O4_Patch_Band``) -- else the file itself.  The file itself
    too when the airport stands on the elevation its patch was made for
    (``O4_Custom_Patch_Ground.grounds``, RULINGS 2026-11-19n (2)): as
    authored, no re-base, no band.  Never raises: a failure keeps the
    user's file and says so."""
    path = os.path.join(patch_dir, name)
    if (not _is_custom(name) or not getattr(tile, SETTING_KEY, True)
            or _on_its_source(tile, name)):
        _drop_copy(tile, name)
        if _is_custom(name):
            try:                # #2179: the notice names the source
                fit = _fit(tile, path)
                if fit:
                    _remember(tile, name, path, fit[5])
            except Exception as exc:    # a notice: never a build failure
                UI.vprint(2, "   custom patch source not identified (%s)."
                          % exc)
        return path
    try:
        return _prepared(tile, path, name) or path
    except Exception as exc:  # the user's patch still builds as authored
        _drop_copy(tile, name)
        UI.vprint(0, "   %s: custom patch not re-based (%s: %s)."
                  % (FNAMES.patch_file_icao(name), type(exc).__name__, exc))
        return path


def _on_its_source(tile, name):
    import O4_Custom_Patch_Ground as CUSTOM_GROUND

    return FNAMES.patch_file_icao(name) in CUSTOM_GROUND.grounds(tile)


def read_path(tile, patch_dir, name):
    """The path every later reader of the patch rings takes *name* from
    (``O4_Bank_Annulus``): the copy :func:`mesh_path` wrote for this
    build when there is one, else the file itself."""
    if getattr(tile, "build_dir", None) and _is_custom(name):
        copy = _copy_path(tile, name)
        if os.path.exists(copy):
            return copy
    return os.path.join(patch_dir, name)


def _drop_copy(tile, name):
    """A copy an earlier build wrote must not outlive the decision."""
    if not getattr(tile, "build_dir", None):
        return
    for path in (_copy_path(tile, name), _copy_path(tile, name) + ".json"):
        try:
            os.remove(path)
        except OSError:
            pass


def _prepared(tile, path, name):
    fit = _fit(tile, path)
    if fit is None:
        _drop_copy(tile, name)
        return None
    text, nodes, pads, ramps, sources, ref, stats = fit
    _remember(tile, name, path, ref)
    icao = FNAMES.patch_file_icao(name)
    report = {"reference": ref, "fit": stats, "radius_m": RADIUS_M}
    if ref is None or ref == BUILD_SOURCE:
        UI.vprint(1, "   %s: custom patch fits the build DEM; not re-based."
                  % icao)
    else:
        field = _OffsetField(*_height_gaps(nodes, pads, ramps,
                                         sources[BUILD_SOURCE]))
        text, out = _rebase_text(text, field, nodes, pads, ramps)
        nodes, pads, ramps = _height_points(text)
        median = float(numpy.median(out["added"]))
        report.update({"median_added_m": median,
                       "pad_spread_max_m": float(out["pad_spread"].max(
                           initial=0.0))})
        UI.vprint(0, "   %s: custom patch re-based from %s to the %s "
                  "(median %+.1f m); the tile setting \"Move custom patches "
                  "onto this build's elevation?\" turns it off."
                  % (icao, ref, BUILD_SOURCE, median))
    text = _with_band(tile, text, nodes, pads, ramps, sources, report, icao)
    target = _copy_path(tile, name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    with open(target + ".json", "w", encoding="utf-8",
              newline="") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)
    return target


def _with_band(tile, text, nodes, pads, ramps, sources, report, icao):
    """*text* with the blend band's foot rings (``O4_Patch_Band``), the
    band's widths in *report*, one log line."""
    import O4_Patch_Band as BAND

    margin = _BOX_MARGIN_DEG
    rings, out = BAND.band_rings(
        nodes, pads, ramps, sources[BUILD_SOURCE],
        box=(tile.lon + margin, tile.lat + margin, tile.lon + 1 - margin,
             tile.lat + 1 - margin))
    widths = out["widths"]
    if not rings or not widths.size:
        return text
    p50, p90 = (float(v) for v in numpy.percentile(widths, [50, 90]))
    report["band"] = {"rings": len(rings),
                      "holes": sum(1 for _, hole in rings if hole),
                      "width_p50_m": p50, "width_p90_m": p90,
                      "width_max_m": float(widths.max())}
    UI.vprint(0, "   %s: custom patch pavement blends into the %s over a "
              "band %.0f m wide (p90 %.0f m); the ground beyond keeps the "
              "%s." % (icao, BUILD_SOURCE, p50, p90, BUILD_SOURCE))
    return BAND.band_osm(text, rings)
