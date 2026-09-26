"""Twins for lane ``spjcpads`` (issues #3 / #4, Beta 2 blockers) and owner
RULINGS 2026-09-23a — APRON DOES NOT EXTEND UNDER BUILDING PADS.

1. ``placement_family.member_is_deck`` — the deck VERDICT is ``flag`` /
   ``signature`` (or a ``deck_ring``); ``candidate`` is the signature pass
   having LOOKED, and a tall body carrying it is WALLED, not a leaf.
   MEASURED at SPJC: ``objectzannes/terminal.obj`` (61.57 m, 99,080 m2)
   was a leaf through that misread and lost its pad.
2. ``deck_signature._plate`` — a plate whose rectangle enters the frame as
   nothing is no plate (SPJC's 0.00004 m ``Costa del sol`` slivers aborted
   every planar replay in ``way_cover`` on ``None.is_empty``).
3. ``tools/v2_solve_replay.py --from classify`` / ``--placement`` /
   ``--pad-read`` — the replay-time pad arm refuses a resume that cannot
   see the key, before the capture is read.
4. RULINGS 2026-09-23a — a building over the apron keeps its FOOTPRINT as
   its pad; the apron is cut back to the pad edge; the shared edge is one
   vertex set (the §16g (10) (6) ``pad_airside_weld``); the runway is not
   apron and still trims the pad; ``pad_keeps_footprint = false`` is the
   pre-23a clip.
"""
from __future__ import annotations

import dataclasses as _dc
import importlib.util
import types
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import deck_signature as _ds
from auto_patch_v2.airport.placement_family import (DECK_VERDICTS,
                                                    member_is_deck,
                                                    plan_clusters)
from auto_patch_v2.law import Law

from test_v2connector import _blk, _lat, _PMember, _PPart, _PPlan, _PUnit  # noqa: E402
from test_v2padvert import _renode_scene  # noqa: E402


# ── 1. member_is_deck ───────────────────────────────────────────────────

def _m(kind="", ring=None):
    return types.SimpleNamespace(deck_kind=kind, deck_ring=ring)


def test_member_is_deck_reads_the_verdict_not_the_look():
    assert DECK_VERDICTS == frozenset({"flag", "signature"})
    assert member_is_deck(_m("flag")) and member_is_deck(_m("signature"))
    assert member_is_deck(_m("", ring=((0, 0), (1, 0), (1, 1))))
    # ``candidate`` is the signature pass having LOOKED — not a verdict
    assert not member_is_deck(_m("candidate"))
    assert not member_is_deck(_m("")) and not member_is_deck(None)


def _tall(pid, la0, la1, height=60.0):
    p = _PPart(pid, _blk(la0, la1, -3.0000, -2.9990))
    p.base_y = 0.0
    p.height_m = height
    p.feet = ((p.lat, p.lon, 0.0),)
    p.rings = (((la0, -3.0000), (la1, -3.0000), (la1, -2.9990), (la0, -2.9990)),)
    return p


def test_a_tall_candidate_body_is_WALLED_and_a_verdict_deck_is_a_leaf():
    """The SPJC terminal: one body 61.57 m tall carrying
    ``deck_kind='candidate'``.  Before the fix both ``plan_clusters`` and
    ``footprint_unit`` read any non-empty ``deck_kind`` as a deck, so the
    terminal was a LEAF (``leaf_dropped``) and minted no derived pad."""
    def walled(kind):
        m = _PMember("objects/terminal.obj", [_tall(1, _lat(0), _lat(40))])
        m.deck_kind = kind
        plan = _PPlan([_PUnit("unit:0", [m])], ())
        got = plan_clusters(plan, 0.5, chain_min_height_m=2.5)
        assert len(got) == 1
        return got[0].walled

    assert walled("") == 1
    assert walled("candidate") == 1          # the SPJC terminal
    assert walled("signature") == 0          # a real deck is a leaf
    assert walled("flag") == 0


# ── 2. _plate: a rectangle that enters as nothing ───────────────────────

def _plate_inputs():
    geom = types.SimpleNamespace(
        vertices=np.array([[0.0, 5.0, 0.0], [40.0, 5.0, 0.0],
                           [40.0, 5.0, 12.0], [0.0, 5.0, 12.0]]),
        solid=np.array([[0, 1, 2], [0, 2, 3]]))
    f = _ds._Faces(geom)
    inplane = np.ones(f.n, dtype=bool)
    br = Law.for_airport("ZZZZ").tables.structures.bridge
    o = types.SimpleNamespace(id="o1", path="objects/slab.obj", xy=(0.0, 0.0),
                              heading_deg=0.0)
    return o, f, inplane, br


def test_a_plate_whose_rectangle_enters_as_nothing_is_no_plate(monkeypatch):
    o, f, inplane, br = _plate_inputs()
    # the positive control: the same slab IS a plate
    assert _ds._plate(o, f, inplane, 0.0, br, ()) is not None
    real = _ds._fe.enter

    def _rect_gone(geoms, mat, q=0.0):
        foot, _rect = real(geoms, mat, q)
        return foot, None

    monkeypatch.setattr(_ds._fe, "enter", _rect_gone)
    assert _ds._plate(o, f, inplane, 0.0, br, ()) is None


# ── 3. the replay's pad arm ─────────────────────────────────────────────

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "v2_solve_replay.py"


