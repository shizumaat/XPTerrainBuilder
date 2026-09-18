"""§43 AN APRON ENDS AT ITS MOUTH (owner RULINGS 2026-09-14c item 2;
Fable 2026-09-14; lane ``v2apronneck``) as synthetic twins.

The three the brief names, plus the two traps the HECA arms measured:

1. a DUMBBELL — two wide lobes joined by a 40 m neck 100 m long — is ONE
   neck, cut into three pieces, the middle one the corridor;
2. a wide apron with a 40 m-wide, 30 m-long NOTCH is not cut (under
   ``apron_neck_length_m``);
3. a 40 m taxiway running ALONG an apron edge is not cut (nothing
   narrows: the erosion has one part);
4. THE FRINGE (measured HECA 2026-09-14 arm 1, ``neck._separates``): the
   rim of a wide L-shaped apron is narrow everywhere and connected all
   the way round, so it touches every lobe — it is not a neck, because
   removing it separates nothing.  Without this the first arm cut a
   253,634 m² HECA apron on an 8.3 m, 19-mouth "neck";
5. §41 (1) DOES NOT RE-ABSORB A NECK CUT (the brief's question): the
   three pieces of the dumbbell go through ``planar/overlay.
   absorb_enclosed_pavement`` — the same call the arrangement makes —
   and NOTHING is absorbed.  The guarantee is geometric: every piece of
   a chord split of one face keeps a run of the parent's own exterior
   ring, so no piece lies 95 % inside another piece's exterior ring.

Plus the law-table twin: the two keys exist, carry the spec's values and
appear NOWHERE as a literal in Python (``rules.toml`` is the law).
"""
from __future__ import annotations

import dataclasses as _dc
import pathlib
import re

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from auto_patch_v2.classify.neck import necks_of, split_at_necks
from auto_patch_v2.classify.rules import load_rules

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _dumbbell(neck_w: float = 40.0, neck_l: float = 100.0):
    """Two 200x200 lobes joined by a ``neck_w`` x ``neck_l`` neck."""
    y0 = 100.0 - neck_w / 2.0
    return unary_union([box(0, 0, 200, 200),
                        box(200, y0, 200 + neck_l, y0 + neck_w),
                        box(200 + neck_l, 0, 400 + neck_l, 200)])


def test_dumbbell_is_one_neck_cut_into_three(rules):
    face = _dumbbell()
    necks = necks_of(face, rules)
    assert len(necks) == 1
    n = necks[0]
    assert n.n_lobes == 2
    # the length is the neck's own run, not the face's extent
    assert n.length_m == pytest.approx(100.0, abs=2.0)
    assert n.width_m <= rules.corridor.max_width_m
    assert n.kind == "neck"
    # two mouth CUT LINES, each a chord about the neck's width across
    assert len(n.mouth_lines) == 2
    for (ax, ay), (bx, by) in n.mouth_lines:
        assert ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 == pytest.approx(40.0, abs=2.0)
    pieces = split_at_necks(face, necks, rules)
    assert len(pieces) == 3
    assert sum(1 for _p, is_neck in pieces if is_neck) == 1
    neck_piece = next(p for p, is_neck in pieces if is_neck)
    assert neck_piece.area == pytest.approx(40.0 * 100.0, rel=0.05)
    # nothing is lost or duplicated by the cut
    assert sum(p.area for p, _n in pieces) == pytest.approx(face.area, rel=1e-3)


def test_short_notch_is_not_cut(rules):
    """A 40 m-wide, 30 m-long bite out of an apron edge: under
    ``apron_neck_length_m``, so one apron, no cut."""
    assert necks_of(_dumbbell(neck_l=30.0), rules) == []


def test_taxiway_along_an_apron_edge_does_not_cut(rules):
    """§43 (3): a 40 m taxiway running ALONG an apron edge shares a
    boundary and never narrows — the erosion has ONE part."""
    face = unary_union([box(0, 0, 400, 200), box(0, -40, 400, 0)])
    assert necks_of(face, rules) == []


def test_the_fringe_of_a_wide_apron_is_not_a_neck(rules):
    """The trap the HECA arm measured: an L-shaped apron's own rim is
    narrow and connected all the way round, so it touches every lobe of
    the erosion — but removing it separates nothing."""
    face = unary_union([box(0, 0, 300, 300), box(300, 0, 600, 120)])
    assert necks_of(face, rules) == []
    assert necks_of(box(0, 0, 300, 300), rules) == []


