"""THE CONSTANT-DEM ORACLE — the build oracle with no terrain confound.

OWNER LAW (RULINGS 2026-08-05, "there is no lawful-infeasible ground" +
its sharpening): *DEM is a SEED, nothing more.  It seats things within
their feasible bands; it never shapes a band.*  The direct consequence is
an oracle no real-terrain build can give:

    Build a REAL airport's geometry against a CONSTANT DEM and the
    surface must be perfectly lawful.  There is no terrain signal, so
    every emitted violation is a law, solver or instrument defect with
    nothing to blame it on.

TWO SYNTHETIC WORLDS, and they are not interchangeable — the pair is the
instrument:

* ``PLATEAU`` (DEM ≡ 0, or any low constant): the ground is a giant
  plateau *below* nothing.  Every free value is seated at the FLOOR of
  its feasible band.
* ``CANYON`` (DEM ≡ 10 000 m): the ground is high above everything.
  Every free value is seated at the CEILING of its band.

THREE ASSERTIONS the oracle makes, in ascending power:

1. **COMPLIANCE** — zero law-true rows in BOTH worlds.  Necessary, and
   the weakest of the three: a surface can be lawful and still be
   authored by something other than the law.
2. **EXTREME-SEATING SATURATION** — in each world every free node sits at
   the band edge nearest its seed.  A node that is NOT saturated in the
   flat world is being pulled by something that is not the seed: a hidden
   authority.  That is the defect class the oracle exists to catch and
   the one plain compliance cannot see.
3. **THE BAND-WIDTH FIELD** — the per-node difference
   ``canyon(node) - plateau(node)`` IS the width of the feasible band the
   law grants at that node.  Emitted as a diagnostic artifact, it is the
   direct empirical map of the corridor, per node, checkable against the
   analytic bands.  A node whose measured width is 0 is PINNED; one whose
   width disagrees with the analytic band is a law/solver disagreement
   with an exact address.

WHY A SUBSTITUTED SOURCE AND NOT A LAW GATE.  This is an explicit
DEM-source substitution handed to ``build_airport_pavement(tile_dem=...)``
— the same seam Ortho4XP's own ``tile.dem`` uses.  No law changes, no
environment flag alters a rule; the only difference between an oracle
build and a production build is which surface answers ``alt()``.

THE ALL-ZERO REFUSAL STAYS.  ``elevation._load_airport_dem`` refuses a
disk-composed surface that samples zero everywhere, because that means the
base raster is ABSENT (the measurement trap that reported an 85 m error as
real geometry).  That guard is about missing data and is untouched: it
lives in the disk-load branch, while an oracle DEM arrives as
``override_dem`` and is returned before it.  Constant data is not absent
data — but it must be handed over EXPLICITLY, which is exactly what this
module makes callers do.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

__all__ = [
    "ConstantDEM", "PLATEAU_ELEVATION_M", "CANYON_ELEVATION_M",
    "plateau_dem", "canyon_dem", "band_width_field",
    "saturation_report", "SaturationRow",
]

#: The two worlds.  PLATEAU is deliberately NOT 0.0: a literal zero is
#: indistinguishable from "no data" to every defensive check in the tree
#: (and from an uninitialised array), so the low world sits at a small
#: positive constant that is unmistakably a value.  Both are far outside
#: any real airport elevation, so a leaked real sample is obvious.
PLATEAU_ELEVATION_M = 1.0
CANYON_ELEVATION_M = 10000.0


class ConstantDEM:
    """A DEM that answers one elevation everywhere.

    Implements the surface of ``O4_DEM_Utils.DEM`` that ``auto_patch``
    actually consumes — measured by grep, not guessed: ``alt`` (26 call
    sites), ``alt_strict``, ``alt_vec``, ``alt_dem`` +
    ``nxdem``/``nydem``/``x0``/``x1``/``y0``/``y1`` (the OLS raster
    reader), ``nodata``, and the ``lat``/``lon``/``elevation_level``
    identity fields.

    ``nxdem``/``nydem`` default to a 2x2 raster: large enough that the
    raster consumers do not bail, small enough to cost nothing.
    """

    def __init__(self, elevation_m: float,
                 lat: int = 0, lon: int = 0, n: int = 2):
        self.elevation_m = float(elevation_m)
        self.lat = int(lat)
        self.lon = int(lon)
        self.elevation_level = 0
        self.source_path = f"<constant-dem {self.elevation_m:g} m>"
        self.baked_query_active = False
        self.nodata = -32768
        self.nxdem = int(n)
        self.nydem = int(n)
        self.x0, self.x1 = 0.0, 1.0
        self.y0, self.y1 = 0.0, 1.0
        self.subdems = tuple()
        try:
            import numpy as _np
            self.alt_dem = _np.full((self.nydem, self.nxdem),
                                    self.elevation_m, dtype="float32")
        except Exception:                            # pragma: no cover
            self.alt_dem = None

    # ── the sampling surface ──────────────────────────────────────────
    def alt(self, xy) -> float:
        return self.elevation_m

    def alt_strict(self, xy) -> float:
        return self.elevation_m

    def alt_vec(self, x, y=None):
        try:
            import numpy as _np
            arr = _np.asarray(x)
            return _np.full(arr.shape[:1] or (1,), self.elevation_m,
                            dtype="float64")
        except Exception:                            # pragma: no cover
            return [self.elevation_m]

    def get(self, *a, **kw) -> float:
        return self.elevation_m

    def __repr__(self) -> str:                       # pragma: no cover
        return f"ConstantDEM({self.elevation_m:g} m)"


def plateau_dem(lat: int = 0, lon: int = 0) -> ConstantDEM:
    """The LOW world: everything seats at the FLOOR of its band."""
    return ConstantDEM(PLATEAU_ELEVATION_M, lat, lon)


def canyon_dem(lat: int = 0, lon: int = 0) -> ConstantDEM:
    """The HIGH world: everything seats at the CEILING of its band."""
    return ConstantDEM(CANYON_ELEVATION_M, lat, lon)


# ── the two derived instruments ───────────────────────────────────────

def _node_values(layout) -> dict:
    """``{(x, y) rounded: elevation}`` over every value-carrying vertex of
    a layout, keyed on the metre-frame coordinate so the two worlds' node
    sets can be joined by IDENTITY (they are the same geometry: the DEM
    is a seed, so a constant DEM cannot move a vertex in plan).

    Rounded to the millimetre — the canonical registry's own resolution is
    far coarser (0.5 m), so a millimetre key never merges two real nodes
    and never splits one.
    """
    out: dict = {}
    for shape in getattr(layout, "shapes", ()) or ():
        poly = getattr(shape, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        try:
            ring = list(poly.exterior.coords)
        except Exception:                            # pragma: no cover
            continue
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        alts = shape.node_altitudes
        if alts is not None:
            vals = [None if a is None else float(a) for a in alts]
        elif shape.altitude is not None:
            vals = [float(shape.altitude)] * len(ring)
        else:
            continue
        for (x, y), v in zip(ring, vals):
            if v is None:
                continue
            out[(round(float(x), 3), round(float(y), 3))] = v
    return out


def band_width_field(plateau_layout, canyon_layout) -> dict:
    """ASSERTION 3's artifact: ``{(x, y): canyon - plateau}``.

    The per-node difference between the two worlds is the WIDTH of the
    feasible band the law grants at that node — the direct empirical map
    of the corridor, measurable against the analytic bands.

    A width of 0 means the node is PINNED (an authority, a weld, a
    threshold): it has no freedom, and no seed can move it.  A NEGATIVE
    width is a defect on its face — the high world seated a node BELOW the
    low world, which no monotone seating can do.
    """
    lo = _node_values(plateau_layout)
    hi = _node_values(canyon_layout)
    return {k: hi[k] - lo[k] for k in lo.keys() & hi.keys()}


class SaturationRow:
    """One node's seating verdict in one world."""

    __slots__ = ("xy", "value", "floor", "ceil", "world", "saturated")

    def __init__(self, xy, value, floor, ceil, world):
        self.xy = xy
        self.value = float(value)
        self.floor = floor
        self.ceil = ceil
        self.world = world
        edge = floor if world == "plateau" else ceil
        self.saturated = (edge is None
                          or abs(self.value - float(edge)) <= 1e-6)

    def __repr__(self) -> str:                       # pragma: no cover
        return (f"SaturationRow({self.xy}, v={self.value:.3f}, "
                f"[{self.floor}, {self.ceil}], {self.world}, "
                f"sat={self.saturated})")


