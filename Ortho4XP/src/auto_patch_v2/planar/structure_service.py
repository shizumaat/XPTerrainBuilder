"""§34 (12) THE TWO DERIVATIONS A CORRIDOR IS JUDGED BY (owner RULINGS
2026-09-15f item 1; Fable 2026-09-15i; spec §34 (12)) — lane
`v2vmmcshore`.

Two readings, both pure functions of the law and the classification, and
both used at exactly one site in :mod:`auto_patch_v2.planar.structures`:

* :func:`serves_the_field` — clause (1)'s admission: a tunnel is built
  only where its BORE passes under a §34 (12) (1) cover class;
* :func:`airside_cut_roles` — clause (3)'s exemption set: the airside
  roles a corridor may never cut.

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

__all__ = ["airside_cut_refusal", "airside_cut_roles", "no_service_bores",
           "pad_relief_m", "serves_the_field"]


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


def serves_the_field(line: LineString, polys: _t.Sequence[Polygon], tree) -> bool:
    """§34 (12) (1) A TUNNEL IS BUILT ONLY WHERE IT SERVES THE FIELD (owner
    RULINGS 2026-09-15f item 1; Fable 2026-09-15i).

    ``line`` is the BORE (the mapped ``tunnel=yes`` chain) and ``polys``
    the §34 (12) (1) COVER CLASSES ONLY — airside pavement, a pad or unit
    footprint, a deck the pack authored (a plate or a wall corridor,
    §33).  The bore serves the field when at least a metre of it runs
    UNDER one of them.

    A mouth inside the cover ⊕ ``mouth_standoff_m`` (§29 (1)) is a
    NECESSARY condition and never a sufficient one: VMMC's OSM
    ``highway=service tunnel=yes`` ways −5508/−5507 are a car-park ramp
    under a building that has nothing to do with the aerodrome, and they
    were admitted because a mouth stood 36 m from junction ``pav5``.  A
    bore whose only covers are mapped ``bridge=yes`` roads is not an
    airport tunnel: a mapped bridge is not a cell of this set, and a
    ``bridge_deck:*`` face is minted BY a corridor, so it can never be
    that corridor's own admission evidence.

    The reading is ``structure_approach.under_cover``'s — one
    implementation of "how much of this line is under these polygons",
    two cover sets."""
    return under_cover(line, polys, tree)


def no_service_bores(covered, mouth_list, corridors, cells, polys, plates,
                     law: Law, bore_end_tolerance_m: float):
    """``(served, no_service)`` for §34 (12) (1), in ONE place.

    ``covered`` are the bores §29 (1) admitted (each has a mouth on the
    field).  A bore is SERVED when it passes under a §34 (12) (1) cover
    class — airside pavement, a pad or unit footprint, one of the pack's
    authored corridors or plates.  A groundside road, a lot, or a mapped
    ``bridge=yes`` way is not cover: none of them is a cell of this set,
    and a ``bridge_deck:*`` face is minted BY a corridor, so it can never
    be that corridor's own admission evidence.

    AN OBJECT CORRIDOR'S BORE IS NEVER GATED.  The pack's wall objects
    are the field authority where they stand (§33 (2), the owner's EGLL
    exception, keyed on the pack's geometry and never on OSM), and the
    precedence downstream hands such a mouth to the object.  Measured at
    OTHH without this clause: three ``tunnel-object:*`` corridors
    (``tunnel middle - east`` / ``- west``, ``tunnel south west 2``) were
    dropped because their bore LINE runs under the object rather than
    under a classified cell.
    """
    from shapely.strtree import STRtree
    from .object_corridor import mouth_covered_by
    service = [p for p, c in zip(polys, cells)
               if role_side(law, c.role) == "airside" and c.kind != "structure"]
    service += [c.footprint for c in corridors]
    service += [getattr(pl, "footprint", None) for pl in plates]
    service = [p for p in service if p is not None and not p.is_empty]
    tree = STRtree(service) if service else None
    claimed = {id(m.bore) for m in mouth_list
               if corridors
               and mouth_covered_by(m.xy, corridors, bore_end_tolerance_m) is not None}
    served = [b for b in covered
              if id(b) in claimed or serves_the_field(b.line, service, tree)]
    ids = {id(b) for b in served}
    return served, [b for b in covered if id(b) not in ids]


def airside_cut_refusal(outer, cut_u, decked, mouth_pts, cells, polys,
                        cut_roles, gap: float, grid: float):
    """The §34 (12) (3) refusal message for one corridor, or ``None``.

    ``cut_u`` is the union the corridor may not knife — the whole airside
    role set for an OSM bore, the runway family alone where the PACK
    states the corridor (an object corridor's own plate IS the deck over
    the pavement, which is (3)'s first limb, and there is no terrain deck
    cell to find; measured at OTHH, above).

    TWO EXEMPTIONS, both the ruling's own words.  The pavement a DECK of
    this corridor states is not cut ("the pavement is the DECK of an
    underpass, §34 (5)") — so every §34 (5) underpass, LEMD F-6 and KCLT
    taxiway U, passes exactly as before.  And the pavement the corridor's
    own MOUTH stands on is not cut: (3) is about a bore that CROSSES a
    pavement, and a corridor whose mouth stands on an apron does not
    cross it, it ENDS in it — that is what a portal is, and 08-07 ruling
    4's cut has always been how the portal is opened.  VMMC's bore
    reached junction ``pav5`` 36 m from its mouth and split it into six
    faces at 3.58–4.50 m against the 6.10 m field; that is the defect.
    """
    if cut_u is None:
        return None
    from shapely.ops import unary_union
    mitre = dict(join_style="mitre", mitre_limit=2.0)
    keep = list(decked)
    keep += [p for p, c in zip(polys, cells)
             if c.role in cut_roles and c.kind != "structure"
             and any(p.dwithin(q, grid) for q in mouth_pts)]
    cut = outer
    if keep:
        cut = outer.difference(unary_union(keep).buffer(gap + grid, **mitre))
    if cut.is_empty or not cut.intersects(cut_u) or \
            cut.intersection(cut_u).area <= 1e-6:
        return None
    hit = sorted({c.ref for p, c in zip(polys, cells)
                  if c.role in cut_roles and c.kind != "structure"
                  and p.intersects(cut) and p.intersection(cut).area > 1e-6})[:4]
    return (f"the ramp would cut AIRSIDE pavement {'+'.join(hit) or '(unnamed)'} "
            f"before reaching the DEM, and no deck of this corridor states the "
            f"crossing (\u00a734 (12) (3); ramp_cuts_runway_family = false)")
