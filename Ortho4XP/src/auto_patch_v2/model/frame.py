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

#: THE FRAME HAS TWO PROJECTIONS, AND THE DIFFERENCE BETWEEN THEM IS THE
#: LAW (spec §46, owner 2026-09-17 Q 17d-1; RULINGS 2026-09-17d / 17g).
#:
#:  * :meth:`Frame.entry` — for a coordinate ENTERING the frame from
#:    OUTSIDE (apt.dat, OSM, DSF/OBJ8 placements, footprint rings and
#:    feet; any lat/lon we did not compute ourselves).  The exact
#:    projection, then SNAPPED to ``emit.identity.input_quantum_m``
#:    (1 mm), so the three platforms are fed IDENTICAL doubles.
#:  * :meth:`Frame.transformers` — ``to_xy`` / ``to_ll``, the EXACT
#:    projection, for our OWN geometry.  It is never quantised, so every
#:    round trip of a coordinate we produced stays exact.
#:
#: WHY.  MEASURED (release runs 35272775466, 35274144555, 35283889554,
#: 35285038635 — CYXY through the frozen release check, the three
#: runners' own stage dumps, joined on exact ``float.hex()``):
#:  * Same PROJ 9.5.1, GEOS 3.13.1, shapely 2.1.2, numpy 2.4.4, scipy
#:    1.17.1, python 3.13.15, same apt.dat — and the forward tmerc still
#:    differs.  The spread is NANOMETRES (max 2.11e-9 m, p50 3.6e-10 m,
#:    almost all in northing; it does not grow with distance from the
#:    origin out to 14 km).  Linux and Windows are not equal either (84
#:    of 2,847 coordinates).
#:  * A nanometre became a whole programme: ``classify`` came out
#:    105 / 104 / 105 cells (runway 6 / 5 / 6) and the three platforms
#:    solved 17128x1933, 17151x1922 and 17039x1934 — three patches for
#:    one airport.  The decision is minted DOWNSTREAM, in derived
#:    geometry, not at any snap the pipeline already performs: straddles
#:    at 1e-4 / 1e-3 / 1e-2 / 0.5 m are ZERO of 2,847 on every pair.
#:  * INTERVENTIONAL: with the entering inputs snapped to 1 mm, load,
#:    partition, classify, planar (every DEM sample), shapes and every
#:    constraint agree on all three; 73,528 constraint row values agree
#:    to <= 7.96e-13 m; the LP is 17289 x 1918 / 181 rounds everywhere;
#:    and the emitted patch BODY is byte-identical on all three.
#:
#: WHY IT IS DONE AT ENTRY AND NOWHERE ELSE.  Quantising ``to_xy`` ITSELF
#: breaks ``to_xy(to_ll(xy)) == xy`` while the canonical identity join is
#: lat/lon at ``emit.identity.coordinate_dp`` = 11 dp (~1 um) — finer than
#: any useful quantum, so a vertex within a micron of a cell boundary
#: re-projects into the neighbour and the join misses (arm ``8615f4f9``:
#: ``test_v2padceiling::test_a_groundside_face_is_not_senior_here`` and the
#: 1e-9 deg round-trip twin both red).  Quantising at ENTRY ONLY never
#: touches a coordinate we produced, so that conflict does not arise and
#: THE IDENTITY DOES NOT MOVE (§46 (4) (b)): ``coordinate_dp`` stays 11,
#: ``Vertex.key`` keeps its shape, and the sidecar <-> patch <-> census
#: joins are untouched.  The standing witness is
#: ``scripts/check_frozen_tile.py --xplat-dump`` / ``--compare``, gated in
#: ``release.yml``.


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
                        Mercator centred on the origin, metres);
    ``input_quantum_m`` §46 (4): the grid :meth:`entry` snaps an ENTERING
                        coordinate to, from ``emit.identity.input_quantum_m``.
                        ``0.0`` — the default here, so no module carries a
                        second copy of the law value — means "exact", which
                        is what a synthetic frame in a twin wants.

    The transformers are built lazily from ``pyproj`` and cached on the
    instance; a frame is otherwise a plain value and pickles as one.
    """

    icao: str
    origin: LL
    identity_dp: int
    crs: str = ""
    input_quantum_m: float = 0.0

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
            # THE EXACT projection: our own geometry, round-trip exact.
            # A coordinate ARRIVING from outside goes through ``entry``.
            x, y = fwd.transform(lon, lat)
            return (float(x), float(y))

        def to_ll(x: float, y: float) -> LL:
            lon, lat = inv.transform(x, y)
            return (float(lat), float(lon))

        return to_xy, to_ll

    def entry(self) -> _t.Callable[[float, float], XY]:
        """THE ENTRY PROJECTION (§46 (4) (a)): ``enter(lon, lat) -> (x, y)``
        for a coordinate arriving from OUTSIDE this airport's frame.

        The exact forward projection, then each axis snapped to
        ``input_quantum_m``.  IEEE division, round-half-even and
        multiplication are all exactly rounded and platform-independent,
        so identical inputs give bit-identical outputs on every platform —
        which is the whole claim (§46 (3)).

        ONE derivation site: every consumer the §46 (9) census ruled
        ENTRY calls THIS, never ``transformers()[0]`` with its own snap.
        With ``input_quantum_m`` at 0 it returns the exact function
        UNCHANGED — not a wrapper that happens to be a no-op — so an
        unquantised arm is byte-neutral by construction.
        """
        to_xy = self.transformers()[0]
        # A Frame unpickled from a CAPTURE written before §46 carries no
        # ``input_quantum_m`` at all (pickle restores the ``__dict__`` it
        # was written with), so it replays EXACT — the pre-§46 law, which
        # is the honest answer for a pre-§46 capture.  ``tools/
        # v2_solve_replay.py`` names it on stdout rather than letting it
        # degrade silently (the 2026-09-13 ``v2roadcontact`` class).
        q = float(getattr(self, "input_quantum_m", 0.0) or 0.0)
        if q <= 0.0:
            return to_xy

        def enter(lon: float, lat: float) -> XY:
            x, y = to_xy(lon, lat)
            return (round(x / q) * q, round(y / q) * q)

        return enter

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

