"""A PAD WELDS TO THE APRON IT FRONTS; A TOUCHING APRON AT ANOTHER LEVEL IS A
TERRACE — the twins (owner RULINGS 2026-09-28a (6) + 28b; issue #11
[HECA-6]; ``planar/pad_terrace``).

The site: HECA's cargo complex (``building52`` in the 09-26 patch,
``building50`` on 273eeffa) FACES the high east apron ``pav37`` across
20-40 m of bare ground along its whole east edge, and TOUCHES the low apron
``dsf:objpav399`` at its north-east corner, where a lower pad
(``building135`` / ``building127``) also stands.  The owner: the complex
stays with the high apron; a WALL/TERRACE separates it from objpav399 and
the lower pad.

The fixture: pad P 40 m x 200 m; the HIGH apron B (DEM 704) 30 m east of
its east edge; the LOW apron A (DEM 698) touching its north edge; the
lower pad Q west of P's north end, sharing P's rim and touching A.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import pad_fronting, pads
from auto_patch_v2.law import Law
from auto_patch_v2.planar import pad_terrace
from auto_patch_v2.planar.build import build

from test_v2frontage import HALF_W, RUN_LEN, _airport, _rect  # noqa: E402

P = _rect(-20.0, 200.0, 20.0, 400.0)
#: the same pad with its north (terrace) edge and the top of its west edge
#: vertexed every 5 m, as a pack footprint ring is
P_DENSE = ((-20.0, 200.0), (20.0, 200.0),
           *[(20.0 - 5.0 * i, 400.0) for i in range(0, 9)],
           *[(-20.0, 400.0 - 5.0 * i) for i in range(1, 9)])
A = _rect(-60.0, 400.0, 10.0, 460.0)
B = _rect(50.0, 200.0, 150.0, 400.0)
Q = _rect(-60.0, 360.0, -20.0, 400.0)


class _Dem:
    provenance = {"synthetic": "cargo_hill"}

    def __init__(self, flat: bool = False):
        self.flat = flat

    def z(self, x: float, y: float) -> float:
        if self.flat:
            return 700.0
        if x >= 35.0:
            return 704.0
        return 698.0 if y >= 395.0 else 702.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _cells(lower_pad: bool = True, front_touches: bool = False, pad=P):
    east = _rect(20.0, 200.0, 150.0, 400.0) if front_touches else B
    out = [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                (), 3, "D", "airside", "runway", {}),
           Cell(1, "apron", "apronLow", A, (), None, None, "airside", "apron", {}),
           Cell(2, "building", "padP", pad, (), None, None, "airside", "pad", {}),
           Cell(3, "apron", "apronHigh", east, (), None, None, "airside", "apron", {})]
    if lower_pad:
        out.append(Cell(4, "building", "padQ", Q, (), None, None, "airside", "pad", {}))
    return out


@pytest.fixture(scope="module")
def law():
    from tests.auto_patch_v2._plate import plate_law
    return plate_law(Law.for_airport("ZZZZ"))    # the subject is the plate (28b)


def _built(law, cells, flat=False):
    airport = _airport(law, _Dem(flat))
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return pm, airport


def _fid(pm, ref):
    return next(f.id for f in pm.faces.values() if f.ref == ref)


def _vs(pm, fid):
    return {v for v, vx in pm.vertices.items() if fid in vx.incident_faces}


def test_the_touching_low_apron_is_split_off_as_a_terrace(law):
    """P fronts the high apron (its longest facing edge); the low apron at
    its corner shares NO vertex with it and stands beyond §20's horizon,
    so the pad no longer fronts it; the facing row is the SENIOR one."""
    pm, airport = _built(law, _cells(lower_pad=False))
    kinds = [(t.kind, t.pad_ref, t.other_ref, t.front_ref) for t in pad_terrace.TERRACES]
    assert kinds == [("apron", "padP", "apronLow", "apronHigh")]
    t = pad_terrace.TERRACES[0]
    assert t.front_level == pytest.approx(704.0) and t.other_level == pytest.approx(698.0)
    p, a = _fid(pm, "padP"), _fid(pm, "apronLow")
    assert not (_vs(pm, p) & _vs(pm, a))
    near = float(law.tables.emit.design.pad_frontage_m)
    d = min(((pm.vertices[u].xy[0] - pm.vertices[w].xy[0]) ** 2 +
             (pm.vertices[u].xy[1] - pm.vertices[w].xy[1]) ** 2) ** 0.5
            for u in _vs(pm, p) for w in _vs(pm, a))
    assert d > near
    assert p not in pads.pad_frontage(pm, law)
    g = pad_fronting.analysis(pm, law, airport)["groups"][p]
    assert g["senior"]
    rows = pad_fronting.pad_fronting_level(pm, law, airport)
    assert rows and all(r.source.ruling.startswith(pads.LEVEL_RULING + " ") for r in rows)


def test_the_lower_pad_at_the_corner_is_split_from_the_upper_pad(law):
    """The lower pad touches the low apron and shared P's rim: the rim is
    split (two vertex sets), and the lower pad still fronts its apron."""
    pm, _a = _built(law, _cells(lower_pad=True))
    kinds = sorted((t.kind, t.other_ref) for t in pad_terrace.TERRACES)
    assert kinds == [("apron", "apronLow"), ("pad", "padQ")]
    p, q, a = _fid(pm, "padP"), _fid(pm, "padQ"), _fid(pm, "apronLow")
    assert not (_vs(pm, p) & _vs(pm, q))
    assert q in pads.pad_frontage(pm, law)


def test_a_touching_apron_at_the_same_level_stays_welded(law):
    pm, _a = _built(law, _cells(lower_pad=False), flat=True)
    assert pad_terrace.TERRACES == []
    assert _vs(pm, _fid(pm, "padP")) & _vs(pm, _fid(pm, "apronLow"))


def test_a_pad_touching_the_apron_it_fronts_is_left_to_20(law):
    """The front itself touches: §20's weld, nothing split."""
    pm, _a = _built(law, _cells(lower_pad=False, front_touches=True))
    assert pad_terrace.TERRACES == []
    assert _vs(pm, _fid(pm, "padP")) & _vs(pm, _fid(pm, "apronLow"))


