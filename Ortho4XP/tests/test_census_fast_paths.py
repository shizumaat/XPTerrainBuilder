"""#2008: the census's fast paths read exactly what the slow ones did.

THE TERRACE STEP SUM is read only when it can matter.

``_check_within_shape`` used to sum the declared terrace steps a chord
crosses for EVERY constrained pair — a chord against every declared joint
segment, which on a KMCI closing patch (13 M within-shape pairs) kept the
census busy for tens of minutes.  When every declared step is >= 0 the
envelope only grows with that sum, so a pair inside the envelope WITHOUT
it is inside WITH it, and the sum is skipped.  These twins hold the
verdicts identical: the envelope arithmetic against the pre-#2008 inline
order, and the whole law-true row set eager vs lazy on registered frames.

THE CANDIDATE FILTERS (``_VertexBoxIndex`` for the straddle reading, the
cell block of ``_StretchBox.tied``) and ``PairContext.with_pair`` are held
to the full scan / the plain constructor they replace.
"""
from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

FRAMES = Path("/Users/noah/XPTerrainBuilderData/.harness/frames")
#: registered frames that declare terrace joints (``tools/harness/frames.py``)
TERRACE_FRAMES = (
    FRAMES / "lvnlk" / "lvnlk6.osm",
    FRAMES / "lrwypin" / "CBR2_20261026T133309.osm",
)


