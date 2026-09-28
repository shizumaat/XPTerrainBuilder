"""unit-platform spec §2 — THE SOLID-CONNECTOR DISCRIMINATOR (owner RULINGS
2026-09-28a (2); issues #66 / #10) — lane ``unitplatform``.

ONE verdict (``footprint_connector.solid_connectors``), stamped on the
plan, read by BOTH the design surface's ``plan_clusters`` and the object
stage's ``plan_units_and_connectors`` (§16g (9) one population): a SOLID
connector (S1 walled along its whole length, S3 not a deck, S4 end-ground
step <= ``platform_collar_max_m x bank_slope``) joins its two units; every
other §16g (6) connector is CUT out of both chains.  The HECA precedent: the
elevated rail ``concrete_3`` b1 (1,149 m, a deck on piers, end step 17 m)
chained T2 to T3 in the design cluster only, and one plate over 30 m of
relief lifted T2 to 96.35 over its 68-74 m apron.
"""
from __future__ import annotations

import dataclasses as _dc

from auto_patch_v2.airport import footprint_connector as FC
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport.placement_family import plan_clusters


def _lat(m: float) -> float:
    return 41.0 + m / 111_132.0


class _Part:
    def __init__(self, pid, la0, la1, height, lo0=-3.0, lo1=-2.9990):
        self.pid = pid
        self.box = (_lat(la0), lo0, _lat(la1), lo1)
        self.line = False
        self.scatter = False
        self.lat = 0.5 * (self.box[0] + self.box[2])
        self.lon = 0.5 * (self.box[1] + self.box[3])
        self.base_y = 0.0
        self.feet = ((self.lat, self.lon, 0.0),)
        self.comp = 0
        self.area_m2 = 1.0
        self.height_m = float(height)
        self.rings = ()


class _Member:
    def __init__(self, resource, parts, deck_kind=""):
        self.id = resource
        self.resource = resource
        self.parts = tuple(parts)
        self.deck_datum_z = None
        self.deck_ring = None
        self.deck_shade_ring = None
        self.deck_kind = deck_kind
        self.elevated_deck = False
        self.heading_deg = 0.0


class _Unit:
    def __init__(self, members):
        self.id = "unit:0"
        self.anchor = (41.0, -3.0)
        self.members = tuple(members)


@_dc.dataclass
class _Plan:
    units: tuple
    contacts: tuple = ()
    connectors: "tuple | None" = None


def _plan(kind: str) -> _Plan:
    """Two walled buildings A (0-100 m) and B (400-500 m) joined by a
    300 m connector: ``strip`` one walled component, ``piers`` a plate
    with a 5 m pier every 60 m (a deck on piers), ``deck`` the walled
    strip the object stage calls a deck by its own VERDICT (``signature``),
    ``candidate`` the strip the signature pass merely looked at."""
    a = _Member("objects/a.obj", [_Part(1, 0, 100, 12.0)])
    b = _Member("objects/b.obj", [_Part(2, 400, 500, 12.0)])
    if kind == "piers":
        parts = [_Part(10, 100, 400, 0.0, -2.99960, -2.99940)]
        parts += [_Part(11 + i, 100 + 60 * i, 102 + 60 * i, 5.0,
                        -2.99960, -2.99940) for i in range(6)]
        contacts = tuple((10, 11 + i) for i in range(6))
    else:
        parts = [_Part(10, 100, 400, 4.0, -2.99960, -2.99940)]
        contacts = ()
    c = _Member("objects/link.obj", parts,
                deck_kind={"deck": "signature",
                           "candidate": "candidate"}.get(kind, ""))
    if kind == "candidate":
        c.elevated_deck = True
    return _Plan((_Unit([a, b, c]),), contacts)


def _ground(step: float):
    """The DEM: flat at 100 m south of 250 m, ``100 + step`` north of it."""
    return lambda la, lo: 100.0 + (step if la > _lat(250) else 0.0)


def _verdict(kind: str, step: float):
    plan = _plan(kind)
    got = FC.solid_connectors(plan, _ground(step), touch_m=0.5, span_m=200.0,
                              visual_m=0.5, chain_min_height_m=2.5,
                              gap_max_m=20.0, step_max_m=15.0 * 0.33)
    return plan, got


