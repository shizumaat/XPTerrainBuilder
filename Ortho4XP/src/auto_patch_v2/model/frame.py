"""ONE local metric frame per airport (plan §1 row 1).

Every v2 coordinate is ``(x, y)`` metres in a transverse-Mercator frame
whose origin is the airport reference point; the frame carries the
``pyproj`` transformer factory so the loaders (M1) and the emit adapters
are the only places that touch lat/lon.  The canonical vertex identity is
the lat/lon rounded to ``law.emit.identity.coordinate_dp`` places (memory
``canonical-identity-join``) — computed here, once, so every producer
keys the same way.

No shapely / numpy: the frame is arithmetic over floats.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

XY = tuple[float, float]
LL = tuple[float, float]
Key = tuple[float, float]

__all__ = ["XY", "LL", "Key", "Frame", "identity_key"]

#: THE PROJECTION IS **NOT** QUANTISED — and that is a known, MEASURED
#: cross-platform defect, left standing because closing it needs an owner
#: ruling, not a lane's judgement (lane ``xplatdeterminism``, 2026-09-17).
#:
#: MEASURED (release runs 35272775466 and 35274144555, CYXY through the
#: frozen release check, the three platforms' own stage dumps):
#:  * Same PROJ 9.5.1, GEOS 3.13.1, shapely 2.1.2, numpy 2.4.4, scipy
#:    1.17.1, python 3.13.15, same apt.dat.  The LOAD stage's geometry
#:    agrees at 4 dp (0.1 mm) and DIFFERS at 6 dp (1 um).  Linux and
#:    Windows are equal to each other there; macOS/arm64 stands apart.
#:    Nothing but ``to_xy`` runs between the identical input and that
#:    difference, so it is PROJ's compiled forward tmerc, last ulp.
#:  * A micron then becomes a decision: ``classify`` came out 105 / 104 /
#:    105 cells (runway 6 / 5 / 6), and the three platforms solved
#:    17128x1933, 17151x1922 and 17039x1934 and shipped three different
#:    patches.
#:  * INTERVENTIONAL: quantising this function's output to 0.1 mm made
#:    load, classify, planar (including every DEM sample), shapes and
#:    every constraint COUNT byte-identical on all three, and the LP
#:    exactly 17096 x 1926 / 275 rounds everywhere.  Suspect confirmed.
#:
#: WHY IT IS NOT DONE HERE.  Quantising metres breaks
#: ``to_xy(to_ll(xy)) == xy``, and the canonical identity join is lat/lon
#: at ``emit.identity.coordinate_dp`` = 11 dp, i.e. ~1 um — FINER than any
#: quantum that would help, so a vertex within a micron of a cell boundary
#: re-projects into the neighbouring cell and an identity join misses
#: (measured: ``test_v2padceiling::test_a_groundside_face_is_not_senior_here``
#: goes red at both 1 mm and 0.1 mm).  Reconciling them means moving the
#: identity into the metre domain or coarsening ``coordinate_dp`` — a LAW
#: parameter.  The arm is commit ``8615f4f9`` on ``claude/xplatdeterminism``;
#: the standing witness is ``scripts/check_frozen_tile.py --xplat-dump`` /
#: ``--compare``.


def identity_key(lat: float, lon: float, dp: int) -> Key:
    """Canonical identity of a coordinate: ``(round(lat, dp),
    round(lon, dp))``.  Two vertices with equal keys ARE one vertex;
    proximity never joins (RULINGS 2026-08-21 :1708)."""
    return (round(float(lat), dp), round(float(lon), dp))


@_dc.dataclass(frozen=True)
class Frame:
    """The airport's metric frame.

    ``icao``            the airport it serves;
    ``origin``          ``(lat, lon)`` of the frame origin (x = y = 0);
    ``identity_dp``     decimals of the canonical lat/lon key (from law);
    ``crs``             the PROJ string of the local frame (transverse
                        Mercator centred on the origin, metres).

    The transformers are built lazily from ``pyproj`` and cached on the
    instance; a frame is otherwise a plain value and pickles as one.
    """

    icao: str
    origin: LL
    identity_dp: int
    crs: str = ""

    def __post_init__(self) -> None:
        if not self.crs:
            lat, lon = self.origin
            object.__setattr__(
                self, "crs",
                f"+proj=tmerc +lat_0={lat:.9f} +lon_0={lon:.9f} "
                "+k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs")

    def transformers(self) -> tuple[_t.Callable[[float, float], XY],
                                    _t.Callable[[float, float], LL]]:
        """``(to_xy(lon, lat) -> (x, y), to_ll(x, y) -> (lat, lon))``.
        Imported here so ``model`` stays importable without pyproj."""
        from pyproj import Transformer  # local: the only geodesy import
        fwd = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        inv = Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

        def to_xy(lon: float, lat: float) -> XY:
            # THE one site that turns lat/lon into this frame's metres —
            # see the note above on what that costs across platforms.
            x, y = fwd.transform(lon, lat)
            return (float(x), float(y))

        def to_ll(x: float, y: float) -> LL:
            lon, lat = inv.transform(x, y)
            return (float(lat), float(lon))

        return to_xy, to_ll

    def key(self, lat: float, lon: float) -> Key:
        """Canonical identity of a lat/lon in this frame's law."""
        return identity_key(lat, lon, self.identity_dp)


def rotated_rectangle(poly):
    """``poly.minimum_rotated_rectangle`` with the numeric noise silenced.

    shapely 2.1's ``oriented_envelope`` (the numpy path, GEOS < 3.12)
    divides by every hull edge's components and lets numpy emit
    ``divide by zero`` / ``invalid value`` RuntimeWarnings on an
    axis-aligned or zero-length edge before masking the result — the
    rectangle it returns is correct (OTHH: every warned face read a sane
    width, 0.4–426 m).  The app shows engine stderr, so the noise looked
    like a defect (owner, 2026-09-04).  ONE spelling of the guard for
    every caller; degenerate input still returns whatever shapely returns
    (a Point / LineString), which each caller already handles.  ``model``
    imports no geometry library (test_model): the polygon is duck-typed.
    """
    import warnings
    with warnings.catch_warnings():          # numpy routes errstate here
        warnings.simplefilter("ignore", RuntimeWarning)
        return poly.minimum_rotated_rectangle

