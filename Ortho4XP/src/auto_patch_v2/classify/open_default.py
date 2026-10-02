"""THE OPEN-PAVEMENT DEFAULT (RULINGS 2026-09-04u): open pavement is
NEVER apron by default.  A face the slice scored ``apron`` keeps that
role only on APRON EVIDENCE — a 1300 startup on the face or its source
polygon, a taxi centreline on the source (``cells.min_shared_m`` of it),
the source named an apron (apt.dat description, ``lot.apron_name_tokens``)
or covered by OSM ``aeroway=apron`` — else it is groundside, and
:func:`unclassified_groundside_role` names which groundside role.

§110 UNCLASSIFIED GROUNDSIDE PAVEMENT IS A PARKING LOT (owner remark
RULINGS 2026-09-30b, issue #110).  That naming is THE ONE DERIVATION
SITE for both groundside ladders — this 04u open default and
``roles.py``'s 11ac/04j landside demotion, which used to re-spell it.
Pavement with ROAD PROPORTIONS (:func:`road_ribbon`: at most
``service.free_max_width_m`` wide and at least
``groundside.road_ribbon_min_aspect`` times as long as it is wide) is a
road RIBBON, ``service_road``; everything else is
``groundside.unclassified_role`` — a parking LOT, a flat plate under the
universal cap — whether or not a road reaches it
(``roles._road_evidence``: a route / OSM road within ``cells.on_tol_m``
or a touching road / lot face, now recorded as evidence only).  Before
#110 a face no road touched shipped ``groundside.default_open_role``,
which carries no plate law of its own; that key is now only what the
04z-1 taxi-name VETO falls back to.

Measured CYXY (04u): dsf:pol17 + pol20 + pol123 (12,466 m², no taxi, no
startup, no apron name) defaulted to APRON, airside, while they are the
parking lots 1206 route 50 climbs to from the apron.

A face on a TAXIWAY-NAMED source (RULINGS 2026-09-04z(1)) never reaches
this default: the scorer reads it ``junction`` first (``roles.py``,
``evidence.taxi_name_match``) — the name is evidence above the default.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..model.frame import rectangle_axes
from .rules import Rules
from .sources import SourceRecord

__all__ = ["apron_evidence", "open_pavement_role", "road_ribbon",
           "unclassified_groundside_role"]


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
    if src.apron_cover >= rules.lot.apron_cover_fraction:
        return f"aeroway=apron covers {src.apron_cover:.0%}"
    return None


def road_ribbon(face: Polygon, rules: Rules) -> tuple[bool, float, float]:
    """``(is_a_road_ribbon, aspect, width_m)`` — §110's PROPORTIONS test.

    The face's minimum rotated rectangle read as a ribbon
    (``model.frame.rectangle_axes``, the same long/short sides §27 (5)'s
    mouth test reads): it is a ROAD RIBBON when it is at most
    ``service.free_max_width_m`` wide — the free-road ruling's own width,
    so there is no second number here — and at least
    ``groundside.road_ribbon_min_aspect`` times as long as it is wide.
    A degenerate ring reads ``(False, 0.0, 0.0)``.
    """
    _axis, long_m, width_m = rectangle_axes(face)
    if width_m <= 0.0:
        return False, 0.0, 0.0
    aspect = long_m / width_m
    is_ribbon = (width_m <= rules.service.free_max_width_m
                 and aspect >= rules.groundside.road_ribbon_min_aspect)
    return is_ribbon, aspect, width_m


def unclassified_groundside_role(face: Polygon, rules: Rules, *,
                                 road_reached: bool, taxi_named: bool = False
                                 ) -> tuple[str, dict[str, float | str]]:
    """``(role, evidence)`` for GROUNDSIDE pavement the evidence did not
    classify — §110 (owner remark RULINGS 2026-09-30b, issue #110).

    THE ONE DERIVATION SITE for the unclassified verdict.  Both groundside
    ladders end here: the 04u open default (a face the slice scored apron
    that carries no apron evidence) and the 11ac/04j landside DEMOTION (a
    face with no touch-chain to a runway).  Until #110 each spelled its
    own two-way choice — ``parking_lot`` when a road reached the face,
    else ``groundside_pavement``, a role with no plate law of its own.
    The owner's rule replaces both answers:

    * pavement with ROAD PROPORTIONS (:func:`road_ribbon`) is a road
      RIBBON — ``service_road``, at the road cap;
    * everything else is ``groundside.unclassified_role`` — a parking LOT,
      a flat plate under the universal cap — whether or not a road reaches
      it.  A road reaching a face was never what made it a car park.

    ``taxi_named`` is the 04z-1 VETO and outranks both: a demoted face on
    a TAXIWAY-NAMED source is ``groundside.default_open_role``, never a
    lot and never a road.
    """
    if taxi_named:
        return rules.groundside.default_open_role, {
            "road_evidence": float(road_reached),
            "unclassified_default": "vetoed (04z-1: a taxi-named face is never a lot)"}
    is_ribbon, aspect, width_m = road_ribbon(face, rules)
    evid: dict[str, float | str] = {"road_evidence": float(road_reached),
                                    "ribbon_aspect": aspect,
                                    "ribbon_width_m": width_m}
    if is_ribbon:
        # ``road_by_proportions``: a road by its SHAPE, never by evidence —
        # §27 judges it as the lot it would otherwise be (no MOUTH, no
        # §37 (2) share; ``airside_edge.airside_edge_flip``, HECA
        # ``dsf:objpav0``, lane hecamove 2026-10-02).
        return "service_road", dict(
            evid, road_by_proportions=1.0, unclassified_default=(f"road proportions (§110): aspect {aspect:.1f} "
                                        f">= {rules.groundside.road_ribbon_min_aspect:g}, "
                                        f"width {width_m:.1f} m"))
    return rules.groundside.unclassified_role, dict(
        evid, unclassified_default=(f"§110: unclassified groundside pavement, aspect "
                                    f"{aspect:.1f}, width {width_m:.1f} m"))


def open_pavement_role(face: Polygon, src: SourceRecord | None,
                       evid: _t.Mapping[str, float | str], start_tree: STRtree | None,
                       road_reached: bool, rules: Rules
                       ) -> tuple[str, dict[str, float | str]]:
    """``(role, evidence)`` for a face the slice scored apron."""
    why = apron_evidence(face, src, evid, start_tree, rules)
    if why is not None:
        return "apron", dict(evid, apron_evidence=why)
    role, why_role = unclassified_groundside_role(face, rules,
                                                  road_reached=road_reached)
    return role, dict(evid, open_default=1.0, **why_role,
                      apron_evidence="none (04u: open pavement is never apron by default)")
