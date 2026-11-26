"""ROCK OUTCROPS AND ADDED HILLS ARE TERRAIN SHELLS (owner RULINGS
2026-11-25j, l; #2197 follow-up, #2272 family; spec
``docs/specs/rock-outcrop-witness-20261125.md``).

Owner (2026-11-25T21:54Z): "Rock outcrops should ideally be seated and
matched to terrain like other terrain shell style objects."  A pack may
lay a rock, a boulder field, a berm or a small hill on the ground as a
plain ``OBJECT`` (or ``OBJECT_AGL``) row: relief the AUTHOR adds on top
of the ground, under ``terrain_model.MIN_PLAN_M``, too hard or too
coarsely textured for ``terrain_shell``'s photo-textured candidate.  This
module is the family's ROCK member: it RECOGNISES such an object on its
geometry only (RULINGS 05e: no names, no textures) and hands it to
``terrain_shell``'s one path (one rigid frame, never split, the skirt seat
``shell_seat``, the hide offer ``terrain_model.quality``).  An
``OBJECT_MSL`` row is never a rock: it keeps ``terrain_shell.small_shape``
/ ``small_match`` (TFFJ, TNCS do not move).

THE CANDIDATE (:func:`rock_verdict`): its static solid spans
``terrain_shell.SHELL_MIN_PLAN_M`` or more and less than
``terrain_model.MIN_PLAN_M``; its top spans at least
:data:`ROCK_MIN_RELIEF_M` between its 5th and 95th percentiles; a
HILLSIDE (``relief_skin.MIN_STEEP`` of its cells steeper than
``relief_skin.STEEP_GRADIENT``); at least ``relief_skin.MIN_SHARE`` of
its plan in pieces each spanning ``SHELL_MIN_PLAN_M`` or more
(:func:`big_piece_share`).

THE WITNESS (``rock_witness``): one top sheet standing on its own ground
zero, no storey walls, no right-angle creases, not axis-aligned.  A
candidate it refuses is not a rock (the census lists it with its failing
gates).  A composite of terrain and built parts is not a rock (RULINGS
2026-11-25l (1): it is an ELLX-like partial shell).

ONE RIGID FRAME OF ITS OWN (:func:`own_frame`): every other row sharing
its origin is its content (over its plan), never a scene around it.

THE MATCH (:func:`rock_match`): its datum is the ground under its anchor
plus its ``OBJECT_AGL`` lift (:func:`row_datum`: X-Plane stands such a
row's zero on the terrain at its anchor), and its rim must not FLOAT over
our ground there (``terrain_shell.SHELL_LEVEL_M``; a buried rim is the
skirt's business).  Correlation with the DEM
is not asked: the relief is the author's addition.

THE RUN-OUT FILL (:func:`fill_seat`, spec 4, RULINGS 2026-11-25k/l (3)):
the skirt seat stops at the skirt's depth.  Where, on the DEM, the seat's
worst rim gap exceeds that depth by more than ``terrain_fill.SERVED_M``,
the record carries ``fill_z0`` (its frame zero less the depth: the seat
it will take) and the tile build raises our ground to its rim
(``auto_patch/terrain_cut_stage``, ``terrain_fill.rim_fill``: raise only,
never a patch or tile-edge posting; a support inside the patch is
reported unserved).

Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["ROCK_MIN_RELIEF_M", "big_piece_share", "rock_verdict", "rock_shape", "row_datum",
           "rock_match", "own_frame", "fill_seat"]

ROCK_MIN_RELIEF_M = 5.0


def big_piece_share(covered: np.ndarray, cell_m: float, min_m: float) -> float:
    """ONE BODY, OR A FEW LARGE ONES (module doc): the share of the
    ``covered`` plan cells lying in 8-connected pieces spanning ``min_m``
    or more."""
    from scipy import ndimage
    total = int(covered.sum())
    if not total:
        return 0.0
    lab, _n = ndimage.label(covered, structure=np.ones((3, 3), dtype=bool))
    big = 0
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        span = cell_m * max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
        if span >= min_m:
            big += int((lab[sl] == k).sum())
    return big / total




#: :func:`rock_verdict` per file version (``(path, mtime_ns, size)``): the
#: build's shape test and the census ask it of the same file
_VERDICTS: dict = {}
_VERDICTS_MAX = 512


def rock_verdict(path: str, g: _t.Any) -> "tuple[dict, list[str]] | None":
    """:func:`_verdict`, once per file version."""
    import os
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
    except OSError:
        return _verdict(path, g)
    if key not in _VERDICTS:
        if len(_VERDICTS) >= _VERDICTS_MAX:
            _VERDICTS.clear()
        _VERDICTS[key] = _verdict(path, g)
    return _VERDICTS[key]


def _verdict(path: str, g: _t.Any) -> "tuple[dict, list[str]] | None":
    """``(values, failed gates)`` of an object in a rock's plan and relief
    range (module doc, THE CANDIDATE) on the parsed geometry ``g`` of
    ``path``: ``rock_witness.features`` with ``plan_m``, ``relief_m``,
    ``steep`` and ``big``; the gates failed -- ``hillside``, ``big_pieces``
    (the candidate's; then the witness is not read) or
    ``rock_witness.failed`` at lift 0 -- or ``None`` out of that range."""
    from ..geom.terrain_deck import CELL_M
    from . import relief_skin as _rs
    from . import rock_witness as _rw
    from . import terrain_model as _tm
    from .terrain_shell import SHELL_MIN_PLAN_M
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    plan = _tm._plan_m(g, ROCK_MIN_RELIEF_M)
    if not SHELL_MIN_PLAN_M <= plan < _tm.MIN_PLAN_M or not len(tris):
        return None
    grid = _tm._grid(g)
    if grid is None or not grid.covered.any():
        return None
    lo, hi = np.percentile(grid.top[grid.covered], [5.0, 95.0])
    if hi - lo < ROCK_MIN_RELIEF_M:
        return None
    m = _rs._measures(grid)
    steep = 0.0 if m is None else float(m["steep"])
    big = big_piece_share(grid.covered, CELL_M, SHELL_MIN_PLAN_M)
    values = {"plan_m": float(plan), "relief_m": float(hi - lo), "steep": steep, "big": big}
    fails = (["hillside"] if steep < _rs.MIN_STEEP else []) + \
        (["big_pieces"] if big < _rs.MIN_SHARE else [])
    if fails:                      # no candidate: the witness is not read
        return values, fails
    f = _rw.features(g, _tm._vt_rows(path), grid)
    return dict(f, **values), _rw.failed(f)


def rock_shape(path: str, g: _t.Any) -> "_t.Any | None":
    """A ROCK (module doc) on the parsed geometry ``g`` of ``path`` (one
    ``terrain_shell.small_shape`` refused): a ``terrain_model.Shape`` with
    ``small`` and ``rock`` set and the witness values in ``witness``, or
    ``None``."""
    from . import terrain_model as _tm
    got = rock_verdict(path, g)
    if got is None or got[1]:
        return None
    f = got[0]
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    spread = _tm.photo_spread(g.vertices, _tm._vt_rows(path), tris)
    witness = tuple(sorted((k, v) for k, v in f.items() if k not in ("steep", "big")))
    return _tm.Shape(_tm._grid(g), f["plan_m"], f["relief_m"], spread,
                     _tm.post_m(g.vertices, tris), small=True, rock=True,
                     witness=witness, rock_only=True)


def row_datum(kind: str, elev: _t.Any, xy: tuple[float, float],
              dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
              shape: _t.Any = None) -> "float | None":
    """THE MATCH's datum of a rock's row (module doc): the ground under the
    anchor plus the ``OBJECT_AGL`` lift (0 for a plain row); ``None`` for
    an ``OBJECT_MSL`` row (never a rock), with no ground there, or where
    the lift takes ``shape`` (its ``witness``) off its ground
    (``rock_witness`` ON THE GROUND)."""
    if kind == "OBJECT_MSL":
        return None
    lift = float(elev or 0.0) if kind == "OBJECT_AGL" else 0.0
    if shape is not None and getattr(shape, "witness", ()):
        from . import rock_witness as _rw
        if "on_ground" in _rw.failed(dict(shape.witness), lift):
            return None
    z = float(np.asarray(dem_many(np.array([float(xy[0])]), np.array([float(xy[1])])),
                         dtype=float)[0])
    return z + lift if np.isfinite(z) else None


def own_frame(shape: _t.Any, others: _t.Iterable[_t.Any]) -> bool:
    """ONE RIGID FRAME of its own (module doc): every other row sharing the
    rock's origin (anchor, heading, lift; their parsed geometries
    ``others``, ``None`` unread) is its CONTENT -- the centre of its plan
    lies over the rock's plan (LICR's approach lights on its hillside; a
    row of lights alone has no plan and is content) --
    else the frame is a composite scene (a whole airport exported at one
    zero: LPLA's ground pieces, EGKK's hills among its construction site)
    and the row is not read as a rock (RULINGS 2026-11-25l (1): composites
    are partial shells)."""
    grid = shape.grid
    for g in others:
        if g is None:
            return False
        if not len(g.vertices):          # lights alone: nothing to seat
            continue
        lo, hi = g.vertices.min(axis=0), g.vertices.max(axis=0)
        mid = 0.5 * (lo + hi)
        if not bool(grid.cell_of(np.array([mid[0]]), np.array([mid[2]]))[2][0]):
            return False
    return True


def fill_seat(file: str, xy: tuple[float, float], heading: float, z0: float,
              dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
              ) -> "float | None":
    """THE RUN-OUT FILL (module doc): the rock of OBJ8 ``file`` at frame
    ``xy`` / ``heading`` with its frame zero ``z0``, seated by its skirt
    (``shell_seat.seat_one``) on ``dem_many`` (frame metres): ``fill_z0``
    = ``z0`` less its skirt's depth where its worst rim gap exceeds that
    depth by more than ``terrain_fill.SERVED_M``, else ``None``."""
    from . import shell_seat as _ss
    from .terrain_fill import SERVED_M
    ax, ay = float(xy[0]), float(xy[1])

    def to_ll(e, n):            # the frame as (lon, lat): (east, north)
        return np.asarray(e, float) + ax, np.asarray(n, float) + ay

    def to_xy(x, y):
        return np.asarray(x, float) - ax, np.asarray(y, float) - ay

    pl = _ss.place(file, float(heading), to_xy, to_ll, z0=float(z0))
    if pl is None:
        return None

    def surface(lat, lon):
        return surface.many([lat], [lon])[0]

    def many(lats, lons):
        z = np.asarray(dem_many(np.asarray(lons, float), np.asarray(lats, float)), float)
        return [None if not np.isfinite(v) else float(v) for v in z]
    surface.many = many
    rep = _ss.seat_one(pl, (), surface)
    if rep["gap_before_m"] - rep["depth_m"] <= SERVED_M:
        return None
    return float(z0) - float(rep["depth_m"])


def rock_match(shape: _t.Any, xy: tuple[float, float], heading: float,
               dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray], datum: float,
               fine: "_t.Callable | None" = None, water: "_t.Callable | None" = None
               ) -> "dict[str, float] | None":
    """THE MATCH and THE SEAT of one placement of a rock (module doc):
    ``terrain_model.match``'s record, or ``None``.  Its RIM DOES NOT FLOAT
    at ``datum``: over its outer rim cells, the median of how far its
    bottom stands over the DEM (0 where our ground stands at or over it:
    the edge band may be buried, RULINGS 2026-11-25a (1)) is at most
    ``terrain_shell.SHELL_LEVEL_M``."""
    from . import terrain_model as _tm
    from .terrain_shell import SHELL_LEVEL_M
    grid = shape.grid
    ri, rj = np.nonzero(_tm.outer_rim(grid.covered))
    rx, ry = _tm._world(grid, ri, rj, xy, heading)
    d = np.asarray(dem_many(rx, ry), dtype=float)
    ok = np.isfinite(d)
    if not len(ok) or ok.mean() < 0.9:
        return None
    level = float(np.median(np.maximum(0.0, datum + grid.bot[ri, rj][ok] - d[ok])))
    if level > SHELL_LEVEL_M:
        return None
    z0 = _tm.wet_cap(grid, xy, heading, dem_many, water, datum)
    cover, hideable = _tm.quality(shape, xy, heading, dem_many, fine)
    return {"z0": z0, "corr": 0.0, "peak_err": 0.0, "fit_m": float(np.median(d[ok]) - datum),
            "quality_cover": cover, "hideable": hideable, "level_m": level}
