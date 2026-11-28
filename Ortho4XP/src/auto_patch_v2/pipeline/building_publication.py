"""THE ``buildings`` SIDECAR KEY (owner RULINGS 2026-11-27h; spec
``docs/specs/building-envelope-20261127.md`` §10 stop 1).

One record per separately seated building the load found
(``PackPartition.buildings``, ``airport/building_split``): its id (the
smallest wall part id), its plan centre, cell area, how many wall,
interior, sheet and attached pieces it holds, and how many anchors and
placements those pieces come from.  A REPORT key: nothing reads it yet."""
from __future__ import annotations

import collections

from ..airport.building_split import Building, Split

__all__ = ["building_records", "log_line"]


def building_records(airport) -> list[dict]:
    """The ``buildings`` records (module doc), in building id order."""
    s = getattr(getattr(airport, "partition", None), "buildings", None)
    if not isinstance(s, Split) or not s.buildings:
        return []
    to_ll = airport.frame.transformers()[1]
    kinds: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for p, b in s.of.items():
        kinds[b][s.kind[p]] += 1
    out = []
    for b in s.buildings:
        out.append(_record(b, kinds[b.id], to_ll))
    return out


def _record(b: Building, k: collections.Counter, to_ll) -> dict:
    """One building's record."""
    lat, lon = to_ll(0.5 * (b.box[0] + b.box[2]), 0.5 * (b.box[1] + b.box[3]))
    return {"id": b.id, "lat": round(float(lat), 7), "lon": round(float(lon), 7),
            "area_m2": round(b.area_m2, 2), "walls": len(b.walls),
            "interior": k["interior"], "sheets": k["sheet"], "attached": k["attached"],
            "anchors": len(b.anchors), "placements": len(b.members)}


def log_line(icao: str, s: "Split | None") -> str:
    """The build log's one line on the buildings."""
    if s is None:
        return f"[{icao}] buildings: none (no load reading)"
    c = s.counts
    return (f"[{icao}] buildings: {c.get('buildings', 0)} from {c.get('wall_pieces', 0)} wall "
            f"piece(s); {c.get('interior_pieces', 0)} interior, {c.get('sheet_pieces', 0)} sheet, "
            f"{c.get('attached_pieces', 0)} attached of {c.get('pieces', 0)} solid; "
            f"{c.get('seconds', 0.0):.2f} s at {s.params.cell_m} m")
