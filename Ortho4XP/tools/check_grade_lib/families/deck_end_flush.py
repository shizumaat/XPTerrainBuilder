"""THE DECK END LINE IS FLUSH family ``deck_end_flush`` (spec
``deck-end-anchors-20261103`` §6; owner RULINGS 2026-10-30a (1), 2026-11-03c;
issue #1715), SIDECAR-DECLARED.

A pack hard deck has ONE zero, flush at every end line within
``[bridge] deck_flush_m`` (0.04 m): the object stage seats it at the mean of
the built surface at its end-line stations less their authored tops
(``pipeline/rebake_inputs._deck_plate``).  The sidecar ``deck_anchors``
names every end line's stations (``[lat, lon]``, the emitted node identity)
and their top; this family reads the BUILT surface there and reports

* every station off the object's one zero + its end line's top; and
* every held (pinned, non-yielding) anchor whose built level is off the
  anchor ``z_m`` it was pinned at.

Before it the census could not see a deck end line at all (#1715: LFPG
``obj13030`` 3.2 m off its deck, no row).  A patch with no key reports
nothing, which is every patch built before the anchors."""
from __future__ import annotations

from typing import Dict, List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("deck_end_flush",
     "HARD-DECK END LINE off the deck's one zero (or its anchor)",
     "within"),
)

#: ``[bridge] deck_flush_m`` (law/structures.toml): the flush bar
DECK_FLUSH_M = 0.04


def _surface(nodes, ways) -> Dict[Tuple[float, float], Tuple[float, Way]]:
    out: Dict[Tuple[float, float], Tuple[float, Way]] = {}
    for w in ways:
        for nid, z in zip(w.nids, w.elevs, strict=False):
            if z is None or nid not in nodes:
                continue
            lat, lon = nodes[nid]
            out.setdefault((round(lat, 7), round(lon, 7)), (float(z), w))
    return out


def _row(lat: float, lon: float, z: float, want: float, way: Way) -> Violation:
    v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0, de_m=abs(z - want),
                  way_a=way, way_b=way, pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                  elev_a=z, elev_b=want)
    v.lat, v.lon = lat, lon
    return v


def check_deck_end_flush(deck_anchors, nodes, ways) -> List[Violation]:
    """The family's rows (module doc)."""
    if not deck_anchors:
        return []
    at = _surface(nodes, ways)
    by_obj: Dict[str, list] = {}
    for rec in deck_anchors:
        by_obj.setdefault(str(rec.get("object")), []).append(rec)
    out: List[Violation] = []
    for _oid, recs in sorted(by_obj.items()):
        read = []
        seen = set()
        for rec in recs:
            for lat, lon in rec.get("stations") or ():
                key = (round(float(lat), 7), round(float(lon), 7))
                if key in seen or key not in at:
                    continue
                seen.add(key)
                z, w = at[key]
                read.append((float(lat), float(lon), z, float(rec.get("top_y") or 0.0), w))
        if read:
            zero = sum(z - top for _la, _lo, z, top, _w in read) / len(read)
            out.extend(_row(la, lo, z, zero + top, w) for la, lo, z, top, w in read
                       if abs(z - zero - top) > DECK_FLUSH_M)
        for rec in recs:
            if not rec.get("pinned") or rec.get("yielding") or not rec.get("at"):
                continue
            key = (round(float(rec["at"][0]), 7), round(float(rec["at"][1]), 7))
            if key in at and abs(at[key][0] - float(rec["z_m"])) > DECK_FLUSH_M:
                out.append(_row(key[0], key[1], at[key][0], float(rec["z_m"]), at[key][1]))
    return out
