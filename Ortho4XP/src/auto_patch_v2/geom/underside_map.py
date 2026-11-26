"""THE UNDERSIDE HEIGHT MAP OF ONE OBJECT GROUP (owner RULINGS 2026-11-25m;
spec ``docs/specs/underside-height-map-20261125.md`` §1).

One record per footprint unit, read from its static solid triangles alone,
in the airport's metric frame, the heights in the unit's AUTHORED frame
(``y`` over the members' own zero): what the group stands on, where its
edge meets the ground and how high the floor behind that edge is.

THE LAYERS (:func:`rasterise_layers`), per cell of a 1 m grid (coarsened so
the grid holds at most :data:`MAX_CELLS`): ``top`` (highest surface),
``low`` (lowest surface), ``floor`` (lowest near-horizontal surface:
``|n_y|`` at least the caller's ``normal_y_min``), ``foot`` (lowest
surface of a GROUNDED part within its contact band: the ground contacts)
and ``tread`` (the HIGHEST near-horizontal surface within that band: the
surface the ground meets -- a slab's top, never its buried underside).
Vectorised and chunked: a terminal is 10^5-10^6 triangles.

THE GROUND-CONTACT PLAN ``P`` (:func:`_contact_plan`): the foot cells and the
SKIN cells (``top - low`` at most :data:`SKIN_M`: a paved sheet, a kerb, a
ramp) standing within ``reach_m`` (a storey) of their nearest foot's
contact and joined to the feet through 4-neighbours whose contact heights
differ by at most :data:`SHEET_STEP_M`.  A roof, a canopy, a deck, a
jetway or a span is cut off by its own height, and a car park's ramp ends
a storey up: OVERHANGS SET NO PERIMETER.  A composite's ground sheet
(read on our DEM by the caller) joins ``P`` whole.

THE PERIMETER STATIONS (:func:`_stations`): every cell of ``P`` with a
4-neighbour outside it (the outer edge and every hole).  Each carries
``lo`` (the lowest outer edge: the cell's lowest surface), ``hi`` (the
median floor of ``P`` within :data:`BEHIND_M` behind it), its contact
height ``h`` (``tread``, else ``foot``, else ``lo``), its KIND --
``skirt`` (the edge goes :data:`SKIRT_M` or more under the floor behind
it), ``wall`` (:data:`WALL_M` or more of solid over the cell), ``sheet``
(a skin) or ``open`` -- and ``levels`` (how many storey levels the floor
behind it stands on).

THE BELOW-GRADE INTERIORS (:func:`_interiors`): cells of ``P`` whose floor
lies :data:`FLOOR_SUNKEN_MIN_M` or more under the contact surface (each
cell reads its nearest station's contact height); 8-connected pieces of at
least :data:`INTERIOR_MIN_CELLS`, ``open`` where under
:data:`ROOFED_COVER_MIN` of the piece has solid over its floor, else
``roofed``.  Kept so they can be cut out (25m (3)), never ignored.

THE SCALARS (:func:`_summarise`): ``t`` -- the floor the AIRSIDE ground
contacts (the plan's foot cells the caller marks airside) stand at: the
plurality floor of their contact heights (:func:`_floor_plane`); when none
is airside, the floor every ground contact stands on.  ``levels`` (the
stations' contact heights' populated storey levels), ``relief`` (their
5th-95th percentile span beyond their least-squares plane) and ``flat``.
(``foot_planes.floor_plane``, the seat's airside-floor reading of zero
CANDIDATES, was tried and reads the wrong plane of contact heights: ELLX
Terminal-A 0.89 against its walls' 0.33 at the apron.)

Pure numpy and scipy: no shapely, no engine type, no law.  Nothing here
names a pack, an object or an airport."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["CELL_M", "MAX_CELLS", "SKIN_M", "SHEET_STEP_M", "BEHIND_M", "WALL_M",
           "SKIRT_M", "FLOOR_SUNKEN_MIN_M", "ROOFED_COVER_MIN", "FLAT_M",
           "KINDS", "Layers", "UndersideMap", "rasterise_layers",
           "compose", "ground_sheet",
           "relief", "underside"]

#: the plan grid (m); a grid that would exceed :data:`MAX_CELLS` coarsens
CELL_M = 1.0
MAX_CELLS = 1_000_000
#: the most cell samples one plan's triangles read before the grid coarsens
#: (RJTT's ground plates: 27 s at 1 m); ``None`` reads every cell
MAX_SAMPLES = 6_000_000
#: a SKIN cell stands no thicker than this, top to lowest surface (m)
SKIN_M = 0.5
#: the most two joined cells of ``P`` differ in contact height (m)
SHEET_STEP_M = 0.5
#: the floor behind a station is read this far inside ``P`` (m)
BEHIND_M = 3.0
#: a WALL station has at least this much solid over it (m)
WALL_M = 2.0
#: a SKIRT station's edge goes at least this far under its floor behind (m)
SKIRT_M = 0.3
#: an interior cell's floor lies at least this far under its contact (m)
FLOOR_SUNKEN_MIN_M = 1.0
#: the least cells of a below-grade interior
INTERIOR_MIN_CELLS = 4
#: an interior is ROOFED from this covered share up (else OPEN)
ROOFED_COVER_MIN = 0.9
#: a unit whose contact relief is at most this is FLAT (m)
FLAT_M = 0.5
#: the station kinds, by code
KINDS = ("open", "sheet", "wall", "skirt")
_OPEN, _SHEET, _WALL, _SKIRT = range(4)


@_dc.dataclass(frozen=True, eq=False)
class Layers:
    """The plan grid of one group: cell ``(i, j)``'s centre is ``(e0 + (j +
    .5) step, n0 + (i + .5) step)``; ``nan`` where nothing stands."""

    e0: float
    n0: float
    step: float
    top: np.ndarray
    low: np.ndarray
    floor: np.ndarray
    foot: np.ndarray
    tread: np.ndarray

    def centres(self, ii: np.ndarray, jj: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Frame metres of the cells ``(ii, jj)``."""
        return self.e0 + (jj + 0.5) * self.step, self.n0 + (ii + 0.5) * self.step


