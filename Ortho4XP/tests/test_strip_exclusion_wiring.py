"""Twins for the STRIP-EXCLUSION WIRING (owner rulings 2026-08-24, third
item; the law itself is RULING 2026-08-21d / spec AMENDMENT A4.2).

RULING 2026-08-21d was found UNIMPLEMENTED in production on 2026-08-24:
``grade_graph.GradeContext.strip_keepout`` was declared, documented and
NEVER ASSIGNED by either context builder, so ``strip_excluded_flags`` read
None on every build, ``grade_law.is_apron_in_strip`` answered False for
every pair, and the ruling's acceptance counts came from a re-derivation
rather than from the law.  ``test_production_build_context_fills_the_
strip_keepout`` FAILS on that state by construction.

Headless, geometry-only, no network and no X-Plane install.
"""

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch import grade_graph as GG                       # noqa: E402
from auto_patch import grade_law as GL                         # noqa: E402


# ── 3. THE STRIP EXCLUSION, WIRED ─────────────────────────────────────

class _Prep:
    """A minimal stand-in for the prepared strip keep-out: the law only
    ever asks ``intersects(Point)`` of it (``strip_excluded_flags``)."""

    def __init__(self, poly):
        self._poly = poly

    def intersects(self, geom):
        return self._poly.intersects(geom)


def test_an_apron_sliver_in_the_runway_strip_contributes_zero_pairs():
    """HECA -12251, synthetically: a long thin apron sliver welded onto a
    runway shoulder, wholly inside the strip footprint.  Under A4.2 it is
    not apron law at all, so it contributes ZERO pairs.

    THIS TWIN FAILS ON THE UNWIRED STATE.  Before 2026-08-24 nothing ever
    assigned ``GradeContext.strip_keepout``, so ``strip_excluded_flags``
    read None, every flag was False, and the sliver's pairs were graded as
    apron body."""
    ring = [(0.0, 0.0), (200.0, 0.0), (200.0, 10.0), (0.0, 10.0)]
    keys = list(range(len(ring)))
    strip = _Prep(Polygon([(-50, -50), (400, -50), (400, 80), (-50, 80)]))

    excluded = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], strip_keepout=strip))
    assert excluded.edges == [], (
        "an apron pair inside the runway strip is not apron law (A4.2)")
    assert excluded.strip_excluded == set(keys), (
        "the excluded nodes must be published — the law SKIPS their "
        "pairs, so nothing downstream could otherwise see them")

    # Control: the identical ring with no keep-out is fully graded.
    control = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[]))
    assert control.edges, "the control arm must produce pairs"


def test_an_excluded_node_reads_seniority_excluded():
    """The third seniority value, exported for the census and the trouble
    map.  ``excluded`` OVERRIDES both other values — a strip node carries
    no apron law, so no pair and no transect row can make it senior."""
    sen = GL.apron_node_seniority(
        apron_nodes=[1, 2, 3, 4],
        strict_pairs=[(1, 2), (3, 4)],
        transect_nodes=[3],
        excluded_nodes=[4])
    assert sen[1] == GL.APRON_SENIOR
    assert sen[2] == GL.APRON_SENIOR
    assert sen[3] == GL.APRON_SENIOR
    assert sen[4] == GL.APRON_EXCLUDED, (
        "excluded must win over senior — a strip node has no apron law")


def _strip_layout():
    """HECA -12251's shape: a 666 m x 10 m apron sliver lying on a runway
    shoulder, wholly inside the strip footprint."""
    from auto_patch.layout import (PavementLayout, BuiltShape,
                                   ROLE_RUNWAY, ROLE_APRON)
    L = PavementLayout("TEST", anchor=(30.1, 31.4))
    L.shapes = [
        BuiltShape(polygon=Polygon([(0, -22.5), (3000, -22.5),
                                    (3000, 22.5), (0, 22.5)]),
                   role=ROLE_RUNWAY, ref="05C/23C"),
        BuiltShape(polygon=Polygon([(500, 30), (1166, 30),
                                    (1166, 40), (500, 40)]),
                   role=ROLE_APRON, ref="apron-12251"),
    ]
    return L


def test_production_build_context_fills_the_strip_keepout():
    """THE WIRING, BEHAVIOURALLY — this is the twin that FAILS on the
    unwired state.

    ``GradeContext.strip_keepout`` was declared and documented the day
    A4.2 landed and NOTHING EVER ASSIGNED IT, so on every production build
    ``strip_excluded_flags`` read None, every flag was False and
    ``is_apron_in_strip`` answered False for every pair — the ruling's
    acceptance counts came from a re-derivation, not from the law.  Here
    the real ``build_context`` runs on a real layout and the sliver's
    pairs must be gone."""
    from auto_patch.layout import ROLE_APRON
    L = _strip_layout()
    ctx = GG.build_context(L)
    assert ctx.strip_keepout is not None, (
        "build_context must fill strip_keepout — the unwired state is "
        "exactly None here")

    ring = [(500.0, 30.0), (1166.0, 30.0), (1166.0, 40.0), (500.0, 40.0)]
    assert GG.strip_excluded_flags(ring, ctx) == [True] * 4
    sc = GG.shape_constraints(
        GG.GradeShape(role=ROLE_APRON, ring=ring, keys=[0, 1, 2, 3]), ctx)
    assert sc.edges == [], "-12251's class must contribute zero pairs"
    assert sc.strip_excluded == {0, 1, 2, 3}


def test_both_context_builders_fill_strip_keepout():
    """The wiring itself, asserted on the SOURCE of both readers: the
    field was declared and documented from the day A4.2 landed and NOTHING
    EVER ASSIGNED IT, which is how the acceptance counts came from a
    re-derivation instead of from the law.  A regression that removes
    either assignment fails here."""
    root = Path(__file__).resolve().parents[1]
    solver = (root / "src" / "auto_patch" / "grade_graph.py").read_text()
    census = (root / "tools" / "check_grade.py").read_text()
    assert "strip_keepout=strip_keepout," in solver, (
        "grade_graph.build_context must fill GradeContext.strip_keepout")
    assert "strip_keepout=strip_keepout," in census, (
        "check_grade._grade_context_from_osm must fill it too")
    # ONE law geometry, both sides.
    assert "runway_strip_wall_keepout" in solver
    assert "_runway_strip_keepout_rings(ways, nodes, ll_to_m)" in census


def test_the_seniority_call_sites_pass_excluded_nodes():
    """Both call sites named in the ruling's wiring order."""
    root = Path(__file__).resolve().parents[1]
    one = (root / "src" / "auto_patch" / "elevation_per_surface"
           / "route_profile" / "one_solve.py").read_text()
    slv = (root / "src" / "auto_patch" / "elevation_per_surface"
           / "route_profile" / "solve.py").read_text()
    assert "excluded_nodes=_ex" in one
    assert "excluded_nodes=_excl" in slv
    assert "apron_excluded_nodes" in slv
