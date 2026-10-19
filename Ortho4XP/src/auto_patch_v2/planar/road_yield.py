"""THE ROAD BESIDE THE BAND TRUMPS THE BAND (owner 2026-10-19, issue #944).

Owner, verbatim: "if a road runs next to airside ... then we cannot have
our adjacent ground graded strip go into it ... The road trumps adjacent
ground, and per our existing rules if there's no gap it's welded to the
airside, if there's a gap, then it's graded groundside road and there may
be a step/retaining wall between it and the airside."

Measured at the test site (KBUR, 34.196709421, -118.348961910): a 7-lane
secondary road runs beside an apron; its centreline lies 6.7 m outside the
taxiway band's outer edge, so the band reached about 5.5 m into the road's
24.5 m carriageway and graded the road's outer lanes with the strip.
Nothing trimmed it: §19 rule 2 needs a crest, the band subtracts groundside
CELLS only, and a road the patch does not ribbon has no cell.

THE WITNESS IS THE ZONE ENVELOPE, and it keeps this rule clear of the
standing in-band law.  A road whose centreline runs INSIDE an
adjacent-ground band is ribboned by the patch (``classify/ribbon_mint``'s
extent is the same envelope) and grades WITH the zone (RULINGS 2026-09-13ar,
2026-09-29r, owner 2026-09-30b) -- this module does not touch it.  A road
whose centreline runs OUTSIDE every band is a groundside road the core mesh
owns: the band must not enter its carriageway. So the part of each such
centreline outside the envelope is grown by the road's MAPPED half-width
(``airport/road_ways.ribbon_half_width_m``, #949: the way's ``width``, else
``lanes`` x ``tunnel.lane_width_m``; never narrower than the core's
``road_profile.lane_width_m``; the ribbon a patch road gets) plus the stand-
off every groundside cell gets, and that is subtracted from the band at the
single zone derivation site (``planar/zones.zone_regions``). The gap between
the band's new edge and the road terraces, exactly as against a groundside
cell (groundside terrace law)."""
from __future__ import annotations

from shapely.geometry import LineString
from shapely.ops import unary_union

from ..airport.road_ways import ribbon_half_width_m, road_ways
from ..law import Law

__all__ = ["road_carriageways", "beside_road_cut"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def road_carriageways(osm_ways, law: Law,
                      highways=None) -> tuple[tuple[LineString, float], ...]:
    """Every at-grade mapped road (``airport/road_ways``) of a ribbon class
    (``highways``: ``rules.osm_roads.ribbon_highways``; ``None`` reads the
    shipped table) as ``(centreline, carriageway half-width)``."""
    if highways is None:
        from ..classify.rules import load_rules
        orr = load_rules().osm_roads
        if not orr.enabled:
            return ()
        highways = orr.ribbon_highways
    allowed = set(highways)
    out: list[tuple[LineString, float]] = []
    for w, line in road_ways(osm_ways):
        tags = w.tags or {}
        if tags.get("highway") not in allowed:
            continue
        out.append((line, ribbon_half_width_m(tags, law)))
    return tuple(out)


def beside_road_cut(carriageways, envelope, standoff_m: float):
    """The ground the bands yield to: each road's centreline OUTSIDE the
    zone ``envelope``, grown (flat ends) by its half-width plus
    ``standoff_m``.  ``None`` when no road runs beside a band."""
    if not carriageways or envelope is None or envelope.is_empty:
        return None
    reach = envelope.buffer(max(h for _l, h in carriageways) + standoff_m, **_MITRE)
    pieces = []
    for line, half in carriageways:
        if not line.intersects(reach):
            continue
        outside = line.intersection(reach).difference(envelope)
        if outside.is_empty or outside.length <= 0.0:
            continue
        # a stretch that has just CROSSED out of a band cuts the band
        # beside it too: that ground is the road's carriageway, not the
        # band's (a notch-free variant -- the crossing's in-band growth
        # withheld -- was measured worse at KBUR: hairline 318 -> 377)
        pieces.append(outside.buffer(half + standoff_m, cap_style="flat", **_MITRE))
    if not pieces:
        return None
    cut = unary_union(pieces)
    return None if cut.is_empty else cut
