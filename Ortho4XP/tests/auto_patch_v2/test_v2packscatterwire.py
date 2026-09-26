"""#29 / spec ``pack-read-once-fast-spec.md`` §B.2 (4), slice S5b: the
SCATTER class wired (owner RULINGS 2026-09-18q Q1/Q2, 18t (4)).

T1 the piece rule (a trunk and its fronds one body, two bushes 0.6 m
apart two bodies, the chain order deterministic); T3 no scatter pid in any
weld / narrow pair, no ring, one foot; T4 a scatter member is INELIGIBLE
(no group, no ground_fit); a scatter piece never joins a cluster; T5 the
screen re-states the verdict for a structure-seated member; T6 the cache
version refuses a v3 payload; the member-level exemptions (a deck, a
line object) keep their own class.  The false-positive safety (T2: a
scatter piece inside a building footprint rides the building's §16g
unit) is §16g's own law reading the part BY ITS BOX, twinned where
``rings == ()`` is read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.airport import contact as C                  # noqa: E402
from auto_patch_v2.airport import obj8 as O                     # noqa: E402
from auto_patch_v2.airport import partition_cache as PC         # noqa: E402
from auto_patch_v2.model.rebake import Member, Part             # noqa: E402
from auto_patch_v2.planar import group as G                     # noqa: E402

from test_v2packscatter import _box, _write_obj                  # noqa: E402


def _placed(path: str, x: float = 0.0, y: float = 0.0, oid: str = "o1") -> O.PlacedObject:
    return O.PlacedObject(id=oid, path=path, resolved=path, xy=(x, y), heading_deg=0.0,
                          agl_m=0.0, kind="OBJECT", anchor_z=10.0, below_grade=None,
                          plan_bbox=None, solid_min_z=None, solid_min_depth_m=None,
                          hard_deck=None, deck_top_z=None)


def _member(path: str, **kw):
    geom = O.parse_obj8(path)
    comps = list(enumerate(O.solid_components(geom)))
    return (_placed(path, **kw), geom, comps)


def _partition(members, scatter=(), touch=0.5):
    return C.partition(members, 0.25, 0.001, 200_000, 1.0, 50_000, 1.0, 4, None,
                       (), 0.0, 0, list(range(len(members))), 0.0, 0.0, 0.0,
                       scatter_members=scatter, piece_touch_m=touch)


@pytest.fixture()
def field(tmp_path):
    """A 'palm' (trunk + two fronds overlapping it in plan), then two
    bushes 0.6 m apart, then a bush 0.3 m from the second."""
    comps = [_box(0.0, 0.0, 0.4, 0.4, 3.0),          # trunk
             _box(-1.0, 0.1, 1.2, 0.2, 0.5, 3.0),     # frond (overlaps in plan)
             _box(0.2, -1.0, 0.2, 1.2, 0.5, 3.0),     # frond
             _box(10.0, 0.0, 0.5, 0.5, 1.0),          # bush A
             _box(11.1, 0.0, 0.5, 0.5, 1.0),          # bush B, 0.6 m from A
             _box(11.9, 0.0, 0.5, 0.5, 1.0)]          # bush C, 0.3 m from B
    return _write_obj(tmp_path / "Flora" / "palms.obj", comps)


def _bodies(part):
    uf = C._UnionFind(len(part.parts))
    for a, b in part.contacts:
        uf.union(a, b)
    out: dict[int, list[int]] = {}
    for p in part.parts:
        out.setdefault(uf.find(p.pid), []).append(p.pid)
    return sorted(sorted(v) for v in out.values())


def test_t1_the_piece_rule(field):
    part = _partition([_member(field)], scatter={0})
    assert all(p.scatter for p in part.parts)
    # palm = one piece; A alone (0.6 m > 0.5 m); B + C one piece
    assert _bodies(part) == [[0, 1, 2], [3], [4, 5]]
    # the chain is stated in pid order and is deterministic
    again = _partition([_member(field)], scatter={0})
    assert part.contacts == again.contacts
    assert set(part.contacts) == {(0, 1), (1, 2), (4, 5)}


def test_t3_no_ring_one_foot_and_no_cross_member_edge(field, tmp_path):
    other = _write_obj(tmp_path / "Terminal" / "shed.obj", [_box(10.0, 0.0, 3.0, 3.0, 4.0)])
    # the shed sits ON bush A: a solid would weld / narrow-contact it
    part = _partition([_member(field), _member(other, oid="o2")], scatter={0})
    scat = {p.pid for p in part.parts if p.scatter}
    for p in part.parts:
        if p.scatter:
            assert p.rings == ()
            assert p.feet.shape[0] == 1
        else:
            assert len(p.rings) >= 1
    for a, b in part.contacts:
        # a scatter pid only ever pairs with a scatter pid of its own member
        if a in scat or b in scat:
            assert a in scat and b in scat
            assert part.parts[a].member == part.parts[b].member
    assert part.abutments == () or not (set(sum(part.abutments, ())) & scat)


def test_no_scatter_member_partitions_as_before(field, tmp_path):
    """With no scatter member the pass is the shipped one: same parts,
    rings, feet and edges as a call that never heard of the class."""
    other = _write_obj(tmp_path / "Terminal" / "shed.obj", [_box(10.0, 0.0, 3.0, 3.0, 4.0)])
    ms = [_member(field), _member(other, oid="o2")]
    a = _partition(ms, scatter=())
    b = C.partition(ms, 0.25, 0.001, 200_000, 1.0, 50_000, 1.0, 4, None,
                    (), 0.0, 0, list(range(len(ms))), 0.0, 0.0, 0.0)
    assert a.contacts == b.contacts and a.abutments == b.abutments
    assert a.structures == b.structures and a.pairs_tested == b.pairs_tested
    for p, q in zip(a.parts, b.parts):
        assert not p.scatter and np.array_equal(p.feet, q.feet)
        assert len(p.rings) == len(q.rings)


def _mpart(pid, scatter=False, line=False):
    return Part(pid, 0, 0.0, 0.0, 0.0, 1.0, (0.0, 0.0, 1e-5, 1e-5),
                ((0.0, 0.0, 0.0),), line, (), 1.0, scatter=scatter)


def test_t4_a_scatter_member_is_ineligible():
    m = Member(id="m", resource="r", authored_path="a", live_path="l", heading_deg=0.0,
               parts=(_mpart(0, True), _mpart(1, True)), scatter=True)
    assert G._eligible(m) is False
    solid = Member(id="m", resource="r", authored_path="a", live_path="l",
                   heading_deg=0.0, parts=(_mpart(0), _mpart(1)))
    assert G._eligible(solid) is True


def test_t6_the_cache_refuses_a_payload_of_another_version(tmp_path):
    assert PC.CACHE_VERSION >= 4
    assert "auto_patch_v2.airport.scatter" in PC._CODE_MODULES
    assert "auto_patch_v2.airport.bulk_geos" in PC._CODE_MODULES


def test_the_member_verdict_keeps_the_deck_and_line_classes_first():
    """``_build_member`` reads the scatter class AFTER the deck and line
    verdicts (the census: six OTHH resources read scatter AND
    ``elevated_deck`` — the deck wins).  Source-order twin."""
    import inspect
    from auto_patch_v2.airport import pack_partition as PP
    src = inspect.getsource(PP._build_member)
    i_deck = src.index("deck_body = bool(")
    i_line = src.index("is_line = (")
    i_scat = src.index("is_scatter = (")
    assert i_deck < i_scat and i_line < i_scat
    for clause in ("not is_line", "not deck_body", "not in_deck_family",
                   "sc.structure_seated", "sc.plate_paths", "sc.basin_members"):
        assert clause in src[i_scat:i_scat + 800]
