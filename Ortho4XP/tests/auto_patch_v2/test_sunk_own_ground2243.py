"""#2243: a SUNK row's own-ground body keeps its authored frame zero.

A tower row authored ``OBJECT_AGL -80`` (its masts' feet buried 80 m under
the ground at its anchor, the lights 21.66 m over it) reaches down a slope
off a runway end.  §16 (3)'s own-ground seat stood ``y = 0`` on the ground
under the cut body's footprint, 40 m under the anchor's ground, and the
lights rose 40 m + 80 m over their authored height into the approach path.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_file as PF

#: the anchor at the runway end (ground 63.6 m), the footprint down the
#: slope (ground 22.6 m)
_ANCHOR = (64.1800, -51.6876)
_FOOT_BOX = (64.1778, -51.6894, 64.1802, -51.6873)


def _surface(la: float, lo: float) -> float:
    return 63.6 if (la, lo) == _ANCHOR else 22.6


def _file(agl: float):
    part = types.SimpleNamespace(pid="p0", comp=0, box=_FOOT_BOX, feet=())
    anchor = AR.Anchor("other", *_ANCHOR, 0.0, "", None)
    raw = [([part], "other", anchor, (), True, (), ((64.179, -51.688, 90.0),), None)]
    m = types.SimpleNamespace(resource="objects/towers.obj", heading_deg=108.6)
    u = types.SimpleNamespace(anchor=_ANCHOR, agl_m=agl)
    counts: dict = {}
    body = PF._own_ground_file(raw, [0], m, u, _surface, 0, counts, {})
    return body.anchor, counts


def test_sunk_row_keeps_its_authored_zero():
    a, counts = _file(-80.0)
    zero = float(a.surface_z) - float(a.y_zero)
    assert abs(zero - (63.6 - 80.0)) < 1e-9          # the anchor's ground + its lift
    assert abs(float(a.surface_z) - 22.6) < 1e-9     # written at its own ground
    assert "sunk row" in a.reason and "#2243" in a.reason
    assert counts["footless_own_ground"] == 1


def test_row_on_the_ground_keeps_the_footprint_seat():
    """AGL 0 / lifted rows: §16 (3) unchanged — y = 0 on the ground under
    the footprint."""
    for agl in (0.0, 8.5):
        a, _ = _file(agl)
        assert float(a.y_zero) == 0.0
        assert abs(float(a.surface_z) - 22.6) < 1e-9


def test_sunk_row_without_an_anchor_ground_falls_back():
    u = types.SimpleNamespace(anchor=_ANCHOR, agl_m=-80.0)
    assert PF._sunk_zero(lambda la, lo: None, u, 22.6) is None
    assert PF._sunk_zero(_surface, u, None) is None


def test_a_piece_of_a_cut_model_keeps_the_footprint_seat():
    """A sunk ground plate cut into pieces over a kilometre of relief: each
    piece stands on its own ground (§16 (3)), never at the anchor's."""
    part = types.SimpleNamespace(pid="p0", comp=0, box=_FOOT_BOX, feet=())
    anchor = AR.Anchor("other", *_ANCHOR, 0.0, "", None)
    one = ([part], "other", anchor, (), True, (), ((64.179, -51.688, 0.0),), None)
    m = types.SimpleNamespace(resource="objects/plate.obj", heading_deg=0.0)
    u = types.SimpleNamespace(anchor=_ANCHOR, agl_m=-0.3)
    body = PF._own_ground_file([one, one], [0], m, u, _surface, 0, {}, {})
    assert float(body.anchor.y_zero) == 0.0
