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

__all__ = ["XY", "LL", "Key", "Frame", "identity_key", "PROJECTION_DP"]

#: DECIMALS THE PROJECTION IS QUANTISED TO (lane ``xplatdeterminism``,
#: measured 2026-09-17 on release run 35272775466).  The same PROJ 9.5.1
#: and GEOS 3.13.1, the same wheels and the same apt.dat gave the CYXY
#: load stage geometry that agreed to 4 dp (0.1 mm) on macOS/arm64,
#: Linux/x86_64 and Windows/x86_64 and DISAGREED at 6 dp (1 um) — Linux
#: and Windows equal to each other there, macOS apart, which is the
#: arm64/compiler last-ulp signature, not a data difference.  A micron is
#: nothing to the law and everything to a THRESHOLD: one cell flipped at
#: ``classify`` (105/104/105 cells, runway 6/5/6) and from there the three
#: platforms solved different problems — 17128x1933, 17151x1922,
#: 17039x1934 — and shipped different patches.
#:
#: THIS IS A MEASUREMENT ARM, NOT A RATIFIED FIX (lane
#: ``xplatdeterminism``, dispatch 2).  The projection is quantised HERE,
#: at its ONE derivation site, to 0.1 mm — the resolution at which all
#: three platforms' load dumps already AGREED — so that a CI dispatch can
#: answer interventionally whether the divergence really is the
#: projection's last ulp, or something further down.
#:
#: What is already known against it, measured on this tree:
#:  * at 1 mm (3 dp) it breaks ``test_frame_round_trip_cyxy``'s stated
#:    1e-9 deg round-trip contract and moves a pad-relief verdict;
#:  * at 0.1 mm it still breaks ``test_v2padceiling::
#:    test_a_groundside_face_is_not_senior_here``, because quantising xy
#:    breaks ``to_xy(to_ll(xy)) == xy``: the canonical identity join is
#:    lat/lon at 11 dp (~1 um), which is FINER than the quantum, so a
#:    vertex within a micron of a 0.1 mm boundary re-projects into the
#:    neighbouring cell and an identity join misses;
#:  * it changes the surface: CYXY's planar vertices moved 4289 -> 4256
#:    (1 mm) / 4283 (0.1 mm) on one unchanged macOS tree, because the
#:    thresholds downstream sit near degeneracy.
#:
#: So quantising the METRES is in tension with a MICRON-resolution
#: identity in DEGREES.  Whatever ships has to reconcile those two; this
#: constant exists to buy the measurement that says where to reconcile
#: them.
PROJECTION_DP = 4


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
            x, y = fwd.transform(lon, lat)
            # Quantised to PROJECTION_DP — see the constant.  ONE site:
            # the frame is the only thing in v2 that turns lat/lon into
            # metres, so every producer downstream inherits the same
            # numbers on every platform.
            return (round(float(x), PROJECTION_DP),
                    round(float(y), PROJECTION_DP))

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

