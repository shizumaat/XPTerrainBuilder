"""THE OPEN-PAVEMENT DEFAULT (RULINGS 2026-09-04u): open pavement is
NEVER apron by default.  :func:`apron_witness` is THE ONE READER of apron
evidence (#2134 §4.2): it names the strongest RUNG a face carries — ``A1``
a stand on it, ``A2`` a parking lobe with OSM apron over the cell's
majority or an authored apron name, ``A3`` anything weaker (a taxi
centreline, a startup or cover on the source page, partial cover, a
name), which proves AIRSIDE and never APRON (owner Q1 2026-11-17T14:33Z).
``apron_gate`` turns the rungs into verdicts; a face with no witness at
all is groundside, and :func:`unclassified_groundside_role` names which
groundside role.

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
from .evidence import apron_named, is_library_path
from .rules import Rules
from .sources import SourceRecord

__all__ = ["A1", "A2", "A3", "apron_witness", "has_lobe",
           "narrow_road", "open_pavement_role", "road_ribbon",
           "unclassified_groundside_role"]


#: THE WITNESS RUNGS (#2134 spec §4.1, owner 2026-11-17T14:12Z: "The more
#: strict the grade requirements, the more strict and certain we need to be
#: about classifying pavement").  ``A1`` CERTAIN: a stand on the cell.
#: ``A2`` STRONG: a parking LOBE and an independent apron witness on the
#: cell itself (the contiguity half of A2 is ``apron_gate``'s fixpoint).
#: ``A3`` WEAK: something on the page, near it or beside it — it proves
#: AIRSIDE, never APRON (owner Q1 14:33Z).
A1, A2, A3 = "A1", "A2", "A3"


def has_lobe(face: Polygon, width_m: float) -> bool:
    """``face`` is somewhere at least ``width_m`` wide: its erosion by half
    that width is not empty (the §43 / :func:`narrow_road` reading)."""
    return not face.buffer(-width_m / 2.0).is_empty


def _authored_apron_name(src: SourceRecord | None, rules: Rules) -> bool:
    """The source page is an apron by its AUTHOR'S word: an apt.dat
    description naming an apron and no taxiway.  A library path's words
    are never this rung (owner Q5 14:38Z: "little weight")."""
    if src is None or src.taxi_name or is_library_path(src.description):
        return False
    return apron_named(src.description, rules)


def apron_witness(face: Polygon, src: SourceRecord | None,
                  evid: _t.Mapping[str, float | str], start_tree: STRtree | None,
                  cell_cover: float, rules: Rules) -> tuple[str | None, str | None]:
    """``(rung, why)`` — THE ONE READER of apron evidence (#2134 §4.2):
    the strongest rung this face carries on its own, or ``(None, None)``.

    ``cell_cover`` is the fraction of THIS CELL under OSM ``aeroway=apron``
    (``roles._apron_cover``).  Two thresholds read the answer and nothing
    else decides "apron": any rung is AIRSIDE evidence (the 11ac demotion,
    the 04u open default); only ``A1`` / ``A2`` (or ``apron_gate``'s body
    contiguity) may make the face ``apron``."""
    if start_tree is not None and len(start_tree.query(face, predicate="contains")) > 0:
        return A1, "startup on the face"
    lot = rules.lot
    if has_lobe(face, rules.corridor.max_width_m):
        if cell_cover >= lot.parking_cover_fraction:
            return A2, f"lobe + aeroway=apron covers {cell_cover:.0%} of the cell"
        if _authored_apron_name(src, rules):
            return A2, "lobe + apron by name"
    if float(evid.get("n_taxi", 0) or 0) > 0:
        return A3, "taxi centreline touches the face"
    if cell_cover >= lot.apron_cover_fraction:
        return A3, f"aeroway=apron covers {cell_cover:.0%} of the cell"
    if src is None:
        return None, None
    if src.startups > 0:
        return A3, f"{src.startups} startup(s) on the source"
    if src.taxi_m >= rules.cells.min_shared_m:
        return A3, f"taxi centreline {src.taxi_m:.0f} m on the source"
    if apron_named(src.description, rules):
        return A3, "apron by name"
    if src.apron_cover >= lot.apron_cover_fraction:
        return A3, f"aeroway=apron covers {src.apron_cover:.0%} of the source"
    return None, None


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


def narrow_road(face: Polygon, rules: Rules) -> float | None:
    """The mean width of ``face`` when it is ROAD-WIDE THROUGHOUT, else
    ``None`` (owner sim read 2026-11-04, HECA ``dsf:objpav1``: "a service
    road (which should be obvious from width alone)").

    :func:`road_ribbon` reads ONE ribbon off the minimum rotated
    rectangle, which says nothing about a NETWORK: HECA's object pavement
    body is 20.9 km of 5.6 m service road spread over 7.0 x 4.7 km, whose
    rectangle is a square.  The two width readings §43 already owns say it
    instead, with no new number: no point of the face reaches
    ``corridor.max_width_m`` of local width (its erosion by half that
    width is empty — ``neck.necks_of``' "no wide lobe at all": nothing an
    aircraft parks on), and its MEAN width, area over half its whole
    boundary, is at most ``service.free_max_width_m`` (the free-road
    ruling's road width).
    """
    per = face.length
    if per <= 0.0:
        return None
    width = 2.0 * face.area / per
    if width > rules.service.free_max_width_m:
        return None
    if not face.buffer(-rules.corridor.max_width_m / 2.0).is_empty:
        return None
    return width


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


def open_pavement_role(face: Polygon, road_reached: bool, rules: Rules,
                       evid: _t.Mapping[str, float | str], why: str
                       ) -> tuple[str, dict[str, float | str]]:
    """``(role, evidence)`` for a face the slice scored apron that may not
    be apron (``apron_gate``) and touches no taxiway: §110's groundside
    verdict, then §27 judges its edges.  ``why`` is what the witness
    ladder found (or ``"none"``)."""
    role, why_role = unclassified_groundside_role(face, rules,
                                                  road_reached=road_reached)
    return role, dict(evid, open_default=1.0, **why_role,
                      apron_evidence=f"{why} (04u / #2134: not an apron witness)")