def _replay_module():
    spec = importlib.util.spec_from_file_location("_v2_solve_replay_spjc", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_replay_pad_arm_refuses_a_resume_that_cannot_see_it(tmp_path):
    """A pad key is read at classify / planar; ``--from constraints`` or
    ``--from shapes`` re-use the captured arrangement, so the arm would be
    silently inert.  Refused BEFORE the (multi-GB) capture is opened — the
    pickle path here does not even exist."""
    mod = _replay_module()
    missing = tmp_path / "absent.pkl"
    for resume in ("constraints", "shapes"):
        with pytest.raises(SystemExit, match="--from classify"):
            mod.replay_problem(missing, resume, [],
                               placement={"pad_keeps_footprint": "false"})
        with pytest.raises(SystemExit, match="--from classify"):
            mod.replay_problem(missing, resume, [], pad_read_only=True)
    law = Law.for_airport("ZZZZ")
    arm, kw = mod._placement_override(law, {"pad_keeps_footprint": "false"})
    assert kw == {"pad_keeps_footprint": False}
    assert arm.tables.structures.placement.pad_keeps_footprint is False
    assert law.tables.structures.placement.pad_keeps_footprint is True


def test_from_classify_is_a_replay_resume():
    src = _TOOL.read_text()
    assert '"classify"' in src and "--pad-read" in src


# ── 4. RULINGS 2026-09-23a ──────────────────────────────────────────────

def _law(keeps=True):
    law = Law.for_airport("ZZZZ")
    p = _dc.replace(law.tables.structures.placement, pad_airside_clip=True,
                    pad_keeps_footprint=keeps)
    st = _dc.replace(law.tables.structures, placement=p)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st))


# the fixture's apron is (-200..200, 100..300); this terminal stands 80 %
# on it and hangs 40 m off its north edge
_TERMINAL = ((-60, 140), (60, 140), (60, 340), (-60, 340))


def _faces(arr, role):
    return [(p, r) for p, r in arr.faces if r.role == role]


def test_23a_the_pad_keeps_its_footprint_and_the_apron_is_cut_back():
    from auto_patch_v2.planar.overlay import PAD_AIRSIDE
    arr = _renode_scene(_law(True), _TERMINAL)
    pad = unary_union([p for p, _r in _faces(arr, "building")])
    foot = Polygon(_TERMINAL)
    # THE PAD IS THE FOOTPRINT — every square metre, in ONE face
    assert len(_faces(arr, "building")) == 1
    assert pad.area == pytest.approx(foot.area, rel=1e-6)
    assert pad.symmetric_difference(foot).area < 1.0
    # THE APRON DOES NOT EXTEND UNDER IT
    apron = unary_union([p for p, _r in _faces(arr, "apron")])
    assert apron.intersection(pad).area < 1e-6
    assert apron.area == pytest.approx(400 * 200 - 120 * 160, rel=1e-6)
    # THE WELD: the shared edge is ONE vertex set (node identity, 09-01g)
    pv = {c for p, _r in _faces(arr, "building") for c in p.exterior.coords}
    av = {c for p, _r in _faces(arr, "apron")
          for ring in (p.exterior, *p.interiors) for c in ring.coords}
    shared = pv & av
    assert {(-60.0, 140.0), (60.0, 140.0)} <= shared
    assert PAD_AIRSIDE["apron_faces_cut"] == 1
    assert PAD_AIRSIDE["pad_airside_weld_pairs"] == 1
    # the pad re-nodes nothing the cut airside did not already carry
    assert PAD_AIRSIDE["renode_deleted"] == 0
    assert PAD_AIRSIDE["renode_minted"] == 0, dict(PAD_AIRSIDE)


def test_23a_matched_base_the_pre_23a_clip_takes_the_apron_out_of_the_pad():
    arr = _renode_scene(_law(False), _TERMINAL)
    pad = unary_union([p for p, _r in _faces(arr, "building")])
    # only the 40 m hanging off the apron survives the old clip
    assert pad.area == pytest.approx(120 * 40, rel=0.05)


def test_23a_a_pad_wholly_on_the_apron_is_still_the_footprint():
    arr = _renode_scene(_law(True), ((-50, 150), (50, 150), (50, 250), (-50, 250)))
    pad = unary_union([p for p, _r in _faces(arr, "building")])
    assert pad.area == pytest.approx(100 * 100, rel=1e-6)
    apron = _faces(arr, "apron")
    # the apron keeps the pad as a HOLE, welded along the hole's ring
    assert any(len(p.interiors) == 1 for p, _r in apron)


def test_23a_the_runway_is_not_apron_and_still_trims_the_pad():
    """23a speaks of the apron.  A pad never takes a runway (airside is
    king, 14ah): the fixture's runway strip is y in [-22.5, 22.5]."""
    from auto_patch_v2.planar.overlay import PAD_AIRSIDE
    arr = _renode_scene(_law(True), ((300, 0), (380, 0), (380, 80), (300, 80)))
    pad = unary_union([p for p, _r in _faces(arr, "building")])
    runway = unary_union([p for p, _r in _faces(arr, "runway")])
    assert pad.intersection(runway).area < 1e-6
    assert pad.area == pytest.approx(80 * (80 - 22.5), rel=1e-3)
    assert PAD_AIRSIDE["pad_trimmed_by_runway_taxi_m2"] == pytest.approx(
        80 * 22.5, rel=1e-3)