def test_neck_cut_survives_section_41_absorption(rules):
    """§41 (1) must not re-absorb a §43 cut: a face bounded by a cut line
    is never 95 % inside its neighbour's exterior ring."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.overlay import Region, absorb_enclosed_pavement
    law = Law.for_airport("CYXY")
    face = _dumbbell()
    pieces = split_at_necks(face, necks_of(face, rules), rules)
    faces = [(p, Region("junction" if is_neck else "apron",
                        f"neck{i}", p, None, None, "airside", "cell"))
             for i, (p, is_neck) in enumerate(pieces)]
    out, absorbed, detached = absorb_enclosed_pavement(
        faces, tuple(law.tables.emit.terrace.shape_roles),
        mouth_m=law.tables.emit.terrace.narrow_mouth_max_m)
    assert absorbed == 0 and detached == 0
    assert len(out) == len(faces)


def test_neck_widths_are_law_not_literals(rules):
    """The keys live in ``classify/rules.toml`` and nowhere else, and §43
    (1) AMENDED reads ONE width — ``corridor.max_width_m``."""
    assert rules.corridor.max_width_m == 50.0
    assert rules.apron.neck_length_m == 60.0
    assert rules.apron.arm_min_aspect == 3.0
    assert rules.apron.arm_mouth_max_factor == 2.5
    assert not hasattr(rules.apron, "neck_width_m")   # retired by 17x (3)
    lit = re.compile(r"(neck_\w+|arm_\w+|max_width_m)\s*[=:]\s*"
                     r"\(?\s*(45|50|60|3|2)\.\d")
    bad = [(p.name, line.strip()) for p in SRC.rglob("*.py")
           for line in p.read_text().splitlines()
           if lit.search(line) and not line.lstrip().startswith("#")]
    assert not bad, bad


def test_thresholds_are_read_from_the_table(rules):
    """Every key actually steers the verdict (a table nobody reads is not
    law): the same dumbbell reads as a neck or not as the keys move."""
    wide = _dc.replace(rules, corridor=_dc.replace(rules.corridor,
                                                   max_width_m=20.0))
    assert necks_of(_dumbbell(), wide) == []        # 40 m is not narrow at 20
    longer = _dc.replace(rules, apron=_dc.replace(rules.apron,
                                                  neck_length_m=400.0))
    assert necks_of(_dumbbell(), longer) == []      # 100 m is not long at 400


# ── §43 (1) AMENDED (owner RULINGS 2026-09-17x item 3) ───────────────
# "We should be able to identify that the vast majority of this shape is
# not apron because it follows a path and is under 50m wide, the only
# portion that's apron is the small square here ... about 70m square."


def _pav188(arm_w: float = 45.0, arm_l: float = 500.0, sq: float = 70.0):
    """The owner's LEMD ``pav188``: a ~70 m square with a dead-end band
    running off it — ONE wide lobe, so today's neck rule sees nothing."""
    y0 = sq / 2.0 - arm_w / 2.0
    return unary_union([box(0, 0, sq, sq),
                        box(sq, y0, sq + arm_l, y0 + arm_w)])


def test_dead_end_arm_is_cut_although_it_leaves_one_lobe(rules):
    face = _pav188()
    necks = necks_of(face, rules)
    assert len(necks) == 1 and necks[0].kind == "arm"
    n = necks[0]
    assert n.n_lobes == 1                       # ONE wide lobe, not two
    assert n.width_m <= rules.corridor.max_width_m
    assert n.aspect >= rules.apron.arm_min_aspect
    assert n.mouth_factor <= rules.apron.arm_mouth_max_factor
    pieces = split_at_necks(face, necks, rules)
    assert len(pieces) == 2
    arm = next(p for p, is_neck in pieces if is_neck)
    square = next(p for p, is_neck in pieces if not is_neck)
    assert arm.area > square.area               # "the vast majority"
    assert square.area == pytest.approx(70.0 * 70.0, rel=0.25)
    assert sum(p.area for p, _n in pieces) == pytest.approx(face.area, rel=1e-3)


def test_a_wide_arm_is_not_cut(rules):
    """A 60 m-wide band is not under the width anywhere: apron, untouched
    (the amendment's own ceiling, the owner's 50 m)."""
    assert necks_of(_pav188(arm_w=60.0), rules) == []


def test_a_short_stub_is_not_a_path(rules):
    """The brief's bar: a stub whose run is about twice its width does not
    FOLLOW A PATH — ``arm_min_aspect``."""
    assert necks_of(_pav188(arm_w=45.0, arm_l=90.0), rules) == []


def test_the_arm_rule_leaves_the_dumbbell_alone(rules):
    """A 45 m arm BETWEEN two lobes is unchanged from today: still one
    NECK, still three pieces."""
    face = _dumbbell(neck_w=45.0, neck_l=200.0)
    necks = necks_of(face, rules)
    assert len(necks) == 1 and necks[0].kind == "neck"
    assert necks[0].n_lobes == 2
    assert len(split_at_necks(face, necks, rules)) == 3


def test_the_fringe_is_not_an_arm(rules):
    """The 09-14 HECA trap, re-run under the amendment: the rim of a wide
    apron is long and thin, but it is attached along its whole length and
    the MOUTH FACTOR refuses it."""
    for face in (box(0, 0, 300, 300),
                 unary_union([box(0, 0, 300, 300), box(300, 0, 600, 120)]),
                 box(0, 0, 900, 400)):
        assert [n.kind for n in necks_of(face, rules)] == []
