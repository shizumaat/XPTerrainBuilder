"""Twins for the BASE PROFILE's PUBLICATION — ``docs/specs/building-base-
profile-spec.md`` §1 (4), owner RULINGS 2026-10-01f / 10-01k.  Lane
``basepads1``, round 2.

§1 (4) says the profile is derived ONCE, at the pack read, and READ from
the plan by everyone else.  Round 1 landed the derivation
(``obj8_grade.base_profile``, ``compose_profiles``) and the ref grammar;
nothing carried the record off the pack read.  These twins pin the carry:

* ONE CODEC (``profile_to_json`` / ``profile_from_json``), so the plan,
  the sidecar and ``tools/obj8_split_report --base-profile`` cannot drift
  into two spellings of one record — the census-wrapper defect class
  (RULINGS 2026-08-30l), and §6's STOP: *"any ``--base-profile`` read
  that disagrees with the planar stage's published planes (two readers of
  one law)"*.
* The FACE UNION survives the round trip as a union — a MULTIPOLYGON
  stays two pieces.  §1 (1) forbids the bbox and the hull, and §4
  measured KASE's ``FireStation_7`` lot as "6,394 m² in two pieces": a
  codec that flattened it to one outer ring would re-introduce exactly
  the claim §1 (1) exists to forbid.
* A plan written BEFORE the read (version < 11) reads as FEET with no
  plane — §1 (3)'s *"a unit with no base plane keeps today's law
  exactly"* — so an owner's older plan still replays with the pre-base
  seat instead of raising.
* The report RE-DERIVES NOTHING and labels its roll-up.

Hermetic and synthetic: no corpus, no network, no OBJ on disk except the
ones written into ``tmp_path`` with an explicit ``encoding=`` /
``newline=`` (the Windows text-IO law, ``tests/test_windows_text_io.py``).
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from shapely.geometry import MultiPolygon, Polygon

from auto_patch_v2.airport import obj8_grade as BG
from auto_patch_v2.model.rebake import (PLAN_VERSION, Member, Part,
                                        RebakePlan, Unit)


def _sq(x0, z0, w, d):
    return Polygon([(x0, z0), (x0 + w, z0), (x0 + w, z0 + d), (x0, z0 + d)])


def _stepped() -> BG.BaseProfile:
    """§1 (2) STEPPED, as the derivation mints it: two base planes, the
    origin plane first, one riser of +3.9 (KASE site 2's reading)."""
    return BG.BaseProfile(
        verdict=BG.STEPPED,
        planes=(BG.BasePlane(y=0.0, area_m2=1200.0, polygon=_sq(0, 0, 40, 30),
                             support_fraction=0.01, trimmed_m2=0.0),
                BG.BasePlane(y=3.9, area_m2=6394.0,
                             polygon=MultiPolygon([_sq(50, 0, 60, 60),
                                                   _sq(130, 0, 20, 20)]),
                             support_fraction=0.002, trimmed_m2=31.0)),
        risers=(BG.Riser(0, 1, 3.9),),
        residual_rms_m=0.0, feet=1041, feet_y=-0.2,
        floor_fraction=0.87, why="two level clusters over the area floor")


def _member(mid: str, prof: BG.BaseProfile | None, *, base_y: float = 0.0,
            resource: str = "objects/FireStation_7.obj") -> Member:
    part = Part(0, 0, 39.22, -106.87, base_y, 1200.0, (0.0, 1.0, 0.0, 1.0),
                ((39.22, -106.87, base_y),), False, (), 6.0)
    return Member(id=mid, resource=resource, authored_path="/p/" + resource,
                  live_path="/p/" + resource, heading_deg=17.0, parts=(part,),
                  base_profile={} if prof is None else BG.profile_to_json(prof))


def _plan(*members: Member) -> RebakePlan:
    return RebakePlan(icao="ZZZZ", pack_name="fixture", pack_root="/p",
                      units=(Unit(id="unit:108", anchor=(39.22, -106.87),
                                  agl_m=0.0, members=tuple(members)),),
                      skipped=(), counts={})


# ---------------------------------------------------------------- the codec

def test_the_codec_round_trips_every_field():
    """ONE CODEC, and it loses nothing the planar stage reads."""
    a = _stepped()
    b = BG.profile_from_json(BG.profile_to_json(a))
    assert b.verdict == a.verdict == BG.STEPPED
    assert len(b.planes) == len(a.planes) == 2
    assert [p.y for p in b.planes] == [p.y for p in a.planes]
    assert [p.area_m2 for p in b.planes] == [p.area_m2 for p in a.planes]
    assert ([p.support_fraction for p in b.planes]
            == [p.support_fraction for p in a.planes])
    assert [p.trimmed_m2 for p in b.planes] == [p.trimmed_m2 for p in a.planes]
    assert [(r.a, r.b, r.dy) for r in b.risers] == [(0, 1, 3.9)]
    assert b.offsets == a.offsets == (0.0, 3.9)
    assert (b.feet, b.feet_y) == (1041, -0.2)
    assert b.floor_fraction == pytest.approx(0.87)
    assert b.residual_rms_m == 0.0 and b.why == a.why


def test_the_codec_is_json_safe():
    """The record goes into ``rebake.json`` — it must survive
    ``json.dumps``/``loads`` with no custom encoder."""
    d = BG.profile_to_json(_stepped())
    back = BG.profile_from_json(json.loads(json.dumps(d, sort_keys=True)))
    assert back.verdict == BG.STEPPED and len(back.planes) == 2


def test_a_two_piece_face_union_stays_two_pieces():
    """§1 (1) / §4: KASE's lot is 6,394 m² IN TWO PIECES.  A codec that
    flattened the union to one outer ring would hand the planar stage a
    polygon that CONTAINS the building between the pieces — exactly the
    claim §1 (1) forbids the bbox and the hull for."""
    a = _stepped()
    b = BG.profile_from_json(BG.profile_to_json(a))
    upper = b.planes[1].polygon
    assert isinstance(upper, MultiPolygon)
    assert len(upper.geoms) == 2
    assert upper.area == pytest.approx(a.planes[1].polygon.area)
    # and the gap between the pieces is NOT claimed
    assert not upper.covers(Polygon([(112, 2), (126, 2), (126, 16), (112, 16)]))


def test_a_sloped_profile_carries_its_gradient_through_the_codec():
    """§2 (2) reads ``slope`` off the published record — a dropped
    gradient would silently make every sloped pad flat again."""
    a = BG.BaseProfile(verdict=BG.SLOPED, slope=(0.0102, -0.0031),
                       residual_rms_m=0.08, feet=430, feet_y=1.5,
                       why="contact set 44 m at 1.07 %")
    b = BG.profile_from_json(BG.profile_to_json(a))
    assert b.verdict == BG.SLOPED
    assert b.slope == pytest.approx((0.0102, -0.0031))
    assert b.residual_rms_m == pytest.approx(0.08)


def test_an_empty_record_is_the_pre_law_profile():
    """§1 (3): a plan with no base read "keeps today's law exactly" —
    FEET, no plane, and it SAYS why rather than reading as a silent
    flat."""
    for empty in (None, {}):
        prof = BG.profile_from_json(empty)
        assert prof.verdict == BG.FEET
        assert prof.planes == () and prof.risers == ()
        assert "predates" in prof.why


# ------------------------------------------------- the carry on the plan

def test_the_plan_carries_the_profile_through_json():
    """§1 (4): the record reaches the planar stage on ``Member``."""
    plan = _plan(_member("m0", _stepped()))
    back = RebakePlan.from_dict(json.loads(plan.to_json()))
    prof = BG.profile_from_json(back.units[0].members[0].base_profile)
    assert prof.verdict == BG.STEPPED
    assert [p.y for p in prof.planes] == [0.0, 3.9]
    assert prof.offsets == (0.0, 3.9)
    assert prof.planes[1].polygon.area == pytest.approx(60 * 60 + 20 * 20)


def test_the_plan_version_is_bumped_and_the_old_one_still_reads():
    """Version 11 is version 10 plus the base profile.  A v10 plan — an
    owner's plan from an earlier build — must still replay, reading as
    the PRE-BASE law (§1 (3)), never raising."""
    assert PLAN_VERSION == 11
    d = json.loads(_plan(_member("m0", _stepped())).to_json())
    assert d["version"] == 11
    assert d["units"][0]["members"][0]["base_profile"]["verdict"] == "stepped"
    # the v10 plan: the key simply is not there
    d["version"] = 10
    del d["units"][0]["members"][0]["base_profile"]
    old = RebakePlan.from_dict(d)
    assert old.units[0].members[0].base_profile == {}
    assert BG.profile_from_json(
        old.units[0].members[0].base_profile).verdict == BG.FEET


def test_the_member_field_defaults_to_empty():
    """Every optional ``Member`` field is defaulted so an inserted field
    cannot shift a positional tail (the ``plate_clearance_m`` /
    ``deck_end_stations`` precedent in ``pack_partition``'s own comment)."""
    m = Member(id="m", resource="r", authored_path="a", live_path="l",
               heading_deg=0.0)
    assert m.base_profile == {}


def test_pack_partition_passes_the_base_profile_by_name():
    """``_build_member`` builds ``Member`` with EVERY optional field named
    — twice a positional tail has silently shifted there.  The base
    profile joins that call, so it is named too."""
    import inspect

    from auto_patch_v2.airport import pack_partition as PP
    src = inspect.getsource(PP._build_member)
    assert "base_profile=base_prof" in src
    assert "cache.base_profile(o.resolved, law)" in src


# ------------------------------------------------------- the report (C21)

def _rpt():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as RPT
    return RPT


#: the two law keys the roll-up needs, at their OWN existing spellings
LAW_KW = dict(pad_terrace_floor_m=1.0, pad_frontage_m=3.0)


def test_the_report_reads_the_published_record_and_derives_nothing():
    """§6's STOP: the report must not be a second reader of the law.  A
    plan whose member carries a STEPPED record reports stepped — and the
    report never opens the OBJ (the fixture's ``authored_path`` does not
    exist, so a re-derivation would raise or read FEET)."""
    rep = _rpt().base_profile_report(_plan(_member("m0", _stepped())), **LAW_KW)
    assert rep["verdicts"] == {"stepped": 1}
    u = rep["units"][0]
    assert u["verdict"] == "stepped"
    assert u["members"][0]["published"] is True
    assert [p["y"] for p in u["members"][0]["planes"]] == [0.0, 3.9]
    assert u["members"][0]["risers"] == [[0, 1, 3.9]]


def test_the_report_says_when_a_plan_predates_the_read():
    """A v10 plan reports FEET and SAYS SO — the owner reading §7 step 3's
    control must not mistake "no read" for "no plane"."""
    rep = _rpt().base_profile_report(_plan(_member("m0", None)), **LAW_KW)
    assert rep["verdicts"] == {"feet": 1}
    m = rep["units"][0]["members"][0]
    assert m["published"] is False and "predates" in m["why"]
    assert any("predates the base read" in ln
               for ln in _rpt().base_profile_lines(rep))


def test_the_roll_up_is_labelled_vertical_only_and_exact_for_one_member():
    """§1 (3): the dry roll-up is the PER-MEMBER UPPER BOUND.  A unit of
    ONE member is exact; a multi-member unit is marked ``~`` because the
    roof test is not re-run on the composed unit (the HECA T3 risk §5 A5
    pre-registers) — the composition belongs to the planar stage."""
    one = _rpt().base_profile_report(_plan(_member("m0", _stepped())), **LAW_KW)
    assert one["composition"] == "vertical_only"
    assert one["units"][0]["exact"] is True
    assert not any(ln.strip().startswith("~") for ln in
                   _rpt().base_profile_lines(one))

    two = _rpt().base_profile_report(
        _plan(_member("m0", _stepped()),
              _member("m1", _stepped(), base_y=3.9,
                      resource="objects/FireStation_1.obj")), **LAW_KW)
    u = two["units"][0]
    assert u["exact"] is False
    assert len(u["members"]) == 2
    assert any("~unit:108" in ln for ln in _rpt().base_profile_lines(two))


def test_the_roll_up_lifts_a_members_planes_by_its_authored_floor():
    """The one offset the plan carries EXACTLY is each member's authored
    floor (§16g (10) (1), the reading ``PlanCluster.floors`` takes).  A
    member standing 3.9 m up contributes its planes 3.9 m up."""
    rep = _rpt().base_profile_report(
        _plan(_member("m0", _stepped()),
              _member("m1", _stepped(), base_y=3.9,
                      resource="objects/FireStation_1.obj")), **LAW_KW)
    ys = [p["y"] for p in rep["units"][0]["planes"]]
    assert 7.8 == pytest.approx(max(ys))      # 3.9 (upper plane) + 3.9 (floor)


def test_the_report_holds_no_copy_of_a_law_number():
    """Every threshold is PASSED IN from its own existing law key — a
    second copy of a law number in a reporting tool is the
    census-wrapper defect in the law file (RULINGS 2026-08-30l)."""
    import inspect
    sig = inspect.signature(_rpt().base_profile_report)
    for k in ("pad_terrace_floor_m", "pad_frontage_m"):
        assert sig.parameters[k].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        _rpt().base_profile_report(_plan(_member("m0", _stepped())))


def test_the_flag_exists_and_is_documented():
    """C21: the flag ships with its INDEX row (RULINGS ``7e90032``: a tool
    absent from the index is treated as absent)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    with open(os.path.join(os.path.dirname(root), "tools", "INDEX.md"),
              encoding="utf-8") as fh:
        idx = fh.read()
    assert "--base-profile" in idx
    src = os.path.join(root, "tools", "obj8_split_report.py")
    with open(src, encoding="utf-8") as fh:
        assert '"--base-profile"' in fh.read()


def test_the_flag_reaches_the_command_line():
    """The library twins above exercise ``base_profile_report`` directly; a
    flag can be written and still never reach ``argparse`` (added to the
    wrong parser, or shadowed).  ``--help`` is the cheapest honest check
    that the CLI actually carries it, and it touches no corpus: argparse
    exits before the tool reads anything."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    out = subprocess.run([sys.executable,
                          os.path.join(root, "tools", "obj8_split_report.py"),
                          "--help"],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[-2000:]
    # argparse REFLOWS help text, so the phrase is matched on whitespace-
    # normalised output — a literal match would break on the wrap column.
    flat = " ".join(out.stdout.lower().split())
    assert "--base-profile" in flat
    assert "re-derives nothing" in flat
