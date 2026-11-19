"""THE PAD UNDER A SLOPED BASE (owner RULINGS 2026-11-19o (1); #2184):
``planar/pad_base_slope`` + its readers.

THE CONSUMER CENSUS (RULINGS 2026-08-30l) — every pass that reads a pad's
LEVEL or TARGET, and what 19o (1) does to it.  Each row names a symbol the
twin imports, so a rename or a deletion fails here first.
"""
from __future__ import annotations

import importlib
import math
import types

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.law import Law
from auto_patch_v2.planar import pad_base_slope as PBS

#: (module, symbol, what it reads, 19o (1) ruling)
CENSUS = [
    ("auto_patch_v2.airport.obj8_grade", "base_profile",
     "the member's authored bottom: FLAT / STEPPED / SLOPED / FEET", "UNCHANGED (the read)"),
    ("auto_patch_v2.planar.pad_base_slope", "sloped_pads",
     "SLOPED + rms <= sloped_pad_rms_m -> the plane, per pad", "NEW: the one derivation"),
    ("auto_patch_v2.planar.platform", "platform_split",
     "which pads are HELD flat at a datum (unit / §4 conforming)",
     "EDITED: a sloped pad is never held"),
    ("auto_patch_v2.constraints.pad_relief", "pad_relief_offsets",
     "the per-vertex target above the pad's level", "EDITED: the plane merged in"),
    ("auto_patch_v2.constraints.pad_relief", "pad_slope_offsets",
     "the plane alone (target AND ceiling)", "NEW"),
    ("auto_patch_v2.constraints.pads", "pad_flats",
     "the plate: cap-0 pairs on the level plane", "EDITED: rel = plane; two-sided (leads its rim)"),
    ("auto_patch_v2.constraints.pads", "pad_slope_ceiling",
     "the hard 1 % pairs", "EDITED: from the plane, own head (stage 1), + hard one-plane rows"),
    ("auto_patch_v2.constraints.door_pad", "door_pads",
     "a building on a sloping apron is ONE level (#798)",
     "EDITED: a sloped-base pad is not a door pad"),
    ("auto_patch_v2.constraints.pads", "pad_frontage_level",
     "contact rows against the pavement's own value", "UNCHANGED (differences only)"),
    ("auto_patch_v2.constraints.platform", "frontage_hold_rows",
     "a held pad's contacts = its datum", "UNCHANGED (a sloped pad is not held)"),
    ("auto_patch_v2.constraints.no_step", "hold_interval",
     "a held block's datum interval", "UNCHANGED (not held)"),
    ("auto_patch_v2.constraints.platform", "platform_records",
     "a held block's datum / released contacts record", "UNCHANGED (not held)"),
    ("auto_patch_v2.constraints.pad_warning", "frontage_warning",
     "'seated flat at' — read off a held record", "UNCHANGED (not held: never said)"),
    ("auto_patch_v2.solve.project_strip", "_pad_plane",
     "a jetway strip's pad plane, capped at 1 % from flat",
     "UNCHANGED: no sloped pad carries a strip (stated, not built)"),
    ("auto_patch_v2.pipeline.publication", "pad_relief_offsets",
     "sidecar pad_relief", "UNCHANGED code: publishes the merged offsets"),
    ("auto_patch_v2.verify.pads", "pad_flat",
     "plane residual / slope on z - pad_relief", "UNCHANGED code: reads the plane via the sidecar"),
    # 2026-11-19q (1): the apron cap yields to the authored grade under the pad
    ("auto_patch_v2.constraints.pad_relief", "pad_slope_pair_caps",
     "the plane's grade along every pair of one sloped pad", "NEW (19q): the one derivation"),
    ("auto_patch_v2.constraints.apron", "apron_within_shape",
     "the apron's hard 1.5 % rows",
     "EDITED (19q): a pad pair's row lifted to the plane (the 11-05a lift)"),
    ("auto_patch_v2.verify.pads", "sloped_plane_offsets",
     "which emitted vertices lie on one sloped pad's plane",
     "NEW (19q): the verify's read of the sidecar"),
    ("auto_patch_v2.verify.within", "within_shape",
     "apron / pad pairs at the 1.5 % cap",
     "EDITED (19q): one sloped pad's pairs at the plane's grade"),
    ("auto_patch_v2.verify.pads", "planar_relief",
     "a relief that is ONE plane (census pad_airside_weld + verify)",
     "NEW (19q): the census's _planar_relief delegates here; the census within-shape already "
     "reads a pad pair against the plane (check_grade pad_relief_by_nid offsets)"),
]


