"""THE OPEN-PAVEMENT DEFAULT (RULINGS 2026-09-04u): open pavement is
NEVER apron by default.  A face the slice scored ``apron`` keeps that
role only on APRON EVIDENCE — a 1300 startup on the face or its source
polygon, a taxi centreline on the source (``cells.min_shared_m`` of it),
the source named an apron (apt.dat description, ``lot.apron_name_tokens``)
or covered by OSM ``aeroway=apron`` — else it is groundside: a
``parking_lot`` when a road reaches it (``roles._road_evidence``: a
route / OSM road within ``cells.on_tol_m`` or a touching road / lot
face), otherwise ``rules.groundside.default_open_role``.

Measured CYXY (04u): dsf:pol17 + pol20 + pol123 (12,466 m², no taxi, no
startup, no apron name) defaulted to APRON, airside, while they are the
parking lots 1206 route 50 climbs to from the apron.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from .rules import Rules
from .sources import SourceRecord

__all__ = ["apron_evidence", "open_pavement_role"]


def apron_evidence(face: Polygon, src: SourceRecord | None,
                   evid: _t.Mapping[str, float | str], start_tree: STRtree | None,
                   rules: Rules) -> str | None:
    """The first apron evidence this face carries, or ``None``."""
    if float(evid.get("n_taxi", 0) or 0) > 0:
        return "taxi centreline touches the face"
    if start_tree is not None and len(start_tree.query(face, predicate="contains")) > 0:
        return "startup on the face"
    if src is None:
        return None
    if src.startups > 0:
        return f"{src.startups} startup(s) on the source"
    if src.taxi_m >= rules.cells.min_shared_m:
        return f"taxi centreline {src.taxi_m:.0f} m on the source"
    d = src.description.lower()
    if any(t in d for t in rules.lot.apron_name_tokens):
        return "apron by name"
    if src.apron_cover >= rules.lot.parking_cover_fraction:
        return f"aeroway=apron covers {src.apron_cover:.0%}"
    return None


def open_pavement_role(face: Polygon, src: SourceRecord | None,
                       evid: _t.Mapping[str, float | str], start_tree: STRtree | None,
                       road_reached: bool, rules: Rules
                       ) -> tuple[str, dict[str, float | str]]:
    """``(role, evidence)`` for a face the slice scored apron."""
    why = apron_evidence(face, src, evid, start_tree, rules)
    if why is not None:
        return "apron", dict(evid, apron_evidence=why)
    role = "parking_lot" if road_reached else rules.groundside.default_open_role
    return role, dict(evid, open_default=1.0, road_evidence=float(road_reached),
                      apron_evidence="none (04u: open pavement is never apron by default)")