def test_the_terrace_is_declared_as_a_joint_between_the_two_bodies(law):
    """The strip is published in ``terrace_joints`` (kind ``pad_terrace``)
    so the census forgives the step across it like a shape joint's."""
    from auto_patch_v2.pipeline.publication import pad_terrace_joints
    pm, _a = _built(law, _cells(lower_pad=True, pad=P_DENSE))
    z = [700.0] * (max(pm.vertices) + 1)
    recs = pad_terrace_joints(pm, law, z)
    assert sorted(tuple(r["shapes"]) for r in recs) == [("padP", "apronLow"), ("padP", "padQ")]
    assert all(r["kind"] == "pad_terrace" and r["pairs"] >= 2 and len(r["points"]) >= 2
               for r in recs)
    lat = [p[0] for r in recs for p in r["points"]]
    assert all(abs(la) > 1.0 for la in lat)       # (lat, lon), not frame metres


def test_a_junior_facing_row_never_crosses_a_declared_pad_terrace(law):
    """SPEC-AUTHOR RULINGS 2026-09-29s (C) (#96): a pad split off an upper
    pad by a declared 28b terrace (kind ``pad``) sits at the level of the
    apron it touches; a JUNIOR facing row toward the upper pad's FRONT
    apron — an apron standing nearer the terrace's FRONT level than its
    other level, i.e. across that terrace — is not minted (report-only
    noise, HECA building131 against pav37).  Every senior row is
    unchanged.  (``padQ`` touches ``apronLow`` at 698 — its senior — and
    faces ``apronW`` at ~702 across 12 m of bare ground; the one variable
    is the ``padP|padQ`` declaration, 704 vs 698.)"""
    cells = _cells(lower_pad=True) + [
        Cell(9, "apron", "apronW", _rect(-110.0, 330.0, -72.0, 392.0), (),
             None, None, "airside", "apron", {})]
    pm, airport = _built(law, cells)
    q = _fid(pm, "padQ")

    def junior_rows():
        pad_fronting._CACHE.clear()
        rows = pad_fronting.pad_fronting_level(pm, law, airport)
        return [r for r in rows if r.source.ruling.startswith(pads.LEVEL_JUNIOR_RULING)
                and set(r.follows or ()) & _vs(pm, q)]

    kept = list(pad_terrace.TERRACES)
    try:
        pad_terrace.TERRACES[:] = [t for t in kept if t.other_ref != "padQ"]
        assert junior_rows(), "the fixture must face apronW with a junior row"
        t0 = next(t for t in kept if t.kind == "pad" and t.other_ref == "padQ")
        assert (t0.front_level, t0.other_level) == (704.0, 698.0)
        pad_terrace.TERRACES[:] = kept
        assert not junior_rows()       # apronW (~702) is the UPPER side
        assert pad_fronting.STATS["pad_fronting_across_terrace"]["junior_dropped"] >= 1
    finally:
        pad_terrace.TERRACES[:] = kept
        pad_fronting._CACHE.clear()


class _GapDem(_Dem):
    """The cargo hill with the low apron ``gap`` metres under the high one."""

    def __init__(self, gap: float):
        super().__init__()
        self.gap = gap

    def z(self, x: float, y: float) -> float:
        if x >= 35.0:
            return 704.0
        return 704.0 - self.gap if y >= 395.0 else 704.0 - self.gap / 2.0


@pytest.mark.parametrize("gap,split", [(0.7, False), (0.99, False), (1.0, True), (1.4, True)])
def test_the_30i_floor_welds_under_one_metre_and_terraces_at_it(law, gap, split):
    """Owner RULINGS 2026-09-30i: the 28b pad|apron terrace floor is
    ``[terrace] pad_terrace_floor_m`` = 1.0 m (was ``cockpit.visual_m``
    0.5).  HECA's pads facing ``objpav1``: building157|objpav450 and
    building159|objpav449 at 0.5-0.7 m WELD; building152|pav98 at ~1.4 m
    TERRACES.  The pad's own weld span (``pad_slope_max`` x contact
    distance) is narrowed so the floor alone decides."""
    assert float(law.tables.emit.terrace.pad_terrace_floor_m) == 1.0
    ws = _dc.replace(law.tables.emit.within_shape, pad_slope_max=0.001)
    em = _dc.replace(law.tables.emit, within_shape=ws)
    lw = _dc.replace(law, tables=_dc.replace(law.tables, emit=em))
    airport = _airport(lw, _GapDem(gap))
    pm, _st = build(airport, Classification(tuple(_cells(lower_pad=False)), (), {}, ()), lw)
    kinds = [(t.kind, t.other_ref) for t in pad_terrace.TERRACES]
    shared = _vs(pm, _fid(pm, "padP")) & _vs(pm, _fid(pm, "apronLow"))
    if split:
        assert kinds == [("apron", "apronLow")]
        assert pad_terrace.TERRACES[0].bound_m == pytest.approx(1.0)
        assert not shared
    else:
        assert kinds == []
        assert shared