@pytest.fixture(scope="module")
def cg():
    spec = importlib.util.spec_from_file_location(
        "lazy_terrace_check_grade", ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _inline_envelope(a, steps, late, weld, zone_cap, dist, tier_shift):
    """The pre-#2008 inline order of ``_check_within_shape``."""
    if steps is not None:
        a += steps
    if late is not None:
        a += late
    if weld is not None:
        a += weld
    if zone_cap is not None:
        a = max(a, zone_cap * dist)
    if tier_shift is not None:
        a = a + tier_shift
    return a


def test_the_envelope_adds_its_terms_in_the_law_order(cg):
    rnd = random.Random(2008)
    for _ in range(20000):
        terms = (rnd.uniform(0, 30), rnd.choice([None, rnd.uniform(0, 2)]),
                 rnd.choice([None, rnd.uniform(-0.5, 0.5)]),
                 rnd.choice([None, rnd.uniform(0, 0.4)]),
                 rnd.choice([None, rnd.uniform(0, 0.1)]),
                 rnd.uniform(0.5, 900), rnd.choice([None, rnd.uniform(-1, 1)]))
        assert cg._pair_envelope(*terms) == _inline_envelope(*terms)


def test_a_pair_inside_without_the_steps_is_inside_with_them(cg):
    rnd = random.Random(20080)
    for _ in range(20000):
        a = rnd.uniform(0, 30)
        rest = (rnd.choice([None, rnd.uniform(-0.5, 0.5)]),
                rnd.choice([None, rnd.uniform(0, 0.4)]),
                rnd.choice([None, rnd.uniform(0, 0.1)]),
                rnd.uniform(0.5, 900), rnd.choice([None, rnd.uniform(-1, 1)]))
        steps = rnd.choice([0.0, rnd.uniform(0, 5)])
        assert (cg._pair_envelope(a, steps, *rest)
                >= cg._pair_envelope(a, 0.0, *rest))


def test_a_negative_declared_step_reads_every_pair(cg):
    joints = [([(0.0, 0.0), (1.0, 0.0)], 0.5), ([(0.0, 1.0), (1.0, 1.0)], -0.2)]
    assert cg._terrace_steps_nonneg(joints) is False
    assert cg._terrace_steps_nonneg(joints[:1]) is True


def _law_true_rows(cg, osm: Path) -> dict:
    fam: dict = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    return {k: sorted(repr(r) for r in v) for k, v in fam.items()
            if isinstance(v, list) and not k.startswith("_")}


@pytest.mark.parametrize("osm", TERRACE_FRAMES, ids=lambda p: p.stem)
def test_the_law_true_rows_are_identical_eager_and_lazy(cg, osm, monkeypatch):
    if not (osm.is_file() and Path(str(osm) + ".axes.json").is_file()):
        pytest.skip(f"registered frame {osm} is not on this machine")
    lazy = _law_true_rows(cg, osm)
    monkeypatch.setattr(cg, "_terrace_steps_nonneg", lambda _joints: False)
    eager = _law_true_rows(cg, osm)
    assert lazy == eager
    assert sum(map(len, lazy.values())) > 0


def test_the_vertex_box_index_keeps_every_vertex_in_reach(cg):
    rnd = random.Random(7)
    verts = [(rnd.uniform(-500, 500), rnd.uniform(-500, 500), 0.0, None)
             for _ in range(3000)] + [(float("nan"), 0.0, 0.0, None)]
    idx = cg._VertexBoxIndex(verts, 5.0)
    for _ in range(200):
        x0, y0 = rnd.uniform(-500, 500), rnd.uniform(-500, 500)
        line = [(x0 + rnd.uniform(-60, 60), y0 + rnd.uniform(-60, 60))
                for _k in range(rnd.randint(2, 6))]
        got = idx.candidates(line)
        want = [v for v in verts
                if not min(cg._seg_point_distance(v[0], v[1], a, b)
                           for a, b in zip(line, line[1:], strict=False)) > 5.0]
        kept = {id(v) for v in got}
        assert all(id(v) in kept for v in want)
        assert got == [v for v in verts if id(v) in kept]     # order kept
    assert idx.candidates(line[:1]) == verts


class _Law:
    """The two law tables ``_StretchBox`` reads, as plain attributes."""

    class _T:
        def value(self, _ctx, letter):
            return {"A": 0.015, "B": 0.02}.get(letter, 0.015)

    def __init__(self):
        from types import SimpleNamespace as NS
        self.tables = NS(emit=NS(within_shape=NS(withdrawn_chord_min_m=30.0)),
                         precedence=NS(taxi_family=NS(members=("stub",))))
        self.ruleset = NS(taxi=NS(transverse=self._T()))


def _full_scan_tied(box, x, y, tie_m=1e-6):
    ds = box._distances(x, y, range(len(box.segs)))
    d0 = min(d for d, *_r in ds)
    return [(ux, uy, cl, ct) for d, ux, uy, cl, ct in ds if abs(d - d0) <= tie_m]


def test_the_stretch_box_tie_reads_the_whole_map(cg):
    rnd = random.Random(11)
    stretches = []
    for _ in range(60):
        x0, y0 = rnd.uniform(0, 2000), rnd.uniform(0, 2000)
        pts = [(x0, y0)]
        for _k in range(rnd.randint(1, 5)):
            pts.append((pts[-1][0] + rnd.uniform(-80, 80),
                        pts[-1][1] + rnd.uniform(-80, 80)))
        stretches.append([pts, rnd.choice([0.015, 0.02]), rnd.choice("AB")])
    # a corner shared by two stretches: an exact tie
    stretches.append([[(1000.0, 1000.0), (1100.0, 1000.0)], 0.015, "A"])
    stretches.append([[(1000.0, 1000.0), (1000.0, 1100.0)], 0.02, "B"])
    box = cg._StretchBox(stretches, lambda la, lo: (la, lo), _Law())
    probes = [(1000.0, 1000.0), (1050.0, 1050.0)] + [
        (rnd.uniform(-300, 2300), rnd.uniform(-300, 2300)) for _ in range(3000)]
    for x, y in probes:
        assert box.tied(x, y) == _full_scan_tied(box, x, y)


def test_with_pair_builds_the_context_the_constructor_builds(cg):
    from harness.law_support import grade_law as GL
    base = GL.PairContext(role="runway", dist=0.0, ring_adjacent=False,
                          a_seam=False, b_seam=False, a_building=False,
                          b_building=False, spine_caps=(), body_cap=0.015,
                          both_road=False)
    got = base.with_pair(12.5, True, False, True, True)
    want = GL.PairContext(role="runway", dist=12.5, ring_adjacent=True,
                          a_seam=False, b_seam=True, a_building=False,
                          b_building=False, spine_caps=(), body_cap=0.015,
                          both_road=True)
    assert got == want and hash(got) == hash(want)
    assert got.__dict__ == want.__dict__
    assert base.dist == 0.0 and base.both_road is False


def test_the_shore_index_finds_the_first_segment_a_point_is_on(cg):
    rnd = random.Random(1177)
    segs = []
    for _ in range(400):
        x0, y0 = rnd.uniform(0, 3000), rnd.uniform(0, 3000)
        segs.append(((x0, y0), (x0 + rnd.uniform(-90, 90), y0 + rnd.uniform(-90, 90)),
                     rnd.choice([0.0, 1.5, 3.0])))
    segs.append(((0.0, 0.0), (2900.0, 2900.0), 7.0))      # one long diagonal
    segs.append(((500.0, 500.0), (500.0, 500.0), 2.0))    # a degenerate one
    indexed = cg._ShoreSegments(segs)
    probes = [(500.0, 500.2), (1450.0, 1450.3)] + [
        (s[0][0] + rnd.uniform(-1, 1), s[0][1] + rnd.uniform(-1, 1)) for s in segs
    ] + [(rnd.uniform(-50, 3050), rnd.uniform(-50, 3050)) for _ in range(3000)]
    for pt in probes:
        assert (cg._shore_level(pt, indexed, cg.SEA_WALL_ON_SHORE_M)
                == cg._shore_level(pt, list(segs), cg.SEA_WALL_ON_SHORE_M))
