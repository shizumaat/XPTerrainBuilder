"""Adjacent-ground ZONE regions (RULINGS 2026-08-01 zone law; memory
``adjacent-ground-zone-law``; ``law/zones.toml``).

Around every runway-family and taxi-family face: zone 1 (the lip,
``lip_width_m`` out from the pavement edge) and zone 2 (the graded band
out to ``zone2_half_width_m`` for the class); beyond zone 2 the DEM is
untouched, so no face exists there.  Zone regions are ``graded_strip``
faces (a non-value role: they trace a lawful bound) carrying the class
that keys the law (``code_number`` for runways, ``code_letter`` for
taxiways) so the M2 zone generator can call ``zone_bounds``.

Seniority: the runway family's strip claims first (``strip area never
apron population``, RULINGS :1672), then the taxi family's; pavement,
pads and roads are never strip.  Buffers are mitred so the rings stay
arc-free (v1 groundside clip convention).
"""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..classify.roles import TAXI_FAMILY, Cell
from ..law import Law
from ..law.tables import zone2_half_width_m

__all__ = ["ZoneRegion", "zone_regions"]

RUNWAY_FAMILY = ("runway", "runway_crossing")
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass(frozen=True)
class ZoneRegion:
    """One zone face source."""

    ref: str
    polygon: Polygon
    zone: int
    family: str
    code_number: int | None
    code_letter: str | None


def zone_regions(cells: tuple[Cell, ...], law: Law) -> list[ZoneRegion]:
    """Zone 1 / zone 2 regions around the airside runway and taxi faces,
    minus every cell (pavement, pads, roads) and minus senior strips."""
    everything = unary_union([Polygon(c.ring, c.holes) for c in cells]) \
        if cells else Polygon()
    lip = law.tables.zones.adjacent_ground.lip_width_m
    groups: dict[tuple[str, int | None, str | None], list[Polygon]] = {}
    for c in cells:
        if c.role in RUNWAY_FAMILY:
            key = ("runway", c.code_number, None)
        elif c.role in TAXI_FAMILY:
            key = ("taxi", None, c.code_letter)
        else:
            continue
        groups.setdefault(key, []).append(Polygon(c.ring, c.holes))

    def rank(key: tuple[str, int | None, str | None]) -> tuple[int, float]:
        fam, cn, cl = key
        hw = zone2_half_width_m(law, "runway" if fam == "runway" else "junction",
                                cn, cl) or 0.0
        return (0 if fam == "runway" else 1, -hw)

    claimed = everything
    out: list[ZoneRegion] = []
    for key in sorted(groups, key=rank):
        fam, cn, cl = key
        role = "runway" if fam == "runway" else "junction"
        hw = zone2_half_width_m(law, role, cn, cl)
        if hw is None or hw <= 0:
            continue
        u = unary_union(groups[key])
        inner = u.buffer(min(lip, hw), **_MITRE)
        outer = u.buffer(hw, **_MITRE)
        z1 = inner.difference(claimed)
        z2 = outer.difference(inner).difference(claimed)
        cls = f"{cn}" if fam == "runway" else f"{cl or 'default'}"
        for zone, geom in ((1, z1), (2, z2)):
            parts = shapely.get_parts(geom) if geom.geom_type != "Polygon" else [geom]
            k = 0
            for g in parts:
                if g.geom_type != "Polygon" or g.is_empty or g.area < 1.0:
                    continue
                out.append(ZoneRegion(f"adjacent_ground:{fam}:{cls}:zone{zone}#{k}",
                                      g, zone, fam, cn, cl))
                k += 1
        claimed = unary_union([claimed, outer])
    return out