@_dc.dataclass(frozen=True)
class _Interior:
    """One below-grade interior: ``open`` or ``roofed``, its cell count,
    its lowest floor (authored ``y``) and its covered share."""

    kind: str
    cells: int
    floor: float
    cover: float


@_dc.dataclass(frozen=True, eq=False)
class UndersideMap:
    """One group's underside map (module doc).  ``key`` the sorted
    placement row ids; ``unit`` the unit id(s) it was read for.  Station
    arrays are aligned: ``e``/``n`` frame metres, ``lo``/``hi``/``h``
    authored ``y``, ``kind`` codes into :data:`KINDS`, ``levels_k``
    counts, ``airside`` whether the caller read the station as airside."""

    key: tuple[str, ...]
    unit: str
    layers: Layers
    plan: np.ndarray
    e: np.ndarray
    n: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    h: np.ndarray
    kind: np.ndarray
    levels_k: np.ndarray
    airside: np.ndarray
    interiors: tuple[_Interior, ...]
    t: "float | None"
    t_from: str
    levels: tuple[float, ...]
    relief: float
    flat: bool
    #: the unit's authored zero today (its walls' feet median), set by the
    #: caller; ``None`` when not read
    base: "float | None" = None
    #: a recognised COMPOSITE (25l): an origin set whose ground sheet joins
    #: its members into this one map
    composite: bool = False

    @property
    def footless(self) -> bool:
        """No ground contact: today's carriers seat it (spec §1)."""
        return not len(self.e)


