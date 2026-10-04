"""Unit tests for the NEAR-MISS building-frontage recognition (2026-07-08).

A DSF building-pad outline and the apt.dat apron edge it fronts can be offset
by a sub-metre source mismatch (SPJC building29 vs its SW apron: 0.68 m),
leaving a thin unpaved sliver that defeats every exact-identity reconciler
(they all key off ``SHARED_VERTEX_TOL_M`` = 0.5 m, the one canonical
identity).  ``anchors._near_miss_frontage_contacts`` recognizes such pairs
per-EDGE and its two consumers emit raise-biased soft floors
(``near_miss_building_frontage_floors``) and joint-projection law edges
(``near_miss_building_frontage_edges``) toward the pad's ALREADY-CHOSEN seat.

These tests pin the recognition contract:

* a pad + apron at a 0.7 m offset (inside ``BUILDING_FRONTAGE_NEAR_MISS_M``)
  gets the raise anchors — floors ``seat − APRON_MAX_GRADE·d`` and edges with
  budget ``APRON_MAX_GRADE·d``;
* the same pair at a 1.5 m offset (outside the radius) gets nothing;
* the pad seat is UNCHANGED in both cases (raise-biased: the near-miss edge
  never feeds the pad's seat);
* a genuinely SHARED (vertex-welded) frontage is not a near miss — identity
  already reconciles it, so no anchors are emitted;
* the retired ``O4_BUILDING_FRONTAGE_NEAR_MISS`` var cannot disable
  recognition (standing law, 2026-08-05).
"""
from __future__ import annotations

import pytest

from auto_patch.config import APRON_MAX_GRADE

PAD_SEAT = 25.56


class _Shape:
    def __init__(self, role, polygon, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref


def _open_ring(polygon):
    coords = list(polygon.exterior.coords)
    return coords[:-1] if coords[0] == coords[-1] else coords


def _wide_band(_x, _y):
    return (0.0, 1000.0)


# ── PAD ROD COUPLING contact map (docs/specs/pad-rod-coupling-spec.md) ───


# ══════════════════════════════════════════════════════════════════════
# THE CENSUS TWIN — ``check_grade._check_frontage_near_miss``
# ══════════════════════════════════════════════════════════════════════
# LOCKSTEP (docs/RULINGS.md, grade-law completeness): a law needs BOTH a
# generation-binding constraint (the edges above) AND its validator twin.
# The law BOUND in the solve for a month (measured edge counts HEAZ 4 ·
# SPJC 12-38 · KCLT 78-86 · HECA 118-138) with nothing measuring it on the
# emitted patch: ``cross_shape`` is scoped to SHARED_VERTEX_TOL_M (0.5 m)
# and reads 0 everywhere, so enforcing the frontage could only ever have
# shown up as unattributed within-shape noise.  Cycle-5 instrument-fix
# spec item 6 registered the family; these are its hermetic twins — a
# synthetic emitted patch, no build, no network.

import importlib.util as _ilu                                 # noqa: E402
import sys as _sys                                            # noqa: E402
from pathlib import Path as _Path                             # noqa: E402

_ROOT = _Path(__file__).resolve().parents[1]


def _load_check_grade():
    for p in (_ROOT / "src", _ROOT, _ROOT / "tools"):
        if str(p) not in _sys.path:
            _sys.path.insert(0, str(p))
    spec = _ilu.spec_from_file_location(
        "near_miss_twin_check_grade", _ROOT / "tools" / "check_grade.py")
    mod = _ilu.module_from_spec(spec)
    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


#: ~1 m of latitude / longitude at the fixture anchor, so the synthetic
#: patch's metre frame is the one ``check_grade`` reconstructs.
_LAT0, _LON0 = 0.0, 0.0
_M_PER_DEG = 111320.0


def _write_patch(tmp_path, ways):
    """Write a minimal emitted patch + sidecar.  ``ways`` is
    ``[(role, ref, [(x_m, y_m), ...], elev_m), ...]``; each ring is closed
    for the reader and carries ONE altitude (pads and small test rings are
    flat, which is what the law reads)."""
    nodes, lines, wid = [], [], -1
    nid = 0
    for (role, ref, ring, elev) in ways:
        nids = []
        for (x, y) in ring:
            nid -= 1
            lat = _LAT0 + y / _M_PER_DEG
            lon = _LON0 + x / _M_PER_DEG
            nodes.append(f"  <node id='{nid}' lat='{lat:.11f}' "
                         f"lon='{lon:.11f}' visible='true' />")
            nids.append(nid)
        body = "".join(f"    <nd ref='{n}' />\n" for n in nids + [nids[0]])
        lines.append(
            f"  <way id='{wid}' action='modify' visible='true'>\n{body}"
            f"    <tag k='aeroway' v='{role}' />\n"
            f"    <tag k='altitude' v='{elev:.2f}' />\n"
            f"    <tag k='ref' v='{ref}' />\n"
            f"    <tag k='role' v='{role}' />\n  </way>")
        wid -= 1
    osm = tmp_path / "patch.osm"
    osm.write_text("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
                   + "\n".join(nodes) + "\n" + "\n".join(lines) + "\n</osm>\n", encoding="utf-8", newline="")
    (tmp_path / "patch.osm.axes.json").write_text(
        '{"anchor": [%r, %r], "ruleset": "icao"}' % (_LAT0, _LON0), encoding="utf-8", newline="")
    return osm


def _near_miss_rows(tmp_path, gap_m, apron_elev, pad_elev=PAD_SEAT):
    """The ``frontage_near_miss`` rows for a pad + apron at ``gap_m``."""
    cg = _load_check_grade()
    pad = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)]
    apron = [(0.0, 20.0 + gap_m), (30.0, 20.0 + gap_m),
             (30.0, 60.0), (0.0, 60.0)]
    osm = _write_patch(tmp_path, [("building", "building29", pad, pad_elev),
                                  ("apron", "apron1", apron, apron_elev)])
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    return cg, fam


