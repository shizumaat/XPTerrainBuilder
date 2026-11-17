"""THE PAVEMENT A GENERATED DECK CARRIES (#2141; owner 2026-11-17: "the
deck surface matches the pavement it carries" -- a runway deck gets the
runway's apt.dat surface, a taxiway deck its taxiway's).

The apt.dat surface code of the pavement under a deck's ring -- the row
``110`` polygon covering most of it (a taxiway deck), or the row ``100``
runway strip (a runway deck) -- and X-Plane's own page for that code:
``lib/airport/default_runways/<shade>/{taxiway,runway}.pol``, the page
X-Plane drapes for the apt.dat pavement beside the deck.  The shade of a
code is X-Plane's apt.dat 1200 specification ("Surface Type Codes",
developer.x-plane.com, read 2026-11-17): 20-23 light asphalt, 1 / 24-26
asphalt, 27-30 darker, 31-34 very dark, 35-38 near black; 50-52 light
concrete, 2 / 53-54 concrete, 55-57 dark.  The wear variants inside a
shade (plain / worn / patched / dirty) are not told apart: the shade's
base page.  A code with no paved page (turf, dirt, water ...) reads
``None`` and the deck keeps ``[deck_gen] concrete_pol``.  Nothing here
names an airport.

Build-time impact: one apt.dat block parse per object-stage write.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon

__all__ = ["surface_page", "carried_surface", "carried_runway"]

_SHADES: tuple[tuple[range, str], ...] = (
    (range(20, 24), "asphalt_L"), (range(24, 27), "asphalt"), (range(27, 31), "asphalt_D"),
    (range(31, 35), "asphalt_D2"), (range(35, 39), "asphalt_D3"),
    (range(50, 53), "concrete_L"), (range(53, 55), "concrete"), (range(55, 58), "concrete_D"),
)


def _shade_of(code: int) -> "str | None":
    """The ``default_runways`` folder of apt.dat surface ``code``, ``None``
    for an unpaved or unknown code (module doc)."""
    code = int(code)
    if code == 1:
        return "asphalt"
    if code == 2:
        return "concrete"
    return next((name for rng, name in _SHADES if code in rng), None)


def surface_page(code: int, family: str) -> "str | None":
    """The library path of X-Plane's page for ``code`` on a ``family``
    deck (``"runway"`` reads the runway page, anything else the taxiway
    page); ``None`` for an unpaved code."""
    shade = _shade_of(code)
    if shade is None:
        return None
    kind = "runway" if family == "runway" else "taxiway"
    return f"lib/airport/default_runways/{shade}/{kind}.pol"


def _runway_strip(rw) -> Polygon:
    (_d0, la0, lo0, *_r0), (_d1, la1, lo1, *_r1) = rw.ends
    half = float(rw.width_m) / 2.0
    # metres -> degrees at the runway's latitude (a strip's own scale)
    k_lat = 1.0 / 111320.0
    k_lon = k_lat / max(math.cos(math.radians((la0 + la1) / 2.0)), 1e-6)
    line = LineString([(lo0 / k_lon, la0 / k_lat), (lo1 / k_lon, la1 / k_lat)])
    strip = line.buffer(half, cap_style="flat")
    return Polygon([(x * k_lon, y * k_lat) for x, y in strip.exterior.coords])


def carried_runway(apt, ring_ll: Polygon):
    """The row-100 runway (``apt_dat.AptRunway``) whose paved strip
    covers most of ``ring_ll`` (lon, lat), ``None`` when no runway's strip
    meets it -- the runway a deck carries, whatever its family."""
    best = None
    for rw in getattr(apt, "runways", ()) or ():
        strip = _runway_strip(rw)
        if not strip.is_valid:
            continue
        a = strip.intersection(ring_ll).area
        if a > 0.0 and (best is None or a > best[0]):
            best = (a, rw)
    return None if best is None else best[1]


def carried_surface(apt, ring_ll: Polygon, family: str) -> "int | None":
    """The apt.dat surface code of the pavement a deck carries: for a
    ``runway`` deck the row-100 runway covering most of ``ring_ll`` (lon,
    lat), else the row-110 polygon covering most of it; ``None`` when
    nothing paved covers it (``apt`` an ``apt_dat.AptAirport``)."""
    if family == "runway":
        rw = carried_runway(apt, ring_ll)
        if rw is not None and _shade_of(rw.surface) is not None:
            return int(rw.surface)
    best: "tuple[float, int] | None" = None
    for pv in getattr(apt, "pavements", ()) or ():
        if not pv.rings or len(pv.rings[0]) < 3 or _shade_of(pv.surface) is None:
            continue
        p = Polygon(pv.rings[0], [r for r in pv.rings[1:] if len(r) >= 3])
        p = p if p.is_valid else p.buffer(0.0)
        a = p.intersection(ring_ll).area
        if a > 0.0 and (best is None or a > best[0]):
            best = (a, int(pv.surface))
    return None if best is None else best[1]