@pytest.mark.parametrize("mod,sym,_reads,_rule", CENSUS)
def test_every_census_row_names_a_live_symbol(mod, sym, _reads, _rule):
    assert hasattr(importlib.import_module(mod), sym)


def _law() -> Law:
    return Law.for_airport("KXYZ")


def _to_xy(lon: float, lat: float) -> tuple[float, float]:
    """A plain local frame: metres east / north of (0, 0) at the equator."""
    from auto_patch_v2.model.frame import m_per_deg_exact
    ml, mo = m_per_deg_exact(0.0)
    return (lon * mo, lat * ml)


def _member(slope=(-0.019, 0.00014), rms=0.001, heading=249.387961, verdict="sloped",
            res="Objects/canopy.obj"):
    return types.SimpleNamespace(
        resource=res, heading_deg=heading, origin=(0.0, 0.0),
        base_profile={"verdict": verdict, "slope": list(slope), "residual_rms_m": rms})


def test_the_authored_gradient_turns_with_the_placement_heading():
    f = PBS._member_field(_member(), _to_xy, 0.05)
    # +x of the object points to bearing heading + 90: the base falls that way
    assert f.authored == pytest.approx(0.019, abs=1e-4)
    assert f.gx == pytest.approx(0.00682, abs=5e-5)
    assert f.gy == pytest.approx(-0.01774, abs=5e-5)
    h = math.radians(249.387961 + 90.0)
    assert f.offset(100 * math.sin(h), 100 * math.cos(h)) == pytest.approx(-1.9, abs=0.01)


def test_a_steeper_base_is_capped_at_the_pavement_law_keeping_its_direction():
    f = PBS._member_field(_member(slope=(0.08, 0.0), heading=90.0), _to_xy, 0.05)
    assert f.authored == pytest.approx(0.08, abs=1e-6)
    assert f.grade == pytest.approx(0.05, abs=1e-6)
    assert math.hypot(f.gx, f.gy) == pytest.approx(0.05, abs=1e-6)


def _to_ll(x: float, y: float) -> tuple[float, float]:
    from auto_patch_v2.model.frame import m_per_deg_exact
    ml, mo = m_per_deg_exact(0.0)
    return (y / ml, x / mo)


def _airport(members, ring_m=(-10.0, -10.0, 10.0, 10.0)):
    x0, y0, x1, y1 = ring_m
    ll = [_to_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    unit = types.SimpleNamespace(id="unit:0", members=members)
    cl = types.SimpleNamespace(rings=[ll], unit="unit:0",
                               members=tuple({m.resource for m in members}))
    return types.SimpleNamespace(clusters=(cl,), partition=types.SimpleNamespace(units=[unit]),
                                 frame=types.SimpleNamespace(entry=lambda: _to_xy))


def _square(h=10.0):
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h)])


def test_a_planar_sloped_base_gives_its_pad_the_plane():
    got = PBS.sloped_pads([("building1", _square())], _airport([_member()]), _law())
    assert set(got) == {"building1"}
    assert got["building1"].grade == pytest.approx(0.019, abs=1e-4)


@pytest.mark.parametrize("member", [
    _member(rms=0.2),                 # uneven contact geometry, not a plane
    _member(verdict="flat"),          # 09c stands
    _member(verdict="feet"),          # posts with no plane fit: not this law
    _member(verdict="stepped"),
])
def test_only_a_planar_sloped_base_is_read(member):
    assert PBS.sloped_pads([("building1", _square())], _airport([member]), _law()) == {}


