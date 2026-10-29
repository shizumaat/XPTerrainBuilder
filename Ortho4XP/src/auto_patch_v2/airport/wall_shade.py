"""A RETAINING WALL IS NEVER A PAD (issue #1633; owner #1600 / RULINGS
2026-10-28t Q268, Q269 (a)).

A pack component that RETAINS ITS OWN HEIGHT
(:func:`airport.wall_class.wall_class_components`, ``retains``) is a STEP
between two levels: its top on its high face, its foot on its low face
(``airport/road_ramp.wall_terrace``, ``constraints/wall_zone``).  A thick
one long enough clears the cluster-pad bar and was minted ONE FLAT PAD
over its whole footprint as well.  MEASURED (KATL capture ``lkatl3`` on
e0f4a3e02, the 27R end): ``muro_27R.obj`` comp 0, 19.99 m, 2,558 m2,
485 m long, 5.3 m thick, became ``building30`` held at its foot (278.5 m);
the truck route sharing its ring vertices sat in a 6-12 m trench under its
own ground, and the high side stood 9-12 m under the wall's back.

The footprints are derived ONCE, beside the sunken ramps
(:func:`attach_wall_shade`), and travel as ``Airport.wall_shade``: every
pad reader — the mint (``classify/evidence``), its census
(``constraints/cluster_pad``) and the apron shelf (``planar/apron_shelf``)
— subtracts them through ``geom.pad_shade_extra``, the one path, so they
cannot disagree.  The wall's own levels are the wall terrace's, as at every
other retaining wall the pack ships under the pad bar."""
from __future__ import annotations

import dataclasses as _dc

from shapely.ops import unary_union

__all__ = ["wall_shade", "attach_wall_shade"]


def wall_shade(airport, cfg, comps=None):
    """The planar-frame union of every retaining wall's footprint, or
    ``None``.  ``cfg`` is ``classify/rules.toml``'s ``[service]`` record,
    supplied by the caller (``airport`` may not read ``classify``);
    ``comps`` the wall-class components when the caller has them."""
    if cfg is None or getattr(airport, "partition", None) is None:
        return None
    if comps is None:
        from .wall_class import wall_class_components
        comps = wall_class_components(airport, cfg)
    polys = [g for c in comps if c.retains for g in c.pieces]
    if not polys:
        return None
    got = unary_union(polys)
    if not got.is_valid:
        got = got.buffer(0.0)
    return None if got.is_empty else got


def attach_wall_shade(airport, cfg):
    """``airport`` with :attr:`Airport.wall_shade` and
    :attr:`Airport.retaining_walls` (``airport/wall_sides``) derived — one
    wall-class reading, called once beside
    :func:`airport.sunken_ramp.attach_sunken_ramps` (``pipeline/build``,
    the replay)."""
    if getattr(airport, "frame", None) is None:
        return airport
    comps = None
    if cfg is not None and getattr(airport, "partition", None) is not None:
        from .wall_class import wall_class_components
        comps = wall_class_components(airport, cfg)
    from .wall_sides import wall_sides
    return _dc.replace(airport, wall_shade=wall_shade(airport, cfg, comps),
                       retaining_walls=wall_sides(airport, cfg, comps))