def test_census_flags_a_near_miss_frontage_step(tmp_path):
    """THE FAMILY BITES.  A 0.7 m sliver with a 0.66 m step (the SPJC
    building29 defect, verbatim) is over the apron-cap budget at every
    endpoint and must be reported."""
    cg, fam = _near_miss_rows(tmp_path, 0.7, PAD_SEAT - 0.66)
    rows = fam["frontage_near_miss"]
    assert rows, ("a 0.66 m step across a 0.7 m sliver was not flagged — the "
                  "near-miss frontage family is a no-op")
    assert all(cg.row_roles(r) == ("apron", "building")
               or cg.row_roles(r) == ("building", "apron") for r in rows)
    assert max(r.de_m for r in rows) == pytest.approx(0.66, abs=1e-6)


def test_census_respects_the_apron_cap_budget(tmp_path):
    """The budget is ``APRON_MAX_GRADE·d``, not zero: a step INSIDE it is
    lawful and must not be reported.  Same geometry, smaller step."""
    _cg, fam = _near_miss_rows(tmp_path, 0.7, PAD_SEAT - 0.001)
    assert fam["frontage_near_miss"] == [], (
        "a step well inside APRON_MAX_GRADE·d was reported — the census twin "
        "is judging a stricter law than the solve prices")


def test_census_ignores_a_pair_beyond_the_recognition_radius(tmp_path):
    """Outside ``BUILDING_FRONTAGE_NEAR_MISS_M`` the pad fronts nothing:
    the pavement is separated by real unpaved ground and grades freely
    (the same scope the solve's recognition uses)."""
    _cg, fam = _near_miss_rows(tmp_path, 1.5, PAD_SEAT - 0.66)
    assert fam["frontage_near_miss"] == [], (
        "a pair 1.5 m apart was judged under the near-miss frontage law — "
        "the census twin has widened the law's scope")


def test_census_never_judges_a_welded_frontage(tmp_path):
    """A SHARED ring node means identity already reconciles the corner, and
    the edge legitimately grades away from the seat.

    IDENTITY IS POSITIONAL, NOT BY NODE ID.  The emitter's test is over
    ``canonical_points``, which interns within ``SHARED_VERTEX_TOL_M``
    (0.5 m); a welded corner can still ship as two distinct OSM node ids at
    one coordinate — that is exactly why a ``stacked_nodes`` family exists.
    This fixture writes the shared corners as SEPARATE ids on purpose, so a
    nid-only twin (the first cut here) judges a reconciled corner as a near
    miss and this test catches it."""
    cg = _load_check_grade()
    pad = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)]
    # A single ring for the apron that SHARES the pad's two top corners.
    apron = [(0.0, 20.0), (30.0, 20.0), (30.0, 60.0), (0.0, 60.0)]
    osm = _write_patch(tmp_path, [("building", "b", pad, PAD_SEAT),
                                  ("apron", "a", apron, PAD_SEAT - 5.0)])
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    for r in fam["frontage_near_miss"]:
        assert min(abs(r.pt_a[0] - cx) + abs(r.pt_a[1] - cy)
                   for (cx, cy) in ((0.0, 20.0), (30.0, 20.0))) > 0.01, (
            "a pad-shared frontage corner was judged as a near miss")


def test_the_census_family_is_registered_and_partitions(tmp_path):
    """The register/emission twin, on THIS family specifically: a check
    that emits rows ``LAW_FAMILIES`` does not name is invisible to every
    census (``tests/test_harness.py`` asserts it globally; this pins the
    bucket, which decides whether the rows reach the cross list)."""
    cg, fam = _near_miss_rows(tmp_path, 0.7, PAD_SEAT - 0.66)
    reg = {key: bucket for key, _title, bucket in cg.LAW_FAMILIES}
    assert reg.get("frontage_near_miss") == "cross", (
        "the near-miss frontage family must land in the CROSS bucket — it is "
        "a two-shape law, and a 'within' bucket would double-count it")
    assert "frontage_near_miss" in fam