def test_s1_s3_s4_each_decide():
    """S1 (walled whole length), S3 (not a deck), S4 (step <= 4.95 m)."""
    _p, v = _verdict("strip", 2.5)          # the HECA metal strip, 2.50 m
    assert [x.solid for x in v] == [True], [x.why() for x in v]
    _p, v = _verdict("piers", 2.5)          # a deck on piers: S1 fails
    assert [x.solid for x in v] == [False] and not v[0].walled
    assert v[0].walled_gap_m > 20.0
    _p, v = _verdict("strip", 29.0)         # the rail's end step: S4 fails
    assert [x.solid for x in v] == [False] and v[0].walled
    # S3: a deck by the object stage's verdict never joins — the topology
    # already leaves it out of the chain (member_is_deck), and asked
    # directly the verdict refuses it
    _p, v = _verdict("deck", 2.5)
    assert not any(x.solid for x in v)
    p = _plan("deck")
    link = p.units[0].members[2]
    cn = FC.PlanConnector("c", (0, 2, 0), frozenset({10}), link.resource,
                          300.0, "unit:0", "a", "b")
    _st, vd = FC.connector_verdict(cn, link.parts, link,
        _ground(2.5), chain_min_height_m=2.5, gap_max_m=20.0,
        step_max_m=4.95)
    assert vd.deck and not vd.solid


def test_s3_is_member_is_deck_only():
    """Spec-author ruling on #66 (2): ``deck_kind == 'candidate'`` (and an
    ``elevated_deck`` reading) is NOT a deck verdict — SPJC
    ``LIMANUEVA_xp11_010`` (13cn) and HECA ``T3_7`` stay unit members."""
    _p, v = _verdict("candidate", 2.5)
    assert [x.solid for x in v] == [True] and not v[0].deck


def test_a_connector_whose_ends_do_not_step_is_a_member():
    """§16g (6): no end step (< visual_m) -> no verdict at all."""
    _p, v = _verdict("piers", 0.1)
    assert v == ()


def _both_readers(plan, verdicts):
    plan.connectors = verdicts
    cut = FC.cut_pids(FC.verdicts_of(plan))
    cl = plan_clusters(plan, 0.5, chain_min_height_m=2.5, cut=cut)
    units, _c = FU.plan_units_and_connectors(plan, 0.5, 200.0, None, 2.5,
                                             cut=cut)
    together_cl = any({"objects/a.obj", "objects/b.obj"} <= set(c.members)
                      for c in cl)
    together_u = any({"objects/a.obj", "objects/b.obj"} <= set(u.members)
                     for u in units)
    return together_cl, together_u


def test_both_readers_cut_a_cut_connector_and_join_a_solid_one():
    """§16g (9) — pad_cluster_mismatch's twin at the derivation: the
    design cluster and the object-stage unit agree on every verdict."""
    plan, v = _verdict("piers", 29.0)
    assert _both_readers(plan, v) == (False, False)
    plan, v = _verdict("strip", 2.5)
    assert _both_readers(plan, v) == (True, True)


def test_unstamped_plan_keeps_todays_chain():
    """A plan with no verdict chains every walled body as before."""
    plan = _plan("piers")
    assert FC.verdicts_of(plan) is None
    cl = plan_clusters(plan, 0.5, chain_min_height_m=2.5)
    assert any({"objects/a.obj", "objects/b.obj"} <= set(c.members)
               for c in cl)


def test_the_verdict_round_trips_the_rebake_plan_json():
    _p, v = _verdict("piers", 29.0)
    d = [x.to_dict() for x in v]
    back = tuple(FC.ConnectorVerdict.from_dict(x) for x in d)
    assert back == v


def test_the_object_stage_seats_a_stamped_cut_connector_at_its_low_end():
    """§2 at the object stage: the stamped CUT connector is out of every
    unit's chain, yet never orphaned to §16c — its row IS its low end's
    seat and carries the verdict ``cut`` that ``_bind_plan_wide`` takes
    without re-asking the staged step."""
    plan, v = _verdict("piers", 29.0)
    plan.connectors = v
    counts: dict = {}
    pw, _s = FU.plan_wide_seats(plan, _ground(29.0), (), 0.5, 0.0, counts,
                                200.0, 2.5)
    assert counts["connector_verdict_stamped"] == 1
    assert counts["connectors_cut"] == 1
    # A and B are no longer one unit
    assert pw.get(1, ("a",))[0] != pw.get(2, ("b",))[0]
    row = pw[10]
    assert len(row) == 7 and row[6] == "cut"
    assert row[4][0] and row[4][1]                  # both ends named
    assert abs(row[5][1] - 100.0) < 1e-6            # the LOW end's ground


def test_two_cut_connectors_of_one_unit_are_two_seats():
    """The end labels name ONE removal's components, so two stamped CUT
    connectors of one unit both read ``<unit>/c0``; each must keep its OWN
    low end's seat (HECA: seven pooled, T2's Titles_not_metal +23 m)."""
    plan, v = _verdict("piers", 29.0)
    v2 = _dc.replace(v[0], pids=(99,))
    plan.connectors = (v[0], v2)
    pw, _s = FU.plan_wide_seats(plan, _ground(29.0), (), 0.5, 0.0, {},
                                200.0, 2.5)
    assert pw[10][5][0] != v2.end_a and pw[10][5][0].startswith(v[0].end_a)
    assert pw[10][0] == pw[10][5][0]