def _grid(lo: np.ndarray, hi: np.ndarray, step: float, max_cells: int
          ) -> tuple[float, float, float, int, int]:
    """``(e0, n0, step, ncol, nrow)``: the lattice-aligned grid over the
    plan box ``lo``..``hi``, coarsened to hold at most ``max_cells``."""
    span = np.maximum(hi - lo, step)
    if span[0] * span[1] / (step * step) > max_cells:
        step = float(math.sqrt(span[0] * span[1] / max_cells))
    e0 = math.floor(float(lo[0]) / step) * step
    n0 = math.floor(float(lo[1]) / step) * step
    return e0, n0, step, int((hi[0] - e0) // step) + 1, int((hi[1] - n0) // step) + 1


def rasterise_layers(p: np.ndarray, floor_ok: np.ndarray, foot_max: np.ndarray,
                     step: float = CELL_M, max_cells: int = MAX_CELLS,
                     max_samples: "float | None" = MAX_SAMPLES,
                     feet: "np.ndarray | None" = None,
                     chunk: int = 4_000_000) -> "Layers | None":
    """THE LAYERS (module doc) of the triangles ``p`` ``(n, 3, 3)`` as
    ``(east, north, y)``, binned at cell centres: ``floor_ok`` per triangle
    whether it may be a floor (near-horizontal); ``foot_max`` per triangle
    the highest ``y`` a sample of it is a ground contact (``-inf``: none --
    an elevated part).  ``feet`` ``(k, 3)`` east/north/``y``: the parts'
    own ground feet (``Part.feet``), read as foot samples where they stand
    -- a building of bare walls has no plan area at its feet.  Extends
    ``ground_rim._raster_of`` (one vectorised rasteriser, chunked so a
    terminal never holds 10^8 samples at once)."""
    if not len(p):
        return None
    xy = p[:, :, :2].reshape(-1, 2)
    if feet is not None and len(feet):
        xy = np.concatenate([xy, feet[:, :2]])
    lo, hi = xy.min(0), xy.max(0)
    e0, n0, step, ncol, nrow = _grid(lo, hi, step, max_cells)
    # THE SAMPLE BUDGET: each triangle samples its box's cells, so a plan of
    # wide ground plates coarsens until :data:`MAX_SAMPLES` cells are read
    ext = p[:, :, :2].max(1) - p[:, :, :2].min(1)
    need = float(np.sum((ext[:, 0] / step + 1.0) * (ext[:, 1] / step + 1.0)))
    if max_samples is not None and need > max_samples:
        e0, n0, step, ncol, nrow = _grid(lo, hi, step * math.sqrt(need / max_samples),
                                         max_cells)
    size = nrow * ncol
    top = np.full(size, -np.inf)
    low = np.full(size, np.inf)
    flo = np.full(size, np.inf)
    foot = np.full(size, np.inf)
    tread = np.full(size, -np.inf)
    x, y, z = p[:, :, 0], p[:, :, 1], p[:, :, 2]
    d = (y[:, 1] - y[:, 2]) * (x[:, 0] - x[:, 2]) + (x[:, 2] - x[:, 1]) * (y[:, 0] - y[:, 2])
    c0 = np.maximum(np.ceil((x.min(1) - e0) / step - 0.5).astype(np.int64), 0)
    c1 = np.minimum(np.floor((x.max(1) - e0) / step - 0.5).astype(np.int64), ncol - 1)
    r0 = np.maximum(np.ceil((y.min(1) - n0) / step - 0.5).astype(np.int64), 0)
    r1 = np.minimum(np.floor((y.max(1) - n0) / step - 0.5).astype(np.int64), nrow - 1)
    nc, nr = c1 - c0 + 1, r1 - r0 + 1
    live = np.flatnonzero((np.abs(d) > 1e-12) & (nc > 0) & (nr > 0))
    cnt = (nc * nr)[live]
    starts = np.r_[0, np.cumsum(cnt)]
    k0 = 0
    while k0 < len(live):
        k1 = max(int(np.searchsorted(starts, starts[k0] + chunk, side="right")) - 1, k0 + 1)
        t = np.repeat(live[k0:k1], cnt[k0:k1])
        off = np.arange(len(t)) - np.repeat(starts[k0:k1] - starts[k0], cnt[k0:k1])
        cc = c0[t] + off % nc[t]
        rr = r0[t] + off // nc[t]
        cx, cy = e0 + (cc + 0.5) * step, n0 + (rr + 0.5) * step
        w1 = ((y[t, 1] - y[t, 2]) * (cx - x[t, 2]) + (x[t, 2] - x[t, 1]) * (cy - y[t, 2])) / d[t]
        w2 = ((y[t, 2] - y[t, 0]) * (cx - x[t, 2]) + (x[t, 0] - x[t, 2]) * (cy - y[t, 2])) / d[t]
        inn = (w1 >= -1e-9) & (w2 >= -1e-9) & (1.0 - w1 - w2 >= -1e-9)
        t, w1, w2 = t[inn], w1[inn], w2[inn]
        zz = w1 * z[t, 0] + w2 * z[t, 1] + (1.0 - w1 - w2) * z[t, 2]
        cell = (rr * ncol + cc)[inn]
        np.maximum.at(top, cell, zz)
        np.minimum.at(low, cell, zz)
        fl = floor_ok[t]
        np.minimum.at(flo, cell[fl], zz[fl])
        ft = zz <= foot_max[t]
        np.minimum.at(foot, cell[ft], zz[ft])
        ft &= fl
        np.maximum.at(tread, cell[ft], zz[ft])
        k0 = k1
    if feet is not None and len(feet):
        fc = np.clip(np.floor((feet[:, 0] - e0) / step).astype(np.int64), 0, ncol - 1)
        fr = np.clip(np.floor((feet[:, 1] - n0) / step).astype(np.int64), 0, nrow - 1)
        cell, fy = fr * ncol + fc, feet[:, 2]
        np.minimum.at(foot, cell, fy)
        np.minimum.at(low, cell, fy)
        np.maximum.at(top, cell, fy)
    arrs = []
    for a in (top, low, flo, foot, tread):
        a[~np.isfinite(a)] = np.nan
        arrs.append(a.reshape(nrow, ncol).astype(np.float32))
    return Layers(float(e0), float(n0), float(step), *arrs)


def compose(layers: _t.Sequence["Layers | None"]) -> "Layers | None":
    """The union of several groups' layers on one grid (every one at the
    same ``step`` and lattice): ``top``/``tread`` the max of theirs per
    cell, ``low``/``floor``/``foot`` the min; ``None`` when the steps
    differ."""
    ls = [g for g in layers if g is not None]
    if not ls or len({g.step for g in ls}) != 1:
        return None
    step = ls[0].step
    e0 = min(g.e0 for g in ls)
    n0 = min(g.n0 for g in ls)
    ncol = max(int(round((g.e0 - e0) / step)) + g.top.shape[1] for g in ls)
    nrow = max(int(round((g.n0 - n0) / step)) + g.top.shape[0] for g in ls)
    out = {k: np.full((nrow, ncol), np.nan, dtype=np.float32)
           for k in ("top", "low", "floor", "foot", "tread")}
    for g in ls:
        i0, j0 = int(round((g.n0 - n0) / step)), int(round((g.e0 - e0) / step))
        sl = (slice(i0, i0 + g.top.shape[0]), slice(j0, j0 + g.top.shape[1]))
        for k, pick in (("top", np.fmax), ("low", np.fmin), ("floor", np.fmin),
                        ("foot", np.fmin), ("tread", np.fmax)):
            out[k][sl] = pick(out[k][sl], getattr(g, k))
    return Layers(e0, n0, step, out["top"], out["low"], out["floor"], out["foot"],
                  out["tread"])


def _joined(cand: np.ndarray, level: np.ndarray, step_m: float) -> np.ndarray:
    """Component labels of the grid graph over ``cand`` cells whose
    4-neighbours join when their ``level`` differs by at most ``step_m``."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    ny, nx = cand.shape
    idx = np.arange(ny * nx).reshape(ny, nx)
    lv = np.where(cand, level, np.nan)
    us, vs = [], []
    for a, b in ((np.s_[:, :-1], np.s_[:, 1:]), (np.s_[:-1, :], np.s_[1:, :])):
        with np.errstate(invalid="ignore"):
            ok = cand[a] & cand[b] & (np.abs(lv[a] - lv[b]) <= step_m)
        us.append(idx[a][ok])
        vs.append(idx[b][ok])
    u, v = np.concatenate(us), np.concatenate(vs)
    g = coo_matrix((np.ones(len(u), dtype=np.int8), (u, v)), shape=(ny * nx, ny * nx))
    return connected_components(g, directed=False)[1].reshape(ny, nx)


def _contact(g: Layers) -> np.ndarray:
    """Per cell its contact height: ``tread``, else ``foot``, else ``nan``."""
    return np.where(np.isfinite(g.tread), g.tread, g.foot).astype(float)


def _contact_plan(g: Layers, reach_m: float, sheet: "np.ndarray | None" = None
                 ) -> np.ndarray:
    """THE GROUND-CONTACT PLAN ``P`` (module doc): a boolean grid;
    ``sheet`` a composite's ground sheet on ``g``'s grid."""
    from scipy import ndimage
    foot = np.isfinite(g.foot)
    if not foot.any():
        return foot if sheet is None else sheet & np.isfinite(g.top)
    c = _contact(g)
    ni, nj = ndimage.distance_transform_edt(~foot, return_distances=False,
                                            return_indices=True)
    with np.errstate(invalid="ignore"):
        skin = (np.isfinite(g.top) & ((g.top - g.low) <= SKIN_M)
                & (np.abs(g.top - c[ni, nj]) <= reach_m))
    cand = foot | skin
    level = np.where(foot, c, g.top)
    lab = _joined(cand, level, SHEET_STEP_M)
    P = cand & np.isin(lab, np.unique(lab[foot]))
    return P if sheet is None else P | (sheet & np.isfinite(g.top))


def ground_sheet(top: np.ndarray, ground: np.ndarray, near_m: float, seed_m: float
                 ) -> np.ndarray:
    """THE GROUND SHEET of a plan's ``top`` over the ground ``ground`` (both
    in one frame, ``nan`` uncovered): the cells within ``near_m`` of the
    ground joined (:data:`SHEET_STEP_M` per 4-neighbour) to a cell within
    ``seed_m`` of it -- a continuous surface standing at the ground (a
    composite's paved skirt, 25l); a roof is cut off by its wall."""
    with np.errstate(invalid="ignore"):
        dev = np.abs(top - ground)
        near = np.isfinite(dev) & (dev <= near_m)
        seed = near & (dev <= seed_m)
    if not seed.any():
        return seed
    lab = _joined(near, top, SHEET_STEP_M)
    return near & np.isin(lab, np.unique(lab[seed]))


def _window(vals: np.ndarray, P: np.ndarray, ii: np.ndarray, jj: np.ndarray,
            r: int) -> np.ndarray:
    """``(k, (2r + 1)^2)`` of ``vals`` over ``P`` in the window of radius
    ``r`` cells round each station (``nan`` off ``P`` or off the grid)."""
    pad = np.pad(np.where(P, vals, np.nan), r, constant_values=np.nan)
    di, dj = np.mgrid[-r:r + 1, -r:r + 1]
    return pad[(ii + r)[:, None] + di.ravel()[None, :],
               (jj + r)[:, None] + dj.ravel()[None, :]]


def _stations(g: Layers, P: np.ndarray, storey_m: float) -> dict[str, np.ndarray]:
    """THE PERIMETER STATIONS of ``P`` (module doc): aligned arrays
    ``ii``, ``jj``, ``e``, ``n``, ``lo``, ``hi``, ``h``, ``kind``,
    ``levels``."""
    from scipy import ndimage
    edge = P & ~ndimage.binary_erosion(P, border_value=0)
    ii, jj = np.nonzero(edge)
    e, n = g.centres(ii, jj)
    lo = g.low[ii, jj].astype(float)
    if not len(ii):
        z = np.zeros(0)
        return {"ii": ii, "jj": jj, "e": e, "n": n, "lo": lo, "hi": z, "h": z,
                "kind": np.zeros(0, dtype=np.int8), "levels": np.zeros(0, dtype=np.int16)}
    win = _window(g.floor.astype(float), P, ii, jj, max(1, int(round(BEHIND_M / g.step))))
    fin = np.isfinite(win)
    with np.errstate(all="ignore"):
        hi = np.nanmedian(np.where(fin, win, np.nan), axis=1)
    hi = np.where(np.isfinite(hi), np.maximum(hi, lo), lo)
    c = _contact(g)[ii, jj]
    h = np.where(np.isfinite(c), c, lo)
    tall = (g.top[ii, jj] - g.low[ii, jj]).astype(float)
    kind = np.full(len(ii), _OPEN, dtype=np.int8)
    kind[tall <= SKIN_M] = _SHEET
    kind[tall >= WALL_M] = _WALL
    kind[hi - lo >= SKIRT_M] = _SKIRT
    q = np.where(fin, np.floor(np.where(fin, win, 0.0) / max(float(storey_m), 1e-6)), np.nan)
    srt = np.sort(q, axis=1)
    levels = (np.isfinite(srt[:, :1]).astype(np.int16).ravel()
              + np.sum(np.isfinite(srt[:, 1:]) & (np.diff(srt, axis=1) > 0), axis=1)
              ).astype(np.int16)
    return {"ii": ii, "jj": jj, "e": e, "n": n, "lo": lo, "hi": hi, "h": h,
            "kind": kind, "levels": levels}


def _interiors(g: Layers, P: np.ndarray, st: _t.Mapping[str, np.ndarray]
              ) -> tuple[_Interior, ...]:
    """THE BELOW-GRADE INTERIORS of ``P`` (module doc)."""
    from scipy import ndimage
    if not len(st["ii"]):
        return ()
    mark = np.ones(P.shape, dtype=bool)
    mark[st["ii"], st["jj"]] = False
    ni, nj = ndimage.distance_transform_edt(mark, return_distances=False,
                                            return_indices=True)
    hmap = np.full(P.shape, np.nan)
    hmap[st["ii"], st["jj"]] = st["h"]
    contact = hmap[ni, nj]
    with np.errstate(invalid="ignore"):
        sunk = P & np.isfinite(g.floor) & (g.floor <= contact - FLOOR_SUNKEN_MIN_M)
    lab, _n = ndimage.label(sunk, structure=np.ones((3, 3), dtype=bool))
    out = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        m = lab[sl] == k
        cells = int(m.sum())
        if cells < INTERIOR_MIN_CELLS:
            continue
        with np.errstate(invalid="ignore"):
            cover = float(np.mean((g.top[sl] - g.floor[sl])[m] > SKIN_M))
        out.append(_Interior("roofed" if cover >= ROOFED_COVER_MIN else "open", cells,
                            round(float(np.nanmin(g.floor[sl][m])), 3), round(cover, 3)))
    return tuple(out)


def relief(e: np.ndarray, n: np.ndarray, h: np.ndarray) -> float:
    """The 5th-95th percentile span of ``h`` beyond its least-squares plane."""
    if len(h) < 3:
        return 0.0
    a = np.c_[e - e.mean(), n - n.mean(), np.ones(len(e))]
    coef, *_ = np.linalg.lstsq(a, h, rcond=None)
    lo, hi = np.percentile(h - a @ coef, [5.0, 95.0])
    return float(hi - lo)


def _levels(h: np.ndarray, storey_m: float, min_share: float = 0.1) -> tuple[float, ...]:
    """The populated storey levels of the contact heights ``h``: 0.5 m bins
    holding ``min_share`` of the stations or more, one per storey."""
    if not len(h):
        return ()
    vals, cnt = np.unique(np.round(h * 2.0) / 2.0, return_counts=True)
    out: list[float] = []
    for k in np.argsort(-cnt, kind="stable"):
        if cnt[k] < min_share * len(h):
            break
        if all(abs(float(vals[k]) - w) >= storey_m for w in out):
            out.append(float(vals[k]))
    return tuple(sorted(out))


def _floor_plane(h: np.ndarray, storey_m: float) -> float:
    """THE FLOOR most of the contact heights ``h`` stand on: the median of
    those within :data:`SHEET_STEP_M` of the fullest 0.5 m bin (a plurality
    floor, never a mean of two storeys; ``storey_m`` is not read)."""
    vals, cnt = np.unique(np.round(np.asarray(h) * 2.0) / 2.0, return_counts=True)
    mode = float(vals[int(np.argmax(cnt))])
    return float(np.median(h[np.abs(h - mode) <= SHEET_STEP_M]))


def _summarise(h: np.ndarray, e: np.ndarray, n: np.ndarray, air_feet: np.ndarray,
              storey_m: float, feet: np.ndarray) -> dict[str, _t.Any]:
    """THE SCALARS (module doc): ``t``, ``t_from``, ``levels``, ``relief``,
    ``flat`` of the stations' contact heights ``h``; ``t`` reads
    ``air_feet`` (the contact heights of the plan's ground contacts at
    airside), else ``feet`` (every ground contact's), else ``h``."""
    if not len(h):
        return {"t": None, "t_from": "none", "levels": (), "relief": 0.0, "flat": True}
    rel = relief(e, n, h)
    if len(air_feet):
        t, src = _floor_plane(air_feet, storey_m), "airside"
    elif len(feet):
        t, src = _floor_plane(feet, storey_m), "feet"
    else:
        t, src = _floor_plane(h, storey_m), "all"
    return {"t": t, "t_from": src, "levels": _levels(h, storey_m), "relief": rel,
            "flat": rel <= FLAT_M}


def underside(g: Layers, key: _t.Sequence[str], unit: str,
              near_airside: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
              storey_m: float, sheet: "np.ndarray | None" = None) -> UndersideMap:
    """The whole map of one group's layers ``g`` (module doc);
    ``near_airside(e, n)`` marks the stations standing at airside;
    ``sheet`` a composite's ground sheet on ``g``'s grid."""
    P = _contact_plan(g, storey_m, sheet)
    st = _stations(g, P, storey_m)
    air = (np.asarray(near_airside(st["e"], st["n"]), dtype=bool) if len(st["e"])
           else np.zeros(0, dtype=bool))
    fi, fj = np.nonzero(P & np.isfinite(g.foot))
    feet = _contact(g)[fi, fj]
    fair = (np.asarray(near_airside(*g.centres(fi, fj)), dtype=bool) if len(fi)
            else np.zeros(0, dtype=bool))
    s = _summarise(st["h"], st["e"], st["n"], feet[fair], storey_m, feet)
    return UndersideMap(tuple(key), str(unit), g, P, st["e"], st["n"], st["lo"], st["hi"],
                        st["h"], st["kind"], st["levels"], air, _interiors(g, P, st),
                        s["t"], s["t_from"], s["levels"], s["relief"], s["flat"])
