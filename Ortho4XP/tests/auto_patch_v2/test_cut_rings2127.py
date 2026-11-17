"""#2127 R4 Part A: a cut whose rim is several open runs is read as ONE ring,
its OUTLINE (``emit/graded.cut_rings`` publishes it,
``airport/placement_read.pads_rims_from_graded_doc`` reads it), never as
each run closed by a chord across the cut.

Synthetic planar maps only: a channel (two floor end lines and an exit
ramp's top line open its rim into three runs over three void faces of one
ref), a U (one run), a closed basin (one closed run)."""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from auto_patch_v2.airport import anchor_rule as _ar  # noqa: E402
from auto_patch_v2.airport import placement_read as _pr  # noqa: E402
from auto_patch_v2.emit import graded as _g  # noqa: E402

REF = "channel_wall:0#1"


@_dc.dataclass
class _F:
    id: int
    role: str
    ref: str
    ring: tuple
    holes: tuple = ()


@_dc.dataclass
class _E:
    id: int
    a: int
    b: int
    left_face: int | None
    right_face: int | None


@_dc.dataclass
class _V:
    id: int
    incident_faces: tuple


class _Map:
    """A planar map from CCW vertex rings: ``faces`` {fid: (role, ref, [vids])}."""

    def __init__(self, faces):
        self.faces, inc, by_pair = {}, {}, {}
        for fid, (role, ref, ring) in faces.items():
            cyc = []
            for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
                key = (min(a, b), max(a, b))
                if key not in by_pair:
                    by_pair[key] = _E(len(by_pair), key[0], key[1], None, None)
                e = by_pair[key]
                if (a, b) == (e.a, e.b):
                    e.left_face = fid
                else:
                    e.right_face = fid
                cyc.append(e.id)
                inc.setdefault(a, set()).add(fid)
            self.faces[fid] = _F(fid, role, ref, tuple(cyc))
        self.edges = {e.id: e for e in by_pair.values()}
        self.vertices = {v: _V(v, tuple(sorted(fs))) for v, fs in inc.items()}

    def ring_vertices(self, cycle):
        e0, e1 = self.edges[cycle[0]], self.edges[cycle[1]]
        cur = e0.a if e0.b in (e1.a, e1.b) else e0.b
        out = [cur]
        for eid in cycle:
            e = self.edges[eid]
            cur = e.b if cur == e.a else e.a
            out.append(cur)
        return tuple(out[:-1])


# plan positions (x, y) of the channel: floor y -1..1, walls 1..2 either
# side, x 0..10; an exit ramp replaces the top wall at x 4..6
XY = {1: (0, -2), 2: (10, -2), 3: (0, -1), 4: (10, -1), 5: (0, 1), 6: (4, 1), 7: (6, 1),
      8: (10, 1), 9: (0, 2), 10: (4, 2), 11: (6, 2), 12: (10, 2)}


def _channel():
    return _Map({
        0: ("tunnel_trench", "channel_floor:0", [3, 4, 8, 7, 6, 5]),
        1: ("retaining_wall", REF, [1, 2, 4, 3]),
        2: ("retaining_wall", REF, [5, 6, 10, 9]),
        3: ("tunnel_ramp", "channel_ramp:0", [6, 7, 11, 10]),
        4: ("retaining_wall", REF, [7, 8, 12, 11])})


def _voids(m):
    return [f for f in m.faces.values() if f.role == _g.VOID_ROLE]


def _doc(m, outlines, xy=XY):
    ll = {v: (37.9 + y * 1e-4, 23.9 + x * 1e-4) for v, (x, y) in xy.items()}
    bls = [{"id": k, "kind": _g.RIM_KIND, "ref": f"{f.ref}@{f.id}", "vertices": list(r)}
           for k, (f, r) in enumerate((f, r) for f in _voids(m)
                                      for r in _g.rim_runs(m, f))]
    prov = {_pr.CUT_RINGS_KEY: outlines} if outlines else {}
    return {"vertices": [[v, la, lo, 70.0] for v, (la, lo) in ll.items()],
            "faces": [], "breaklines": bls, "provenance": prov}, ll


def test_key_literal_matches_writer():
    assert _pr.CUT_RINGS_KEY == _g.CUT_RINGS_KEY


