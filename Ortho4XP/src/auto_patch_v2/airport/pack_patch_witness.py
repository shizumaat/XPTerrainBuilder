"""THE PACK'S OWN ORTHO4XP PATCH IS A WITNESS FOR DECK AND TRENCH LEVELS
(owner RULINGS 2026-11-18f (1): "if there's a custom mesh available,
checking how the author cut it is very helpful"; amends 2026-08-26's "a
pack-shipped mesh patch ... is ground truth for VALIDATING the derived ring,
never a required input"; #2157 KRDU, part C).

A pack may ship the Ortho4XP patch its author built the tile with
(``<pack>/Ortho4XP/Patches/<10 deg>/<tile>/*.patch.osm`` or
``<pack>/Patches/...``).  Its closed ways carry the author's levels:

* ``altitude=Z`` -- a flat PAD at ``Z`` (a trench floor, an airfield
  plateau);
* ``altitude_high=H altitude_low=L`` on a closed five-node way -- a RAMP
  from the short side ``nodes[1:3]`` at ``L`` to the short side
  ``nodes[3], nodes[0]`` at ``H``, linear between them (the reading
  ``O4_Vector_Map`` builds the mesh from).

The patch is READ, never applied: a witness answers what level the author
built at a point (:func:`level_at`), and the readers that consult it compare
or borrow RELATIVE levels -- an author's world may stand metres off this
build's DEM (KRDU: the pack's flat 119 airfield against a 113-124 m lidar
ground).  Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import glob
import math
import os
import typing as _t
import xml.etree.ElementTree as _ET

__all__ = ["Pad", "patch_files", "read_pads", "level_at", "pack_pads"]

LL = tuple[float, float]


class Pad(_t.NamedTuple):
    """One closed patch way: its ring ``(lat, lon)`` and its level -- flat
    (``low == high``, ``ramp`` empty) or a ramp from the ``low`` short side
    to the ``high`` one (``ramp = (low side midpoint, high side midpoint)``)."""

    way_id: str
    ring: tuple[LL, ...]
    low: float
    high: float
    ramp: tuple[LL, ...] = ()


def _tile_dir(lat: int, lon: int) -> str:
    def f(v: int, w: int) -> str:
        return f"{v:+0{w}d}"
    return os.path.join(f(int(math.floor(lat / 10.0)) * 10, 3)
                        + f(int(math.floor(lon / 10.0)) * 10, 4),
                        f(lat, 3) + f(lon, 4))


def patch_files(pack_root: str | None, lat: int, lon: int) -> list[str]:
    """The pack's shipped patch files for tile ``(lat, lon)``, sorted."""
    if not pack_root or not os.path.isdir(pack_root):
        return []
    sub = _tile_dir(lat, lon)
    out: list[str] = []
    for base in ("Ortho4XP/Patches", "Patches"):
        out += glob.glob(os.path.join(pack_root, base, sub, "*.patch.osm"))
    return sorted(set(out))


def _float(v: str | None) -> float | None:
    try:
        return None if v is None else float(v)
    except ValueError:
        return None


def read_pads(path: str) -> list[Pad]:
    """Every closed way of patch ``path`` that states a level."""
    root = _ET.parse(path).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.iter("node")}
    out: list[Pad] = []
    for w in root.iter("way"):
        refs = [nd.get("ref") for nd in w.iter("nd")]
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        if len(refs) < 4 or refs[0] != refs[-1] or any(r not in nodes for r in refs):
            continue
        ring = tuple(nodes[r] for r in refs[:-1])
        alt = _float(tags.get("altitude"))
        if alt is not None:
            out.append(Pad(str(w.get("id")), ring, alt, alt))
            continue
        hi, lo = _float(tags.get("altitude_high")), _float(tags.get("altitude_low"))
        if hi is None or lo is None or len(refs) != 5:
            continue
        low_mid = tuple((a + b) / 2.0 for a, b in zip(ring[1], ring[2]))
        high_mid = tuple((a + b) / 2.0 for a, b in zip(ring[3], ring[0]))
        out.append(Pad(str(w.get("id")), ring, lo, hi, (low_mid, high_mid)))
    return out


def _inside(ring: _t.Sequence[LL], lat: float, lon: float) -> bool:
    hit = False
    n = len(ring)
    for i in range(n):
        (y1, x1), (y2, x2) = ring[i], ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def level_at(pads: _t.Sequence[Pad], lat: float, lon: float) -> float | None:
    """The author's level at ``(lat, lon)``: the pad or ramp holding the
    point (the LAST such way in file order, as the mesh builder lays later
    ways over earlier ones), or ``None`` where the patch says nothing."""
    got = None
    for p in pads:
        if not _inside(p.ring, lat, lon):
            continue
        if not p.ramp:
            got = p.low
            continue
        (la0, lo0), (la1, lo1) = p.ramp
        k = math.cos(math.radians(lat))
        vy, vx = la1 - la0, (lo1 - lo0) * k
        L2 = vx * vx + vy * vy
        s = 0.0 if L2 <= 0.0 else ((lat - la0) * vy + (lon - lo0) * k * vx) / L2
        got = p.low + min(1.0, max(0.0, s)) * (p.high - p.low)
    return got


def pack_pads(pack_root: str | None, lat: int, lon: int) -> list[Pad]:
    """Every level-stating way the pack ships for tile ``(lat, lon)``."""
    out: list[Pad] = []
    for f in patch_files(pack_root, lat, lon):
        try:
            out += read_pads(f)
        except (OSError, _ET.ParseError, ValueError, TypeError):
            continue
    return out


def deck_note(pads: _t.Sequence[Pad], plane: _t.Sequence[LL],
              ring: _t.Sequence[LL]) -> str | None:
    """THE WITNESS LINE of one two-level deck (``rebake_plan``): the
    author's level over its deck plane ``plane`` (the median of the patch
    under its vertices and centre) and the lowest pad level standing inside
    its whole ``ring`` (the trench floor the author cut), and their
    difference -- the depth the author built.  ``None`` where the patch
    says nothing under the deck."""
    if not pads or not plane:
        return None
    n = len(plane)
    pts = list(plane) + [(sum(p[0] for p in plane) / n, sum(p[1] for p in plane) / n)]
    deck = sorted(z for z in (level_at(pads, la, lo) for la, lo in pts) if z is not None)
    floors = [p.low for p in pads if not p.ramp
              and all(_inside(ring, la, lo) for la, lo in p.ring)]
    if not deck:
        return None
    d = deck[len(deck) // 2]
    if not floors:
        return f"pack patch witness: the author's level over the deck plane {d:.2f}"
    f = min(floors)
    return (f"pack patch witness: the author's level over the deck plane {d:.2f}, "
            f"its trench floor {f:.2f} ({d - f:.2f} m under; RULINGS 2026-11-18f)")