def test_placements_of_one_cluster_that_disagree_give_no_plane():
    a = _airport([_member(), _member(heading=0.0)])
    assert PBS.sloped_pads([("building1", _square())], a, _law()) == {}


def test_a_pad_the_cluster_covers_under_half_of_takes_no_plane():
    a = _airport([_member()], ring_m=(-10.0, -10.0, -4.0, 10.0))   # 30 % of the pad
    assert PBS.sloped_pads([("building1", _square())], a, _law()) == {}


def test_the_census_weld_reads_a_planar_relief_and_only_that():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from check_grade import _planar_relief
    pts = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0)]
    plane = [0.0, 0.19, 0.05, 0.24]
    assert _planar_relief(pts, plane) == pytest.approx(plane)
    assert _planar_relief(pts, [0.0, 0.5, 0.0, 0.0]) is None       # per-foot (12u)
    assert _planar_relief(pts, [0.0, 0.19, None, 0.24]) is None


def test_the_apron_lift_is_the_plane_grade_along_pairs_of_one_pad_only(monkeypatch):
    """19q (1): ``pad_slope_pair_caps`` lifts the pairs of ONE sloped pad
    (footprint + shared rim) to the plane's grade along them — never a
    pair reaching off the pad."""
    from auto_patch_v2.constraints import pad_relief as PR
    f = PBS.SlopeField(0.019, 0.0, 0.0, 0.0, 0.019, 0.019, "canopy")
    xy = {1: (0.0, 0.0), 2: (20.0, 0.0), 3: (0.0, 10.0), 4: (40.0, 0.0)}
    pm = types.SimpleNamespace(vertices={v: types.SimpleNamespace(xy=p) for v, p in xy.items()})
    monkeypatch.setattr(PR, "_sloped_groups", lambda *_a: {"building1": (f, {1, 2, 3})})
    caps = PR.pad_slope_pair_caps(pm, None, None)
    assert caps[(1, 2)] == pytest.approx(0.019)            # along the axis: the authored grade
    assert caps[(2, 3)] == pytest.approx(0.38 / math.hypot(20, 10))
    assert (1, 3) not in caps                              # across the axis: no lift
    assert all(4 not in k for k in caps)                   # off the pad: unchanged


def test_the_apron_hard_row_takes_the_lift_and_keeps_its_preference():
    from auto_patch_v2.constraints.apron import _Tier
    from auto_patch_v2.model.constraints import Source
    t = _Tier(7, "dsf:pol43", 0.015, 0.010, lift={(1, 2): 0.019})
    src = Source("apron", "common.roles.apron ring edge (2026-08-21b)", ("face:7",))
    hard, pref = t.rows(2, 1, 20.0, src)
    assert hard.cap == pytest.approx(0.019) and hard.soft is None
    assert pref.cap == pytest.approx(0.010) and pref.soft
    assert t.rows(1, 3, 20.0, src)[0].cap == pytest.approx(0.015)


def test_the_verify_reads_one_pads_plane_and_a_shared_rim_vertex_on_both():
    from auto_patch_v2.verify.pads import sloped_pair_cap
    # vertex 2 is the rim two sloped pads (shapes 0 and 1) share
    sloped = {1: {0: 0.0}, 2: {0: 0.38, 1: 0.38}, 3: {1: 0.76}, 4: {}}
    assert sloped_pair_cap(sloped, 1, 2, 20.0) == pytest.approx(0.019)
    assert sloped_pair_cap(sloped, 2, 3, 20.0) == pytest.approx(0.019)
    assert sloped_pair_cap(sloped, 1, 3, 40.0) == 0.0      # two pads: no one plane
    assert sloped_pair_cap(sloped, 1, 9, 20.0) == 0.0      # off any pad


def test_the_census_and_the_verify_share_one_planar_relief_reading():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from check_grade import _planar_relief
    from auto_patch_v2.verify.pads import planar_relief
    pts = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0)]
    for offs in ([0.0, 0.19, 0.05, 0.24], [0.0, 0.5, 0.0, 0.0]):
        assert _planar_relief(pts, offs) == planar_relief(pts, offs)