def test_channel_runs_and_outline():
    m = _channel()
    runs = [r for f in _voids(m) for r in _g.rim_runs(m, f)]
    assert len(runs) == 3 and all(r[0] != r[-1] for r in runs)
    out = _g._cut_rings(m, _voids(m))
    assert len(out) == 1 and out[0]["ref"] == f"{REF}@1"
    ring = out[0]["ring"]
    # every rim vertex once (the ramp's feet 6, 7 stand on no run), in
    # outline order: the ramp top 11 -> 10 and the end lines 4 -> 8, 5 -> 3
    # are walked across, never the cut
    assert sorted(ring) == sorted(set(XY) - {6, 7})
    i = ring.index(1)
    assert (ring[i:] + ring[:i]) == [1, 2, 4, 8, 12, 11, 10, 9, 5, 3]


def test_reader_one_ring_inside_and_outside():
    m = _channel()
    doc, _ll = _doc(m, _g._cut_rings(m, _voids(m)))
    _pads, rims = _pr.pads_rims_from_graded_doc(doc)
    assert [r.ref for r in rims] == [f"{REF}@1"]
    on_floor = (37.9, 23.9 + 5e-4)
    above_crest = (37.9 + 2.2e-4, 23.9 + 5e-4)          # 0.2 units outside
    assert _ar.rim_of(rims, *on_floor) is rims[0]
    assert _ar.rim_of(rims, *above_crest) is None
    # today's reading: each run closed by its chord misses the floor
    doc0, _ = _doc(m, ())
    _p, rims0 = _pr.pads_rims_from_graded_doc(doc0)
    assert len(rims0) == 3 and _ar.rim_of(rims0, *on_floor) is None


def test_rim_anchor_stands_off_away_from_the_cut():
    m = _channel()
    doc, ll = _doc(m, _g._cut_rings(m, _voids(m)))
    _pads, (rim,) = _pr.pads_rims_from_graded_doc(doc)
    # a crest vertex: its anchor stands OUTSIDE the outline
    for v in (9, 12, 2, 10, 11):
        i = rim.ring.index(ll[v])
        la, lo = _ar.rim_anchor_point(rim.ring, i)
        assert not _ar._inside(rim.ring, la, lo), v


def test_u_publishes_nothing():
    # a U: one void round three sides of its ramp, open where it climbs out
    xy = {21: (0, -2), 22: (11, -2), 23: (11, 2), 24: (0, 2), 25: (0, 1), 26: (10, 1),
          27: (10, -1), 28: (0, -1)}
    m = _Map({
        0: ("tunnel_ramp", "tunnel_ramp:0", [28, 27, 26, 25]),
        1: ("retaining_wall", "tunnel_wall:0", [21, 22, 23, 24, 25, 26, 27, 28])})
    v = [f for f in m.faces.values() if f.role == _g.VOID_ROLE]
    (run,) = _g.rim_runs(m, v[0])
    assert run[0] != run[-1]
    assert _g._cut_rings(m, v) == []
    doc, _ll = _doc(m, (), xy)
    _p, rims = _pr.pads_rims_from_graded_doc(doc)
    assert [r.ref for r in rims] == ["tunnel_wall:0@1"]


def test_closed_basin_publishes_nothing_and_reads_as_today():
    m = _Map({1: ("retaining_wall", "basin_wall:0", [1, 2, 12, 9])})
    v = list(m.faces.values())
    (run,) = _g.rim_runs(m, v[0])
    assert run[0] == run[-1]
    assert _g._cut_rings(m, v) == []
    doc, _ll = _doc(m, ())
    _p, rims = _pr.pads_rims_from_graded_doc(doc)
    assert [r.ref for r in rims] == ["basin_wall:0@1"]


def test_walled_end_two_voids_share_a_divider_foot():
    # one end walled (a void face of its own), the other open: the foot of
    # the edge two void faces share stands inside the piece, not on its
    # outline (MEASURED LGAV channel_wall:0#1@299 / @457)
    xy = {31: (0, -2), 32: (2, -2), 33: (10, -2), 34: (10, -1), 35: (2, -1), 36: (2, 1),
          37: (10, 1), 38: (10, 2), 39: (2, 2), 40: (0, 2)}
    m = _Map({
        0: ("tunnel_trench", "channel_floor:0", [35, 34, 37, 36]),
        1: ("retaining_wall", REF, [32, 33, 34, 35]),
        2: ("retaining_wall", REF, [31, 32, 35, 36, 39, 40]),
        3: ("retaining_wall", REF, [36, 37, 38, 39])})
    out = _g._cut_rings(m, _voids(m))
    assert len(out) == 1
    ring = out[0]["ring"]
    assert sorted(ring) == [31, 32, 33, 34, 37, 38, 39, 40]
    doc, _ll = _doc(m, out, xy)
    _p, rims = _pr.pads_rims_from_graded_doc(doc)
    assert [r.ref for r in rims] == [f"{REF}@1"]
    assert _ar.rim_of(rims, 37.9, 23.9 + 5e-4) is rims[0]
