"""Issue #610 (lane roofs610, owner sim read of 1.0.391): roofs and a canopy
written at another building's zero.  Three general rules, each read off a
KCLT / KASE site and each red on main (the fuel-canopy anchor rule was
dropped by the owner, RULINGS 2026-10-14j):

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


# ── cluster_zero_allowed: what the piece stands over decides ────────────

def _cand(box):
    return types.SimpleNamespace(box=box)


def test_a_roof_over_another_building_does_not_take_the_cluster_zero():
    near = (40.0, -3.0, 40.0003, -2.9996)          # cluster member, 30 m off
    st = types.SimpleNamespace(footless=True)
    piece = (40.0005, -3.0, 40.0008, -2.9996)      # over building 7
    cands = [_cand(near)] + [_cand(piece)] * 7
    cnt: dict = {}
    # main's reading: within the reach, the cluster member carries it
    assert FU.cluster_zero_allowed([0], st, piece, cands, 100.0, cnt) == [0]
    # it stands over candidate 7, which is not in its cluster: search
    assert FU.cluster_zero_allowed([0], st, piece, cands, 100.0, cnt,
                                   over=lambda: {7}) == []
    assert cnt["cluster_zero_refused_stands_over_other"] == 1
    # it stands over its own cluster member: kept, that one first
    assert FU.cluster_zero_allowed([3, 0], st, piece, cands, 100.0, cnt,
                                   over=lambda: {0}) == [0, 3]
    # over nothing footed (a deck abutting its building): unchanged
    assert FU.cluster_zero_allowed([0], st, piece, cands, 100.0, cnt,
                                   over=lambda: set()) == [0]


# ── _atom_targets: an orphan atom carries no parts ──────────────────────

def test_an_orphan_only_atom_carries_no_parts(monkeypatch):
    part = types.SimpleNamespace(pid=11, comp=0, box=(40.0, -3.0, 40.0001, -2.9999),
                                 base_y=4.0, feet=())

    class _Cut:
        def part_tris(self, parts):
            return ((0, 1, 2),)

        def _comp_blocks(self, tris):
            return [[0], [1]]

        def comp_of(self, tris):
            return [0, 5]                 # component 5: no plan part

        def plan_box_of_tris(self, tris):
            return ((40.0, -3.0, 40.0001, -2.9999) if tris[0] == (0, 1, 2)
                    else (40.002, -3.0, 40.0021, -2.9999))

        def part_tops(self, raw):
            return [[4.0]]

    monkeypatch.setattr(PB, "_geom_ground", lambda *a: ((), (), None))
    raw0 = ([part], "building", _ar.Anchor("building", 40.0, -3.0, 0.0, "", 200.0),
            (), True, ((0, 1, 2), (3, 4, 5)), (), None)
    st = types.SimpleNamespace(cutter=_Cut(), raw=[raw0], boxes=[None],
                               part_boxes=[[(40.0, -3.0, 40.0021, -2.9999)]],
                               geom_boxes=None, part_tops=None, surface=None)
    out = PB._atom_targets(st, [0], reach_m=0.0)
    assert out == [[1], [2]], out
    assert [p.pid for p in st.raw[1][0]] == [11]
    assert st.raw[2][0] == [], "the orphan atom inherited the group's parts"


# ── the roof witness: part boxes, and never across two footprint units ──

_N = (40.0004, -3.0, 40.0009, -2.9995)             # north bay
_S = (40.0, -3.0, 40.0004, -2.9995)                # south bay, touching


def _footed(member, pid, box, zero, feet, unit="", parts=()):
    return ATOM.RigidNode(member, frozenset([pid]), box, footprint_m2=100.0,
                          footed=True, bindable=True, zero=zero, feet=feet,
                          part_boxes=tuple(parts) or (box,), unit=unit)


def _roof(pid, box, parts=()):
    return ATOM.RigidNode(9, frozenset([pid]), box, footprint_m2=50.0,
                          footed=False, bindable=True, zero=None,
                          part_boxes=tuple(parts) or (box,))


def test_the_roof_witness_never_binds_across_two_footprint_units():
    north = _footed(0, 1, _N, 2355.71, 43, unit="fu:a")
    south = _footed(1, 2, _S, 2356.49, 6, unit="fu:b")
    roof = _roof(3, (40.0, -3.0, 40.0009, -2.9995))
    cnt: dict = {}
    senior, _c = ATOM.unit_rigid([north, south, roof], [(1, 2), (2, 3)],
                                 bind_ground_m=0.5, counts=cnt, roof_bind_m=1.0)
    assert senior[1] == -1, senior
    assert cnt["roof_witness_other_unit"] == 1
    # one unit (or a leaf in none): the #625 witness binds as before
    south1 = _footed(1, 2, _S, 2356.49, 6, unit="fu:a")
    senior1, _c1 = ATOM.unit_rigid([north, south1, roof], [(1, 2), (2, 3)],
                                   bind_ground_m=0.5, roof_bind_m=1.0)
    assert senior1[1] == 0, senior1
    leaf = _footed(1, 2, _S, 2356.49, 6)
    senior2, _c2 = ATOM.unit_rigid([north, leaf, roof], [(1, 2), (2, 3)],
                                   bind_ground_m=0.5, roof_bind_m=1.0)
    assert senior2[1] == 0, senior2


def test_the_roof_witness_reads_part_boxes_not_the_hull():
    """A roof whose hull spans both bays but whose plates cover only the
    north one is not a roof over the south bay."""
    north = _footed(0, 1, _N, 2355.71, 43)
    south = _footed(1, 2, _S, 2356.49, 6)
    roof = _roof(3, (40.0, -3.0, 40.0009, -2.9995),
                 parts=((40.0005, -3.0, 40.0009, -2.9995),
                        (40.0, -3.0, 40.00001, -2.99999)))   # a sliver, no overlap
    roof = ATOM.RigidNode(9, frozenset([3]), (40.0, -3.0, 40.0009, -2.9995),
                          footprint_m2=50.0, footed=False, bindable=True,
                          zero=None,
                          part_boxes=((40.0005, -3.0, 40.0009, -2.9995),))
    senior, _c = ATOM.unit_rigid([north, south, roof], [(1, 2), (2, 3)],
                                 bind_ground_m=0.5, roof_bind_m=1.0)
    assert senior[1] == -1, senior
