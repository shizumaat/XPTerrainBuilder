"""A STOREY SHELL'S BLOCK DATUM (#2062 spec R3b A; owner rulings 13w / 13x
(2), 2026-11-15T03:05Z: one code path for every shell).

``planar/storey_floor`` names what leads each shell's block
(``StoreyShell.leader``); its levels stand at the block's DATUM COLUMN ``D``
(``model/platform.datum_vertices(fills=True)``) plus their ``y``
(``constraints/platform.landing_rows``).  This generator holds ``D``:

* ``floor`` -- a HARD two-sided tie ``z_D - z_f = 0`` to a vertex ``f`` of
  the ramp-class floor's DATUM GROUP (``constraints/structures.datum_group``,
  the tunnel whose axis passes nearest the floor the lowest level faces):
  the block stands on the mouth's level and FOLLOWS it one-way (the
  floor's own rows place it);
* ``ground`` -- a HARD pin at ``StoreyShell.datum_z``;
* ``airside`` -- nothing here: the stage-1 weld column holds it (every held
  pad's frontage hold).

Ruling head :data:`RULING` (``[design] hard_rulings``, ``pad_level_rulings``,
the pad tier).  Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point

from ..law import Law
from ..model.constraints import Linear, Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["shell_datum_rows", "RULING"]

GEN = "shell_datum"
RULING = "structures.building_pad storey shell datum"
STATS: dict[str, dict[str, int]] = {}


def _floor_vertex(planar: PlanarMap, xy) -> "int | None":
    """A vertex of the datum group of the tunnel whose axis passes nearest
    ``xy`` (the nearest of them to it)."""
    from .structures import datum_group
    tns = [tn for tn in planar.structures if len(tn.axis) >= 2]
    if xy is None or not tns:
        return None
    p = Point(xy)
    for tn in sorted(tns, key=lambda tn: (LineString(tn.axis).distance(p), tn.id)):
        vs = datum_group(planar, tn)
        if vs:
            return min(vs, key=lambda v: (Point(planar.vertices[v].xy).distance(p), v))
    return None


def shell_datum_rows(planar: PlanarMap, law: Law, airport: _t.Any = None) -> list[Row]:
    """The block datum rows of every floor- or ground-led storey shell
    (module docstring)."""
    STATS.pop("shell_datum_rows", None)
    shells = [sh for sh in getattr(planar, "storey_shells", ()) or ()
              if getattr(sh, "leader", "airside") in ("floor", "ground")]
    if not shells:
        return []
    from ..model.platform import datum_vertices
    held = datum_vertices(planar, law, fills=True)
    rows: list[Row] = []
    n = {"floor": 0, "ground": 0, "no_datum": 0, "no_floor": 0}
    for sh in shells:
        dv = held.get(sh.pad_ref)
        if dv is None:
            n["no_datum"] += 1
            continue
        src = Source(GEN, RULING, (f"storey_shell:{sh.id}", sh.pad_ref, sh.leader))
        if sh.leader == "ground":
            if sh.datum_z is None:
                n["no_datum"] += 1
                continue
            rows.append(Pin(dv, float(sh.datum_z), src))
            n["ground"] += 1
            continue
        f = _floor_vertex(planar, sh.floor_xy)
        if f is None or f == dv:
            n["no_floor"] += 1
            continue
        # ONE-WAY (``[design] one_way_rulings``): the block follows its floor
        rows.append(Linear(((dv, 1.0), (f, -1.0)), None, 0.0, src, follows=dv))
        rows.append(Linear(((dv, -1.0), (f, 1.0)), None, 0.0, src, follows=dv))
        n["floor"] += 1
    STATS["shell_datum_rows"] = {**n, "rows": len(rows)}
    return rows