def saturation_report(layout, world: str, band_of,
                      tol_m: float = 1e-6) -> list:
    """ASSERTION 2: every free node must sit at the band edge nearest its
    seed.

    ``band_of(xy) -> (floor, ceil)`` supplies the analytic band at a node
    (``None`` on either side = unbounded there).  Returns the rows that
    are NOT saturated — i.e. the nodes something other than the seed is
    holding.  An empty list is the pass.

    ``world`` is ``"plateau"`` (seed below ⇒ expect the FLOOR) or
    ``"canyon"`` (seed above ⇒ expect the CEILING).
    """
    if world not in ("plateau", "canyon"):
        raise ValueError(f"world must be plateau|canyon, got {world!r}")
    unsaturated = []
    for xy, value in _node_values(layout).items():
        band = band_of(xy)
        if band is None:
            continue
        floor, ceil = band
        row = SaturationRow(xy, value, floor, ceil, world)
        if not row.saturated:
            unsaturated.append(row)
    return unsaturated


def band_width_summary(field: dict) -> dict:
    """Report shape of a ``band_width_field`` — for the artifact header."""
    if not field:
        return {"nodes": 0}
    widths = sorted(field.values())
    n = len(widths)
    negative = [w for w in widths if w < -1e-6]
    pinned = [w for w in widths if abs(w) <= 1e-6]
    return {
        "nodes": n,
        "pinned": len(pinned),
        "negative": len(negative),
        "min": widths[0],
        "p50": widths[n // 2],
        "max": widths[-1],
        "mean": math.fsum(widths) / n,
    }


def write_band_width_artifact(field: dict, path,
                              extra: Optional[dict] = None) -> None:
    """Persist the band-width field as JSON beside a build."""
    import json
    from pathlib import Path
    doc = {
        "summary": band_width_summary(field),
        "nodes": [{"x": x, "y": y, "band_width_m": round(w, 6)}
                  for (x, y), w in sorted(field.items())],
    }
    if extra:
        doc.update(extra)
    Path(path).write_text(json.dumps(doc, indent=1))


def constant_dem_worlds(lat: int = 0, lon: int = 0) -> Iterable:
    """``[("plateau", dem), ("canyon", dem)]`` — the pair, in the order the
    oracle reports them."""
    return [("plateau", plateau_dem(lat, lon)),
            ("canyon", canyon_dem(lat, lon))]
