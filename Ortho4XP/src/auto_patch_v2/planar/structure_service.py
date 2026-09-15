"""§34 (12) THE TWO DERIVATIONS A CORRIDOR IS JUDGED BY (owner RULINGS
2026-09-15f item 1; Fable 2026-09-15i; spec §34 (12)) — lane
`v2vmmcshore`.

Two readings, both pure functions of the law and the classification, and
both used at exactly one site in :mod:`auto_patch_v2.planar.structures`:

* :func:`airside_cut_roles` — clause (3)'s protected set: the airside
  roles a corridor may never cut;
* :func:`airside_stops` — the faces of that set ONE corridor must stop
  short of, its own decked and mouth-standing pavement excluded.

CLAUSE (1) IS WITHDRAWN (Fable 2026-09-15; RULINGS 2026-09-15w).  Round
1 read it as "a tunnel is built only where its bore passes under a cover
class" and measured the price at LEMD by dry pair: **54 tunnels → 16**,
the 38 lost being exactly owner 2026-09-12ab's "Build them" population —
a mapped tunnel whose mouth stands on the field is built, mouth and
ramp, whether or not its bore passes under an airport surface.  That is
an owner ruling, and (1) reversed it by the side door.  ADMISSION IS BY
THE MOUTH (§29 (1), ``mouth_standoff_m``); what stops VMMC's seafront
line is (2)–(4), and the code for (1) is DELETED rather than gated.

They live beside ``structures.py`` rather than in it for the reason
``structure_approach.py`` and ``structure_deck.py`` do: that file stands
at its 1,000-line budget (``tests/auto_patch_v2/test_planar.py::
test_import_and_budget``).
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon

from ..law import Law
from ..law.tables import is_structure_role, is_value_role, role_side
from .structure_approach import under_cover

__all__ = ["airside_cut_roles", "airside_stops", "grade_reach_for",
           "osm_stops", "pad_relief_m"]


def pad_relief_m(airport: Airport, poly: Polygon) -> float:
    """The DEM relief across a pad's ring (a flat pad is ground; a pad on
    relief is a levelled plane).  ONE implementation, in
    ``airport/skirt.ring_relief_m`` (spec §22 C4).  It lives here, beside
    §34 (12)'s two readings, only for ``structures.py``'s 1,000-line
    budget; ``structures`` re-exports it under its old private name."""
    from ..airport.skirt import ring_relief_m
    return ring_relief_m(lambda x, y: float(airport.dem.z(x, y)), poly.exterior.coords)



def airside_cut_roles(law: Law) -> tuple[str, ...]:
    """§34 (12) (3) THE AIRSIDE ROLE SET A CORRIDOR NEVER CUTS (owner
    RULINGS 2026-09-15f item 1; Fable 2026-09-15i).

    Every AIRSIDE role that carries a surface of its own — the runway
    family, the parallels, the stubs, the cross-connectors, the junctions
    and the aprons — read from ``precedence.toml`` (``side = "airside"``,
    ``value = true``, not a structure), never typed out here.  Before
    §34 (12) only the runway family was exempt from a corridor cut
    (08-07 ruling 4), so VMMC's seafront car-park bore knifed code-E
    junction ``pav5`` into six faces at 3.58–4.50 m against the 6.10 m
    field.  ``ramp_cuts_runway_family = false`` keeps its name and its
    value; what widened is the population it protects.

    The PAD (``building``) is deliberately NOT here: a pad is protected by
    ``tunnel.ramp_crosses_pad``, which STOPS the ramp at the pad's edge
    rather than refusing the corridor, and that machinery
    (``structure_geometry.pad_hit``) is unchanged."""
    return tuple(r for r in law.tables.precedence.roles
                 if role_side(law, r) == "airside" and is_value_role(law, r)
                 and not is_structure_role(law, r) and r != "building")


def airside_stops(cells, polys, cut_roles, decked, mouth_pts, grid: float):
    """§34 (12) (3) A CORRIDOR NEVER CUTS AIRSIDE PAVEMENT — the faces one
    corridor must STOP SHORT of, as ``[(polygon, ref)]`` for
    ``structure_geometry.pad_hit`` (owner RULINGS 2026-09-15f item 1 as
    AMENDED, Fable 2026-09-15; RULINGS 2026-09-15w).

    IT STOPS SHORT, IT IS NOT REFUSED.  The ruling's own words: "it
    becomes an underpass where the pavement is authored as a deck or a
    pack corridor covers it, otherwise it STOPS SHORT of the pavement —
    at VMMC the OSM car-park bore stops at pav5".  The stop is the
    existing station-truncation loop in ``structures.build_structures``,
    the same one ``ramp_crosses_pad`` has always used; a corridor with no
    room left refuses there, by that loop's own message.

    TWO EXCLUSIONS, both the ruling's.  ``decked`` are this corridor's own
    deck polygons — "the pavement is the DECK of an underpass (§34 (5))"
    — so every §34 (5) underpass, LEMD F-6 and KCLT taxiway U, is
    untouched.  And the pavement the corridor's own MOUTH stands on is
    not a cut: (3) is about a bore that CROSSES a pavement, and a
    corridor whose mouth stands on an apron does not cross it, it ENDS in
    it — that is what a portal is, and 08-07 ruling 4's cut is how the
    portal is opened.

    THE CALLER SCOPES IT TO OSM-DERIVED CORRIDORS.  A PACK-STATED
    corridor (§33 (6) signatures A/B/C — ``tunnel_objects``, wall
    corridors, plates) is authored geometry and its crossing of airside
    IS an underpass by authorship: measured at OTHH, applying (3) to them
    refused three terminal tunnels (``tunnel middle - east`` / ``- west``,
    ``tunnel south west 2``) against aprons ``pav32`` / ``pav30``.
    """
    from shapely.ops import unary_union
    keep = unary_union(list(decked)) if decked else None
    out = []
    for p, c in zip(polys, cells):
        if c.role not in cut_roles or c.kind == "structure":
            continue
        if any(p.dwithin(q, grid) for q in mouth_pts):
            continue                      # the portal's own pavement
        if keep is not None and p.within(keep.buffer(grid)):
            continue                      # this corridor's own deck
        out.append((p, c.ref))
    return out


def osm_stops(corridor, group, cells, polys, pads, pad_tree, cut_roles,
              deck_ivals, obj_ivals, grid: float, wall_kind: str):
    """``(stops, tree)`` for ``structure_geometry.pad_hit`` — what ONE
    corridor's ramp must stop short of (§34 (12) (3) as amended).

    A PACK-STATED corridor (``corridor is not None``) or a wall corridor
    keeps the building pads alone, exactly as before: it is authored
    geometry and its crossing of airside IS an underpass by authorship
    (measured at OTHH — bound by (3) it refused three terminal tunnels
    against aprons ``pav32`` / ``pav30``).  An OSM-derived corridor adds
    :func:`airside_stops`.
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    if corridor is not None or group.kind == wall_kind:
        return pads, pad_tree
    stops = pads + airside_stops(
        cells, polys, cut_roles,
        [d[3] for d in deck_ivals] + [d[3] for d in obj_ivals],
        [Point(m.xy) for m in (group.members or ())] or [Point(group.mouth)],
        grid)
    return stops, (STRtree([p for p, _r in stops]) if stops else None)


def grade_reach_for(airport, law: Law, axis_fn, mouth_z: float,
                    grade: float, spacing: float):
    """§34 (12) (4) as AMENDED (RULINGS 2026-09-15aj): ``f(covered_end) ->``
    the station at which the climb from ``covered_end`` reaches the DEM
    along the route, or ``None`` where it never does.

    It is ``structure_approach.ramp_top`` — the RAMP's own derivation, so
    the deck reading and the ramp it feeds cannot disagree about where
    the trench ends — bound to this group's mouth datum, cap and station
    spacing.
    """
    from .structure_approach import ramp_top

    def reach(covered_end: float) -> float | None:
        s_top, _ss = ramp_top(airport, law, axis_fn, mouth_z, covered_end,
                              spacing, grade=grade)
        return s_top

    return reach
