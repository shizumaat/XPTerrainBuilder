"""THE ABUTMENT GROUP twins (owner RULINGS 2026-09-10ay; spec
``othh-seat-artefacts-spec.md`` §17, lane ``v2bridgegroup``).

In a SHARED-DATUM pack — one anchor plane for every placement, so the
authored relation between them is exact — bodies of DIFFERENT placements
that ABUT in the AUTHORED frame (plan footprints overlapping, authored z
within ``[rebake] plate_gap_max_m``) form ONE GROUP with ONE delta: the
SENIOR body's.  The T4 departures viaduct stays at the terminal kerb it
was authored to meet and its ramp ends BURY where the ground is higher.

Three sites, all hermetic and v2-pure:

1. a terminal (a ground core carrying an overhanging upper slab) and a
   SEPARATE deck placement authored 2 m under the slab's edge, its own
   piers standing on ground 5 m HIGHER — grouped, the deck takes the
   terminal's ground and its pier feet bury 5 m (the ruling's "allow
   either end to be submerged");
2. the same deck 10 m clear of the building in plan — no abutment, its
   own body, its own feet;
3. a LINE OBJECT (a fence) spanning two buildings that touch nothing
   else — bodies that abut only through a line object never group
   (RULINGS 2026-09-10bb rule 2);
4. THE GATE (owner RULINGS 2026-09-11a): the same body in the same
   place, WALLED to the ground instead of carried on piers, abutting
   the same terminal — a BUILDING, which never groups with a building.
   Round 1's ungated rule pulled 7 of LEMD's OldTerminal buildings one
   hop toward a larger neighbour.

The fixture's ground is 5 m HIGHER under the viaduct, not lower: it is
the direction that makes the BURIAL observable, and it is the direction
of the owner's own read ("being separated and RAISED above the
terminal").
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as _plan
from auto_patch_v2.emit import rebake as R
from auto_patch_v2.emit import clusters as C
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects

from test_m6a_rebake import _airport  # noqa: E402
from test_m6b_deck import _boxes_obj  # noqa: E402

ORIGIN = (60.5, -135.5)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    root = tmp_path_factory.mktemp("grouppack")
    (root / "Earth nav data").mkdir()
    (root / "Earth nav data" / "apt.dat").write_text("I\n1200\n\n1 700 0 0 ZZZZ Synthetic\n")
    d = root / "objects"
    # THE TERMINAL: a ground core (z -10..+10, y 0..14) carrying an upper
    # slab that OVERHANGS it to z -20 (y 14..20).  The two touch, so the
    # slab is one body with the core and the body has feet at y = 0.
    _boxes_obj(d / "terminal.obj", [(0.0, 0.0, 40.0, 10.0, 0.0, 14.0),
                                    (0.0, 0.0, 40.0, 20.0, 14.0, 20.0)])
    # THE VIADUCT, a SEPARATE placement: a deck slab under the slab's
    # overhang (z -20..-12, y 10..11.8 — 2.2 m clear of the slab's
    # bottom, no contact) on two piers reaching the ground.
    _boxes_obj(d / "viaduct.obj", [(0.0, -16.0, 60.0, 4.0, 10.0, 11.8),
                                   (-25.0, -16.0, 1.0, 1.0, 0.0, 10.0),
                                   (25.0, -16.0, 1.0, 1.0, 0.0, 10.0)])
    # THE ANNEX: the same body in the same place, WALLED to the ground —
    # a building, not a deck.  It abuts the terminal exactly as the
    # viaduct does and must NOT group with it (owner RULINGS 2026-09-11a:
    # buildings never group with buildings, each seats on its own feet).
    _boxes_obj(d / "annex.obj", [(0.0, -16.0, 60.0, 4.0, 0.0, 11.8)])
    # TWO BUILDINGS 10 m apart in plan, and a FENCE spanning both: a
    # ribbon 0.2 m wide, 60 m long, 2 m high, overlapping each building's
    # plan box and standing within the gap of each.
    _boxes_obj(d / "west.obj", [(-20.0, 0.0, 8.0, 8.0, 0.0, 6.0)])
    _boxes_obj(d / "east.obj", [(20.0, 0.0, 8.0, 8.0, 0.0, 6.0)])
    _boxes_obj(d / "fence.obj", [(0.0, 0.0, 30.0, 0.1, 0.0, 2.0)])
    return root


def _planned(pack, law, placements):
    a = _airport(pack, law, placements)
    objs, _ = read_objects(a, law)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    return a, _plan(a, objs, cache, law, None)


def _site_sampler():
    """The kerb site: 710 under the terminal, 715 north of the core (the
    viaduct's piers), and 700 in a 6 m window at the ANCHOR — the anchor
    reading is the member's ``y = 0`` plane, so a flat sampler would make
    every delta 0 and every body stay below ``min_delta_m``."""
    m_lat, m_lon = C.metres_per_degree(ORIGIN[0])

    def f(lat, lon):
        x = (lon - ORIGIN[1]) * m_lon
        y = (lat - ORIGIN[0]) * m_lat
        if abs(x) < 3.0 and abs(y) < 3.0:
            return (700.0, False)                # the anchor window
        return (715.0 if y >= 11.0 else 710.0, False)
    return f


def _fence_sampler():
    """700 at the anchor, 710 west of it, 715 east of it."""
    _m_lat, m_lon = C.metres_per_degree(ORIGIN[0])

    def f(lat, lon):
        x = (lon - ORIGIN[1]) * m_lon
        if abs(x) < 3.0:
            return (700.0, False)
        return (715.0 if x >= 5.0 else 710.0, False)
    return f


def _body(res, resource):
    """``(cluster ids, deltas)`` a member's parts came out with."""
    for u in res.units:
        for m in u.members:
            if m.resource.endswith(resource):
                return ([k for _c, k, _d in m.part_deltas],
                        [d for _c, _k, d in m.part_deltas])
    raise AssertionError(f"{resource} not in the result")


# ── 1. the viaduct authored to meet the terminal kerb ────────────────────

@pytest.fixture(scope="module")
def kerb(pack, law):
    # ONE ANCHOR for both placements: the shared-datum pack (10ad/10ax).
    return _planned(pack, law, [("terminal", (0.0, 0.0), 0.0, 0.0),
                                ("viaduct", (0.0, 0.0), 0.0, 0.0)])


def test_the_plan_records_the_authored_abutment(kerb):
    _a, pl = kerb
    assert pl.counts["abutments"] >= 1
    by = {m.resource: m for u in pl.units for m in u.members}
    term = {p.pid for p in by["objects/terminal.obj"].parts}
    via = {p.pid for p in by["objects/viaduct.obj"].parts}
    cross = [(a, b) for a, b in pl.abutments
             if (a in term and b in via) or (a in via and b in term)]
    assert cross, "the deck and the terminal slab abut in the authored frame"
    # and they carry NO contact edge: the abutment is exactly what the
    # ε-contact graph cannot see (2.2 m of authored clearance)
    assert not [(a, b) for a, b in pl.contacts
                if (a in term and b in via) or (a in via and b in term)]


def test_the_viaduct_takes_the_terminals_ground_and_its_ends_bury(kerb, law):
    _a, pl = kerb
    # the ground steps 5 m UP north of the terminal core, which is where
    # the viaduct's piers stand (the OBJ8 -z axis is world NORTH)
    sampler = _site_sampler()
    res = R.seat(pl, sampler, law)
    tk, td = _body(res, "terminal.obj")
    vk, vd = _body(res, "viaduct.obj")
    assert len({k for k in tk}) == 1 and len({k for k in vk}) == 1
    assert tk[0] != vk[0], "two placements, two BODIES — the group is not a merge"
    # ONE delta: the viaduct takes the terminal's, to the millimetre
    # (the anchor DEM is flat 700, so the terminal's own is +10)
    assert td[0] == pytest.approx(10.0, abs=0.05)
    assert vd[0] == pytest.approx(td[0], abs=1e-9)
    # ...and it is the SENIOR's ground, not the viaduct's own feet's
    seats = {k.id: k for k in res.clusters}
    senior = seats[tk[0]]
    junior = seats[vk[0]]
    assert junior.group == senior.id == senior.group
    assert junior.ground_m == pytest.approx(senior.ground_m, abs=1e-9)
    # the burial: the viaduct's own feet wanted 715, it sits at 710
    assert junior.foot_residual_max_m == pytest.approx(5.0, abs=0.05)
    # a junior raises NO pad request — the burial is lawful (10ay)
    assert not [p for p in res.pad_requests if p.cluster == junior.cluster]


def test_the_group_is_off_when_the_law_key_is_zero(pack, law):
    zero = _dc.replace(law, tables=_dc.replace(law.tables, structures=_dc.replace(
        law.tables.structures, rebake=_dc.replace(law.tables.structures.rebake,
                                                  abutment_extent_min_m=0.0))))
    _a, pl = _planned(pack, zero, [("terminal", (0.0, 0.0), 0.0, 0.0),
                                   ("viaduct", (0.0, 0.0), 0.0, 0.0)])
    assert pl.counts["abutments"] == 0
    res = R.seat(pl, _site_sampler(), zero)
    _tk, td = _body(res, "terminal.obj")
    _vk, vd = _body(res, "viaduct.obj")
    assert td[0] == pytest.approx(10.0, abs=0.05)
    assert vd[0] - td[0] == pytest.approx(5.0, abs=0.05)        # the pre-10ay tear


# ── 2. a deck 10 m clear of any building ─────────────────────────────────

def test_a_deck_clear_of_every_building_is_its_own_body(pack, law):
    # the viaduct 40 m NORTH of its kerb position: its deck (north
    # 52..60 m) clears the terminal's slab (north 20 m) by 32 m and
    # overlaps nothing in plan
    _a, pl = _planned(pack, law, [("terminal", (0.0, 0.0), 0.0, 0.0),
                                  ("viaduct", (0.0, 40.0), 0.0, 0.0)])
    by = {m.resource: m for u in pl.units for m in u.members}
    term = {p.pid for p in by["objects/terminal.obj"].parts}
    via = {p.pid for p in by["objects/viaduct.obj"].parts}
    assert not [(a, b) for a, b in pl.abutments
                if (a in term and b in via) or (a in via and b in term)]
    res = R.seat(pl, _site_sampler(), law)
    tk, _td = _body(res, "terminal.obj")
    vk, _vd = _body(res, "viaduct.obj")
    seats = {k.id: k for k in res.clusters}
    assert seats[vk[0]].group is None and seats[tk[0]].group is None
    # its OWN feet (715), not the terminal's ground (710)
    assert seats[vk[0]].ground_m == pytest.approx(715.0, abs=0.05)
    assert seats[tk[0]].ground_m == pytest.approx(710.0, abs=0.05)


# ── 3. a fence between two buildings ─────────────────────────────────────

def test_two_buildings_joined_only_by_a_fence_never_group(pack, law):
    _a, pl = _planned(pack, law, [("west", (0.0, 0.0), 0.0, 0.0),
                                  ("east", (0.0, 0.0), 0.0, 0.0),
                                  ("fence", (0.0, 0.0), 0.0, 0.0)])
    by = {m.resource: m for u in pl.units for m in u.members}
    assert all(p.line for p in by["objects/fence.obj"].parts), \
        "the fixture's fence must classify as a LINE OBJECT"
    ids = {r: {p.pid for p in by[f"objects/{r}.obj"].parts} for r in ("west", "east", "fence")}
    for a, b in pl.abutments:
        assert not (a in ids["fence"] or b in ids["fence"]), \
            "a line object never proposes an abutment (10bb rule 2)"
        assert not ((a in ids["west"] and b in ids["east"])
                    or (a in ids["east"] and b in ids["west"]))
    res = R.seat(pl, _fence_sampler(), law)
    wk, wd = _body(res, "west.obj")
    ek, ed = _body(res, "east.obj")
    assert wk[0] != ek[0]
    seats = {k.id: k for k in res.clusters}
    assert seats[wk[0]].group is None and seats[ek[0]].group is None
    assert ed[0] - wd[0] == pytest.approx(5.0, abs=0.05)        # each on its own ground


# ── 4. THE GATE: only an ELEVATED DECK may be a cross-placement junior ──

def test_the_plan_reads_the_deck_on_piers_and_the_walled_body(kerb):
    """owner RULINGS 2026-09-11a: the plate-on-piers reading, on the plan."""
    _a, pl = kerb
    by = {m.resource: m for u in pl.units for m in u.members}
    assert by["objects/viaduct.obj"].elevated_deck, \
        "a plate 10 m up on two 1 m piers IS an elevated deck"
    assert not by["objects/terminal.obj"].elevated_deck, \
        "a slab carried on a walled core is NOT"
    assert pl.counts["elevated_decks"] == 1


def test_a_building_abutting_a_larger_building_never_groups(pack, law):
    """The annex stands exactly where the viaduct's deck does and abuts
    the same terminal — but it is WALLED to the ground, so it seats on
    its own feet (11a; 10i: each body on its own feet)."""
    _a, pl = _planned(pack, law, [("terminal", (0.0, 0.0), 0.0, 0.0),
                                  ("annex", (0.0, 0.0), 0.0, 0.0)])
    by = {m.resource: m for u in pl.units for m in u.members}
    assert not by["objects/annex.obj"].elevated_deck
    term = {p.pid for p in by["objects/terminal.obj"].parts}
    ann = {p.pid for p in by["objects/annex.obj"].parts}
    assert [(a, b) for a, b in pl.abutments
            if (a in term and b in ann) or (a in ann and b in term)], \
        "the fixture's annex must ABUT the terminal (the gate, not the geometry)"
    res = R.seat(pl, _site_sampler(), law)
    tk, td = _body(res, "terminal.obj")
    ak, ad = _body(res, "annex.obj")
    seats = {k.id: k for k in res.clusters}
    assert seats[ak[0]].group is None and seats[tk[0]].group is None
    # each on its OWN ground: the terminal 710, the annex 715
    assert seats[tk[0]].ground_m == pytest.approx(710.0, abs=0.05)
    assert seats[ak[0]].ground_m == pytest.approx(715.0, abs=0.05)
    assert ad[0] - td[0] == pytest.approx(5.0, abs=0.05)
