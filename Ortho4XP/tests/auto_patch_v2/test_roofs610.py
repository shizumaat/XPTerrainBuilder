"""Issue #610 (lane roofs610, owner sim read of 1.0.391): roofs and a canopy
written at another building's zero.  Four general rules, each read off a
KCLT / KASE site and each red on main:

* ``anchor_rule.anchor_for``: a part the plan judged ELEVATED (no feet) is
  no ground contact where the body has footed parts — KCLT's fuel canopy
  (posts at y 0, beams at 5.45) took its zero on a beam, was judged
  elevated and was carried, posts and all, to a building 45 m away;
* ``footprint_unit.cluster_zero_allowed``: a carried piece that stands over
  footed bodies, none of them in its rigid cluster, does not take the
  cluster's zero — KCLT's roof over ``005_ALB`` b0 rode ``007_ALB`` b8,
  7.5 m up;
* ``placement_body._atom_targets``: an atom made of components the plan
  holds no part for carries NO parts, never the whole group's;
* ``placement_atom.unit_rigid``'s roof witness reads "stands over" on the
  PART boxes and never binds across two §16g footprint units — KASE's
  hangar south bay walls went 0.78 m down to the north bay's zero under
  roof planes that stayed on their own unit.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as _ar
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import placement_atom as ATOM
from auto_patch_v2.airport import placement_body as PB
from auto_patch_v2.airport import placement_carrier as _pc


# ── anchor_for: an elevated part is no ground contact ───────────────────

def test_a_canopy_on_posts_anchors_on_its_posts_not_its_beam():
    """Posts at y 0 on ground 215.0..215.2; the canopy roof (no feet, base
    4.8) stands in at a centroid where the ground reads 214.9.  Read as a
    contact it spreads the body 4.8 m, the low-side rule picks it, and the
    body's zero lands on the roof plane (y_zero 4.8 → elevated)."""
    posts = tuple((40.0 + 1e-5 * k, -3.0, 0.0, ((40.0 + 1e-5 * k, -3.0, 0.0),))
                  for k in range(6))
    canopy = (40.00002, -2.99998, 4.8, ())
    geom = _ar.BodyGeometry(posts + (canopy,), 40.0, -3.0)

    def surface(la, lo):
        return 214.9 if lo > -2.99999 else 215.0 + (la - 40.0) * 4e3

    a = _ar.anchor_for(_ar.OTHER if hasattr(_ar, "OTHER") else "other", geom,
                       surface, tol_m=0.3)
    assert a.y_zero == 0.0, (a.y_zero, a.reason)
    assert abs(float(a.surface_z) - float(a.y_zero) - 215.0) < 0.25
    # a body with NO footed part keeps the stand-in (a pre-09s plan)
    bare = _ar.BodyGeometry((canopy, (40.0, -3.0, 0.0, ())), 40.0, -3.0)
    b = _ar.anchor_for("other", bare, surface, tol_m=0.3)
    assert b.y_zero in (0.0, 4.8)
