"""THE CENSUS'S KNOWN-ANSWER TWIN (RULINGS 2026-08-06, "Instrument truth
is law", binding point 1: *a known-answer twin, or it is not an
instrument*).

Until this file existed NO test called ``census_one``, ``print_report``,
``zone_split`` or ``print_compare``.  ``tests/test_harness.py`` asserts the
census's STRUCTURE — that it iterates the family register, that it never
enumerates families itself, that the sidecar reader is the only reader —
which keeps it from drifting back into a per-lane wrapper but says nothing
about whether the numbers it prints are the numbers it computed, or whether
either is right.

So: ONE hand-built patch whose every law row is derivable with a
calculator, and assertions on the REPORTED NUMBERS.

THE FIXTURE (metres, in the sidecar anchor's own frame; every shape is a
20 m square, so every ring edge is 20 m and every diagonal 28.284 m):

    A1  apron            [  0, 20]²   corner alts (0, 0, 1.2, 0)
    G1  groundside       [ 20, 40]×[0,20]   alts (0.1, 0, 2.0, 0)
    B1  building  flat 10.0   [200,220]×[0,20]
    B2  building  flat 12.0   [220.6,240.6]×[0,20]
    A4  apron  o4_grade_law=fan_ramp  [250,270]×[0,20]  alts (0,0,2.0,0)
    A2  apron     flat  5.0   [300,320]×[0,20]
    A3  apron     flat  7.0   [320.6,340.6]×[0,20]
    A5  apron            [400,420]×[0,20]   alts (0, 0, 0.5, 0)
    A6  apron            [450,470]×[0,20]   alts (0, 0, 2.0, 0)
    A7  apron            [500,520]×[0,20]   alts (0, 0, 2.0, 0)

    sidecar fan-ramp zones, both at cap 5 %:
        Z1  [398, 472]×[-2, 22]     (covers A5 and A6 whole)
        Z2  [460, 510]×[-2, 22]     (covers A7's western half)

Every count asserted below is derived in the test that asserts it.  The
governing caps are ``auto_patch.config.ROLE_GRADE_LIMITS`` (apron 1 %,
groundside_pavement 5 %, building 1 %) and the allowance rule
``max(baked, cap·d) + quant_noise`` with a 0.03 m emit-noise envelope.

Nothing here builds, downloads or reads the shared data repo.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
sys.path.insert(0, str(ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg():
    return _load("census_twin_check_grade", ROOT / "tools" / "check_grade.py")


@pytest.fixture(scope="module")
def census(cg):
    return _load("census_twin_census", HARNESS / "census.py")


# ══════════════════════════════════════════════════════════════════════
# THE FIXTURE PATCH
# ══════════════════════════════════════════════════════════════════════

ANCHOR = (1.5, 1.5)   # deliberately NOT an integer degree: a node on an
                      # integer lat/lon is seam-anchored and its pairs are
                      # dropped (DEM controls them), which silently empties
                      # every within-shape count.


class _PatchBuilder:
    """Metres in, one ``.patch.osm`` + ``.axes.json`` out.

    The same equirectangular formula ``check_grade._ll_to_m_factory`` uses
    with an anchor, so a corner placed at x=20 m comes back out of the
    parser at x=20 m to float precision.
    """

    def __init__(self, cg):
        self._r = cg.R_EARTH
        self._cos0 = math.cos(math.radians(ANCHOR[0]))
        self.nodes: list = []
        self.ways: list = []
        self._next = 0

    def ll(self, x: float, y: float):
        return (ANCHOR[0] + math.degrees(y / self._r),
                ANCHOR[1] + math.degrees(x / (self._r * self._cos0)))

    def _id(self) -> str:
        self._next -= 1
        return str(self._next)

    def node(self, x, y, alt=None) -> str:
        nid = self._id()
        lat, lon = self.ll(x, y)
        self.nodes.append((nid, lat, lon, alt))
        return nid

    def way(self, nids, tags) -> None:
        self.ways.append((self._id(), list(nids), dict(tags)))

    def square(self, x0, y0, side, alts, tags) -> None:
        """Per-vertex alts, counter-clockwise from the SW corner."""
        ns = [self.node(x0, y0, alts[0]),
              self.node(x0 + side, y0, alts[1]),
              self.node(x0 + side, y0 + side, alts[2]),
              self.node(x0, y0 + side, alts[3])]
        self.way(ns + [ns[0]], tags)

    def square_flat(self, x0, y0, side, alt, tags) -> None:
        """One way-level altitude: a shape lying flat, no internal grade."""
        t = dict(tags)
        t["altitude"] = f"{alt:.2f}"
        ns = [self.node(x0, y0), self.node(x0 + side, y0),
              self.node(x0 + side, y0 + side), self.node(x0, y0 + side)]
        self.way(ns + [ns[0]], t)

    def rect_ring_ll(self, x0, y0, x1, y1) -> list:
        return [list(self.ll(x0, y0)), list(self.ll(x1, y0)),
                list(self.ll(x1, y1)), list(self.ll(x0, y1)),
                list(self.ll(x0, y0))]

    def write(self, path: Path, sidecar: dict, root_attrs: str = "") -> Path:
        out = ["<?xml version='1.0' encoding='UTF-8'?>",
               f"<osm version='0.6' generator='census-twin'{root_attrs}>"]
        for nid, lat, lon, alt in self.nodes:
            head = f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'"
            out.append(f"{head} />" if alt is None else
                       f"{head}><tag k='alt_abs' v='{alt:.2f}' /></node>")
        for wid, nids, tags in self.ways:
            out.append(f"  <way id='{wid}'>")
            out += [f"    <nd ref='{n}' />" for n in nids]
            out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
            out.append("  </way>")
        out.append("</osm>")
        path.write_text("\n".join(out) + "\n")
        Path(str(path) + ".axes.json").write_text(json.dumps(sidecar))
        return path


def _build_fixture(cg, tmp_path: Path, *, root_attrs: str = "") -> Path:
    b = _PatchBuilder(cg)
    b.square(0, 0, 20, [0.0, 0.0, 1.2, 0.0],
             {"role": "apron", "shapeID": "A1"})
    b.square(20, 0, 20, [0.1, 0.0, 2.0, 0.0],
             {"role": "groundside_pavement", "shapeID": "G1"})
    b.square_flat(200, 0, 20, 10.0, {"role": "building", "shapeID": "B1"})
    b.square_flat(220.6, 0, 20, 12.0, {"role": "building", "shapeID": "B2"})
    b.square(250, 0, 20, [0.0, 0.0, 2.0, 0.0],
             {"role": "apron", "shapeID": "A4", "o4_grade_law": "fan_ramp"})
    b.square_flat(300, 0, 20, 5.0, {"role": "apron", "shapeID": "A2"})
    b.square_flat(320.6, 0, 20, 7.0, {"role": "apron", "shapeID": "A3"})
    b.square(400, 0, 20, [0.0, 0.0, 0.5, 0.0],
             {"role": "apron", "shapeID": "A5"})
    b.square(450, 0, 20, [0.0, 0.0, 2.0, 0.0],
             {"role": "apron", "shapeID": "A6"})
    b.square(500, 0, 20, [0.0, 0.0, 2.0, 0.0],
             {"role": "apron", "shapeID": "A7"})
    sidecar = {
        "anchor": list(ANCHOR),
        "ruleset": "icao",
        "fan_ramp_zones": [
            {"ring_ll": b.rect_ring_ll(398, -2, 472, 22), "cap": 0.05},
            {"ring_ll": b.rect_ring_ll(460, -2, 510, 22), "cap": 0.05},
        ],
    }
    return b.write(tmp_path / "TWIN_auto.patch.osm", sidecar,
                   root_attrs=root_attrs)


@pytest.fixture(scope="module")
def report(cg, census, tmp_path_factory):
    """The census of the fixture, with every optional section on."""
    tmp = tmp_path_factory.mktemp("census_twin")
    osm = _build_fixture(cg, tmp)
    return census.census_one(osm, cg, want_bare=True, top=5,
                             want_zone_split=True)


def _fam(report: dict, key: str) -> dict:
    return next(f for f in report["families"] if f["family"] == key)


# ══════════════════════════════════════════════════════════════════════
# §1 THE LAW-TRUE COUNTS
# ══════════════════════════════════════════════════════════════════════

def test_the_per_family_counts_are_the_hand_computed_ones(report):
    """Every non-empty family, derived pair by pair.

    WITHIN_SHAPE = 14.  Allowance is ``cap·d + 0.03``: apron at 1 % allows
    0.23 m over a 20 m edge and 0.313 m over the 28.284 m diagonal;
    groundside pavement at the ROAD limit 8 % (owner ruling 2026-08-12,
    "GROUNDSIDE PAVEMENT GRADES AT THE ROAD LIMIT" — it carries the same
    vehicles the service road does) allows 1.63 m / 2.293 m; a declared
    fan-ramp piece and a pair wholly inside a declared 5 % zone allow
    1.03 m / 1.457 m.

      A1 (apron, one corner at 1.2): the three pairs touching that corner
         carry |de|=1.2 > 0.23 / 0.313      -> 3
      G1 (groundside, 0.1 / 0 / 2.0 / 0): b-c and c-d carry 2.0 > 1.63;
         the a-c diagonal's 1.9 is now UNDER the 2.293 allowance the
         road limit grants, so it is lawful; a-b, a-d (0.1) and b-d
         (0) pass                                                   -> 2
      A4 (declared ramp piece, corner 2.0, judged at the 5 % ramp cap):
         2.0 > 1.03 twice and 2.0 > 1.457 on the diagonal          -> 3
      A5 (corner 0.5, wholly inside zone Z1 -> 5 %): 0.5 < 1.03    -> 0
      A6 (corner 2.0, wholly inside Z1 -> 5 %): as A4              -> 3
      A7 (corner 2.0, only its western half inside Z2, so no pair is
         wholly covered and the strict 1 % apron cap stands)       -> 3
      A2/A3/B1/B2 lie flat                                         -> 0

    DRAINAGE_MINIMUM = 0, and the family is PRESENT-and-zero.  G1's a-b
    edge falls 0.1 m over 20 m = 0.5 %, which §B3's landside half read as
    a shortfall against its 1 % minimum until that half RETIRED (RULINGS
    2026-08-14: the family "retires only where it demanded curvature ON
    taxiway/road/groundside pavement surfaces").  The APRON half survives
    and is a no-op under this fixture's ICAO ruleset, so the family runs,
    walks the aprons, and reports nothing.  ``tests/test_harness.py``
    asserts the retired roles are absent from its walk — the difference
    between this zero and the 2026-08-13b blindness zero is a register
    entry, not a number.

    STACKED_NODES = 2.  A1 and G1 abut at x=20 with DISTINCT node ids at
    both shared corners: (20,0) holds 0.0 and 0.1, (20,20) holds 1.2 and
    0.0 — both past the 0.05 m tolerance.

    VERTEX_TO_EDGE_STEP = 8 raw.  Two shape pairs sit 0.6 m apart (inside
    the 1.0 m contact tolerance) with a 2.0 m height difference: each
    contributes its own two facing corners against the neighbour's edge,
    2 + 2 = 4.  B1|B2 gives 4, A2|A3 gives 4.

    MID_EDGE_STEP = 20 raw.  Five samples per edge, on both facing edges
    of both pairs: 2 x 5 x 2 = 20.
    """
    assert _fam(report, "within_shape")["n"] == 14
    assert _fam(report, "drainage_minimum")["n"] == 0
    assert _fam(report, "stacked_nodes")["n"] == 2
    # steps are reported AFTER the registered exemption (below)
    assert _fam(report, "vertex_to_edge_step")["n"] == 4
    assert _fam(report, "mid_edge_step")["n"] == 10
    # AIRSIDE_NO_STEP = 15, all of them the §1.2 RATE term (owner ruling
    # RULINGS 2026-08-27; this fixture's sidecar publishes no
    # ``airside_no_step_edges``, so the §1.1 direct-distance term has an
    # empty population here BY CONSTRUCTION).  Each apron square is walked
    # as a CYCLIC ring sequence a-b-c-d-a-b at 20 m stations, and the rate
    # allowance is ``arc_rate x 20 m`` = 0.0131 (FAA ±2 %/30.5 m, ICAO
    # provisional) against a reader blind spot of q(1/20 + 1/20).  A
    # square carrying ONE raised corner therefore breaches at three of its
    # four stations — (a,b,c), (b,c,d) and (c,d,a); the fourth, (d,a,b),
    # is flat on both sides:
    #    A1 (corner 1.2), A4 (2.0), A5 (0.5), A6 (2.0), A7 (2.0) -> 3 each
    #    A2 / A3 lie flat, and G1 / B1 / B2 are not airside     -> 0
    # 5 x 3 = 15.  A5's 0.5 m corner is priced here even though the 5 %
    # zone exempts its within-shape pairs: the ZONE relaxes the GRADE cap,
    # and the ruling's second bound is about CURVATURE, which no zone
    # declares away.
    assert _fam(report, "airside_no_step")["n"] == 15
    assert [f["family"] for f in report["families"] if f["n"]] == [
        "within_shape", "airside_no_step", "stacked_nodes",
        "vertex_to_edge_step", "mid_edge_step"]


def test_the_law_true_total_and_the_within_cross_steps_split(report):
    """14 + 15 + 2 within-bucket rows = 31 (the middle term is the
    AIRSIDE NO-STEP rate family, RULINGS 2026-08-27, derived station by
    station above); no cross-bucket row (the two abutting shapes share no
    vertex inside the 0.5 m proximity window that the law does not already
    exempt as a wall-separated pair); 28 raw step rows of which 14 hold a
    registered exemption, so 14 are counted.  TOTAL = 31 + 0 + 14 = 45."""
    lt = report["lawtrue"]
    assert lt["within"] == 31
    assert lt["cross"] == 0
    assert lt["steps_raw"] == 28
    assert lt["steps"] == 14
    assert lt["total"] == 45


def test_the_side_split_and_the_airside_is_king_accounting(report):
    """AIRSIDE 41 = 12 within-shape apron rows (A1 3, A4 3, A6 3, A7 3)
    + 15 airside no-step RATE rows (A1/A4/A5/A6/A7, 3 each)
    + 4 vertex-to-edge + 10 mid-edge apron steps.
    GROUNDSIDE 2 = G1's 2 within-shape rows (its drainage-minimum row
    left with the retired landside half of §B3).
    MIXED 2 = the two stacked-node rows, apron against groundside.

    ``airside_for_acceptance`` APPLIES the owner ruling the old report
    line only stated: a mixed row counts against airside, so 41 + 2 = 43.
    """
    lt = report["lawtrue"]
    assert (lt["airside"], lt["groundside"], lt["mixed"], lt["unknown"]) == (
        41, 2, 2, 0)
    assert lt["airside"] + lt["groundside"] + lt["mixed"] == lt["total"]
    assert lt["airside_for_acceptance"] == 43


def test_the_registered_step_exemption_is_named_and_counted(report):
    """B1|B2 are both buildings, so all 14 of their step rows (4 + 10)
    hold the ``building_to_building`` exemption; A2|A3 are both aprons and
    hold none."""
    assert report["lawtrue"]["steps_exempt_by_rule"] == {
        "building_to_building": 14}
    assert (report["lawtrue"]["steps_raw"]
            - report["lawtrue"]["steps"]) == 14


def test_the_worst_row_is_the_largest_magnitude_row(report):
    """Largest |de| in the fixture is 2.0 m — carried by G1's two 2.0 m
    within-shape pairs, A4/A6/A7's, and every step row."""
    assert report["worst"][0]["magnitude_m"] == pytest.approx(2.0)
    assert all(r["magnitude_m"] <= 2.0 + 1e-9 for r in report["worst"])


# ══════════════════════════════════════════════════════════════════════
# §2 THE ADJUDICATION SPLIT
# ══════════════════════════════════════════════════════════════════════

def test_the_adjudication_defers_exactly_the_registered_family(report, cg):
    """RULINGS d48bc0a: instruments report, the law adjudicates.  The one
    version-deferred family is ``drainage_minimum``, still REGISTERED and
    still reported under its own heading — but it now carries no row on
    this fixture (its landside half retired 2026-08-14, and its apron half
    is an ICAO no-op).  So ADJUDICATED = 45 - 0 = 45 and the verdict is
    FAIL (a PASS requires zero adjudicated rows).

    The deferral heading is printed with n=0 rather than dropped: a
    deferred family that vanishes from the report when it happens to find
    nothing is the census-wrapper defect in miniature."""
    adj = report["adjudication"]
    assert adj["ruling"] == cg.DEFERRED_ADJUDICATION_RULING
    assert adj["deferred_total"] == 0
    assert adj["deferred_families"]["drainage_minimum"]["n"] == 0
    assert adj["adjudicated_total"] == 45
    assert adj["adjudicated_by_side"] == {
        "airside": 41, "groundside": 2, "mixed": 2, "unknown": 0}
    assert adj["pass"] is False
    assert report["adjudicated_airside_for_acceptance"] == 43
    # the deferred rows are REPORTED, never dropped
    assert (adj["adjudicated_total"] + adj["deferred_total"]
            == report["lawtrue"]["total"])


def test_a_clean_patch_adjudicates_pass(cg, census, tmp_path):
    """The other side of the verdict: one flat apron, zero rows, PASS.
    A gate that can only ever say FAIL is not an instrument."""
    b = _PatchBuilder(cg)
    b.square_flat(0, 0, 20, 5.0, {"role": "apron", "shapeID": "F1"})
    osm = b.write(tmp_path / "clean.patch.osm",
                  {"anchor": list(ANCHOR), "ruleset": "icao"})
    rep = census.census_one(osm, cg, top=5)
    assert rep["lawtrue"]["total"] == 0
    assert rep["adjudication"]["pass"] is True
    assert rep["adjudication"]["adjudicated_total"] == 0


# ══════════════════════════════════════════════════════════════════════
# §3 THE BARE FRAME, AS A NUMBER
# ══════════════════════════════════════════════════════════════════════

def test_the_bare_minus_law_true_difference_is_the_two_frame_effects(
        report):
    """The report holds BOTH totals, so the gap between the frames is
    arithmetic, not an adjective.

    BARE runs with no sidecar law context at all and applies no registered
    step exemption:

      +3   A5's three pairs.  Law-true reads them at the declared zone's
           5 % cap (0.5 m < 1.03 m allowance); bare has no zones and reads
           them at the apron's 1 % (0.5 m > 0.23 / 0.313).
      +14  the building-to-building step rows the exemption removes.

    bare 62 - law-true 45 = +17.  (A4 keeps its relief in both frames: the
    ramp cap comes from the WAY's own ``o4_grade_law`` tag, which is on the
    patch, not in the sidecar.)
    """
    assert report["bare"]["within"] == 34     # 31 + A5's 3
    assert report["bare"]["cross"] == 0
    assert report["bare"]["steps"] == 28      # raw, no exemption
    assert report["bare"]["total"] == 62
    assert report["bare"]["total"] - report["lawtrue"]["total"] == 17


# ══════════════════════════════════════════════════════════════════════
# §4 THE FRAME STAMPS (RULINGS 2026-08-06, binding point 3)
# ══════════════════════════════════════════════════════════════════════

def test_an_unstamped_patch_reports_null_provenance_and_a_reason(report):
    """Never a crash, never a silently absent key: an explicit null plus
    the verified reason."""
    assert report["provenance"] is None
    assert report["provenance_reason"] == (
        "no o4_provenance_* attributes on the <osm> root")


def test_a_stamped_patch_carries_the_build_frame_into_the_report(
        cg, census, tmp_path):
    """The stamp is rendered by the EMITTER's own renderer
    (``auto_patch.provenance.provenance_tags``) and decoded by its own
    reader, so this is an emitter/reader lockstep, not a hand-written
    string this test agrees with itself about."""
    from auto_patch.provenance import provenance_tags
    tags = provenance_tags({
        "git": {"sha": "0123456789abcdef", "dirty": True},
        "gates": {"on": ["GATE_A"], "nondefault": [("GATE_A", "1")],
                  "total": 7},
        "dem": {"raw": False},
        "built": "2026-08-06T12:00:00",
        "icao": "TEST",
    })
    attrs = "".join(f" {k}='{v}'" for k, v in tags.items())
    osm = _build_fixture(cg, tmp_path, root_attrs=attrs)
    rep = census.census_one(osm, cg, top=5)
    assert rep["provenance_reason"] is None
    prov = rep["provenance"]
    assert prov["sha"] == "0123456789abcdef"
    assert prov["dirty"] == "true"
    assert prov["gates_total"] == "7"
    assert prov["gates_nondefault"] == ["GATE_A=1"]
    assert prov["dem_raw"] is False
    assert prov["built"] == "2026-08-06T12:00:00"
    assert prov["icao"] == "TEST"
    # ...and the counts are untouched by the stamp
    assert rep["lawtrue"]["total"] == 45


def test_the_reported_knobs_are_the_knobs_the_law_true_run_binds(
        cg, census, tmp_path, monkeypatch):
    """A serialised frame that does not match the frame actually used is
    worse than no frame at all, so this captures what ``run_checks``
    receives rather than trusting the constant."""
    seen: dict = {}
    real = cg.run_checks

    def _spy(osm_path, **kw):
        seen.update(kw)
        return real(osm_path, **kw)

    monkeypatch.setattr(cg, "run_checks", _spy)
    osm = _build_fixture(cg, tmp_path)
    rep = census.census_one(osm, cg, top=0)
    for key, value in rep["law_true_knobs"].items():
        assert seen[key] == value, f"reported {key} is not the bound one"
    assert rep["law_true_knobs"] == {
        "max_grade_pct": 1.5, "proximity_m": 0.5,
        "edge_search_m": 5.0, "edge_step_m": 0.5}


def test_the_ruleset_is_reported_declared_and_active(report):
    assert report["ruleset_declared"] == "icao"
    assert report["ruleset_active"] == "icao"


def test_an_undeclared_ruleset_reports_none_declared_not_a_cause(
        cg, census, tmp_path, capsys):
    """A sidecar with no ``ruleset`` key.  The report may say what the
    sidecar declared (nothing), what the run judged in, and where that came
    from — and may NOT say why the key is missing or what to do about it."""
    b = _PatchBuilder(cg)
    b.square_flat(0, 0, 20, 5.0, {"role": "apron", "shapeID": "F1"})
    osm = b.write(tmp_path / "noruleset.patch.osm",
                  {"anchor": list(ANCHOR)})
    rep = census.census_one(osm, cg, top=0)
    assert rep["ruleset_declared"] is None
    assert rep["ruleset_active"] == "icao"
    census.print_report(rep, 0)
    out = capsys.readouterr().out
    assert "declared=None" in out and "source=DEFAULT" in out
    for banned in ("predates", "Rebuild", "rebuild"):
        assert banned not in out, (
            f"the ruleset line asserts {banned!r} — an unverified cause or "
            f"an instruction to the reader (RULINGS 2026-08-06 point 2)")


# ══════════════════════════════════════════════════════════════════════
# §5 THE PRINTER AND THE COMPUTER AGREE
# ══════════════════════════════════════════════════════════════════════

def test_print_report_prints_the_numbers_census_one_computed(
        report, census, capsys):
    """THE MISSING LINK.  ``census_one`` computes and ``print_report``
    prints, and nothing asserted the second showed the first.  Every field
    below is matched as the printed ``key=value``, so a printer reading the
    wrong dict key fails here."""
    census.print_report(report, 5)
    out = capsys.readouterr().out
    lt = report["lawtrue"]
    adj = report["adjudication"]
    for token in (
            f"LAW-TRUE TOTAL {lt['total']}",
            f"within={lt['within']}",
            f"cross={lt['cross']}",
            f"steps={lt['steps']}",
            f"(raw {lt['steps_raw']}",
            "building_to_building=14",
            f"airside={lt['airside']}",
            f"groundside={lt['groundside']}",
            f"mixed={lt['mixed']}",
            f"airside_for_acceptance={lt['airside_for_acceptance']}",
            f"ADJUDICATED {adj['adjudicated_total']}",
            f"VERSION-DEFERRED (reported, NOT adjudicated) "
            f"{adj['deferred_total']}",
            "verdict: FAIL",
            f"total={report['bare']['total']}",
            f"bare {report['bare']['total']} − law-true {lt['total']} = "
            f"{report['bare']['total'] - lt['total']:+d} rows",
            "max_grade_pct=1.5",
            "declared='icao'",
    ):
        assert token in out, f"print_report never printed {token!r}"


def test_print_report_prints_every_family_row_including_the_empty_ones(
        report, census, cg, capsys):
    census.print_report(report, 5)
    out = capsys.readouterr().out
    for key, _title, _bucket in cg.LAW_FAMILIES:
        assert key in out, f"family {key} absent from the printed table"
    for f in report["families"]:
        if f["n"]:
            assert f"{f['family']:<24}{f['n']:>7}" in out


def test_the_printed_report_carries_no_verdict_sentence(report, census,
                                                        capsys):
    """The sweep's own regression guard.  A verdict may be printed by the
    law layer (``verdict: PASS/FAIL``, from ``check_grade.adjudication``)
    or when it is a world-invariant computation; these phrases were
    neither — each asserted a CAUSE the code never checks, instructed the
    reader, or labelled a number with an adjective in place of the second
    number that would have measured it."""
    census.print_report(report, 5)
    out = capsys.readouterr().out
    for banned in (
            "predates the FAA/ICAO split",
            "Rebuild for a law-true judgment",
            "OVERCOUNTS",
            "the emitter grew a field",
            "zones OVERLAP, one per adjacent building pair",
            "the number that says whether the law is INERT",
            "no ramp cap rescues these",
            "mixed counts AGAINST airside",
    ):
        assert banned not in out, (
            f"verdict sentence back in the report: {banned!r}")


# ══════════════════════════════════════════════════════════════════════
# §6 print_compare's ARITHMETIC
# ══════════════════════════════════════════════════════════════════════

def _stub_report(patch: str, within_n: int, steps_n: int, total: int,
                 adjudicated: int, deferred: int) -> dict:
    return {
        "patch": patch,
        "families": [{"family": "within_shape", "n": within_n},
                     {"family": "cross_shape", "n": 0},
                     {"family": "mid_edge_step", "n": steps_n}],
        "lawtrue": {"total": total},
        "adjudication": {"adjudicated_total": adjudicated,
                         "deferred_total": deferred},
    }


def test_print_compare_deltas_are_last_minus_first(census, capsys):
    """A/B arithmetic, hand-computed: within 100 -> 60 is -40, mid-edge
    7 -> 12 is +5, TOTAL 107 -> 72 is -35, ADJUDICATED 100 -> 70 is -30,
    deferred 7 -> 2 is -5.  A family that is zero in BOTH reports is not
    printed at all."""
    census.print_compare([
        _stub_report("/x/ARM_A.patch.osm", 100, 7, 107, 100, 7),
        _stub_report("/x/ARM_B.patch.osm", 60, 12, 72, 70, 2),
    ])
    out = capsys.readouterr().out
    assert "-40" in out and "+5" in out
    assert "-35" in out and "-30" in out and "-5" in out
    assert "cross_shape" not in out, (
        "a family empty in every arm must not take a row in the A/B table")
    for line, cells in (("within_shape", ("100", "60")),
                        ("mid_edge_step", ("7", "12")),
                        ("TOTAL", ("107", "72"))):
        row = next(r for r in out.splitlines() if r.strip().startswith(line))
        for cell in cells:
            assert cell in row


def test_print_compare_is_a_no_op_below_two_reports(census, capsys):
    census.print_compare([_stub_report("/x/only.osm", 1, 1, 2, 2, 0)])
    assert capsys.readouterr().out == ""


# ══════════════════════════════════════════════════════════════════════
# §7 zone_split
# ══════════════════════════════════════════════════════════════════════

def test_zone_split_buckets_the_within_shape_rows(report):
    """The four buckets over the 15 within-shape rows.

      ramp_piece 3  A4's rows: its way carries ``o4_grade_law=fan_ramp``,
                    so the LAW is already judging them at the zone cap.
      in_zone    3  A6's rows: A6 lies wholly inside Z1, so every chord is
                    covered.  (A5 also lies inside Z1 but produces no rows
                    — the relief is why.)
      crosses    2  A7's diagonal (500,0)-(520,20) and its northern edge
                    (520,20)-(500,20) both straddle Z2's x=510 boundary.
      outside    7  A1's 3, G1's 3, and A7's eastern edge (520,0)-(520,20),
                    which is 10 m clear of Z2.
    """
    zs = report["zone_split"]
    assert zs["within_rows"] == 14
    assert zs["buckets"] == {"ramp_piece": 3, "in_zone": 3,
                             "crosses": 2, "outside": 6}
    assert sum(zs["buckets"].values()) == zs["within_rows"]


def test_zone_split_areas_and_the_overlap_number(report):
    """Z1 is 74 x 24 = 1776 m², Z2 is 50 x 24 = 1200 m², parts sum 2976
    m².  They share [460,472]x[-2,22] = 12 x 24 = 288 m², so the union is
    2688 m².  The report used to assert a CAUSE for parts > union; it now
    reports the difference."""
    zs = report["zone_split"]
    assert zs["zones"] == 2
    assert zs["zone_parts_area_m2"] == pytest.approx(2976.0, abs=0.5)
    assert zs["zone_area_m2"] == pytest.approx(2688.0, abs=0.5)
    assert zs["zone_overlap_m2"] == pytest.approx(288.0, abs=1.0)
    assert (zs["zone_overlap_m2"]
            == pytest.approx(zs["zone_parts_area_m2"] - zs["zone_area_m2"],
                             abs=0.05))


def test_zone_split_counts_the_ramp_pieces_and_stamps_their_frame(report):
    """One declared ramp way with a 4-vertex ring (the closing repeat is
    dropped), binding all 6 vertex pairs of a convex 4-gon under the shape
    law.  The pair count is taken in a CONTEXT-FREE ``GradeContext`` while
    the rows above come from the sidecar's real axes/routes — two frames in
    one report, so the frame is stamped rather than left to be inferred."""
    zs = report["zone_split"]
    assert zs["ramp_ways"] == 1
    assert zs["ramp_vertices"] == 4
    assert zs["ramp_law_pairs"] == 6
    assert zs["ramp_law_pairs_frame"] == (
        "context-free GradeContext(centerlines=[], routes=[])")


def test_zone_split_reports_the_cap_bound_its_count_was_taken_at(report):
    """``steeper_than_zone_cap`` is only meaningful with the bound: it is
    14 of the 15 rows at the 5 % maximum THIS sidecar declares.  The one
    row under it is A1's diagonal — 1.2 m over 28.284 m = 4.24 %; every
    other row is 6 % or steeper."""
    zs = report["zone_split"]
    assert zs["caps"] == [0.05]
    assert zs["steeper_than_zone_cap_bound"] == 0.05
    assert zs["steeper_than_zone_cap"] == 13
    assert zs["top_role_pairs"] == {
        "apron|apron": 12, "groundside_pavement|groundside_pavement": 2}


def test_zone_split_prints_its_frame_and_bound(report, census, capsys):
    census.print_report(report, 5)
    out = capsys.readouterr().out
    assert "context-free GradeContext" in out
    assert "NOT the census's law-true frame" in out
    assert "overlap" in out and "288" in out
    assert "rows steeper than 5%" in out


def test_zone_split_declines_with_a_reason_when_it_cannot_measure(
        cg, census, tmp_path):
    """No anchor in the sidecar means no metre frame, and the section says
    so rather than guessing one."""
    b = _PatchBuilder(cg)
    b.square_flat(0, 0, 20, 5.0, {"role": "apron", "shapeID": "F1"})
    osm = b.write(tmp_path / "noanchor.patch.osm", {"ruleset": "icao"})
    assert census.zone_split(osm, cg, {}) == {
        "reason": "sidecar carries no anchor — no metre frame"}


# ══════════════════════════════════════════════════════════════════════
# §8 THE STEP EXEMPTION IS ONE AUTHORITY (the census-wrapper defect class)
# ══════════════════════════════════════════════════════════════════════

def test_step_exempt_matches_both_hand_written_copies_it_replaced(
        cg, census, tmp_path):
    """``_both_buildings`` existed VERBATIM in ``tools/harness/census.py``
    and in ``tests/test_pavement_grade.py``: one law, two copies, nothing
    asserting they agree.  Both copies are reproduced here and asserted
    row-for-row against the registered authority on the fixture's whole
    step population, so the move is provably behaviour-neutral."""
    def census_copy(step):        # the census's, verbatim
        return (step.way_v.tags.get("role") == "building"
                and step.way_e.tags.get("role") == "building")

    def gate_copy(s):             # test_pavement_grade's, verbatim
        return (s.way_v.tags.get("role") == "building"
                and s.way_e.tags.get("role") == "building")

    osm = _build_fixture(cg, tmp_path)
    _w, _c, steps = cg.run_checks_law_true(osm, quiet=True, top_n=0)
    assert len(steps) == 28, "the fixture must exercise both sides"
    for s in steps:
        assert bool(cg.step_exempt(s)) is census_copy(s) is gate_copy(s)
    assert sum(1 for s in steps if cg.step_exempt(s)) == 14


def test_the_exemption_names_the_rule_it_applied(cg, census, tmp_path):
    osm = _build_fixture(cg, tmp_path)
    _w, _c, steps = cg.run_checks_law_true(osm, quiet=True, top_n=0)
    names = {cg.step_exempt(s) for s in steps}
    assert names == {None, "building_to_building"}
    assert "building_to_building" in cg.STEP_EXEMPTIONS


def test_the_exemption_register_covers_the_step_bucket(cg):
    assert set(cg.STEP_EXEMPT_FAMILIES) == {
        key for key, _t, bucket in cg.LAW_FAMILIES if bucket == "steps"}


def test_step_exempt_is_total_where_the_copies_were_partial(cg):
    """A row with no ways raised ``AttributeError`` in both copies.  The
    registered authority answers None.  Every ``EdgeStep`` ``run_checks``
    emits carries both ways, so this is a superset, not a behaviour
    change — the row-for-row twin above is what pins that."""
    class _Bare:
        pass
    assert cg.step_exempt(_Bare()) is None


def test_no_reader_redefines_the_exemption_locally(census):
    """The regression guard for the defect class itself."""
    import inspect
    src = Path(inspect.getfile(census)).read_text()
    assert "_both_buildings" not in src, (
        "the census re-grew a private copy of a law exemption; call "
        "check_grade.step_exempt")
    assert "step_exempt" in src


# ══════════════════════════════════════════════════════════════════════
# §9 THE SPINE-CURVATURE READER IS REPORTER-ONLY
# ══════════════════════════════════════════════════════════════════════

class TestSpineCurvatureIsReporterOnly:
    """``_check_spine_curvature`` produces a law-SHAPED count that is not a
    law family: not in ``LAW_FAMILIES``, never in ``family_out``, never
    adjudicated, printed only when ``not quiet``.  Printed unlabelled it
    read exactly like a defect count, which under RULINGS 2026-08-06 point
    1 is an untwinned instrument.  Here is the twin, and the label."""

    def _profile_ways(self, cg):
        """Four collinear vertices, 20 m apart, elevations 0 / 0 / 0.4 /
        0.8 — one grade CHANGE of 0.02 at the third vertex, then none."""
        nodes = {str(-i - 1): (0.0, 0.0) for i in range(4)}
        way = cg.Way(wid="-100", role="apron", ref="", aeroway="",
                     nids=["-1", "-2", "-3", "-4", "-1"],
                     elevs=[0.0, 0.0, 0.4, 0.8, 0.0],
                     tags={"role": "apron"})
        xs = [0.0, 20.0, 40.0, 60.0]

        def ll_to_m(lat, lon):
            return (xs[int(lat)], 0.0)

        nodes = {str(-(i + 1)): (float(i), 0.0) for i in range(4)}
        return [way], nodes, ll_to_m

    def test_the_kink_count_and_worst_excess_are_the_hand_computed_ones(
            self, cg):
        """Allowance at l1 = l2 = 20 m is
        ``k·(l1+l2)/2 + 0.03·(1/l1 + 1/l2)`` = 0.0003333·20 + 0.003 =
        0.0096667.  The one interior vertex with a grade change has
        |g2 - g1| = 0.4/20 - 0 = 0.02, so excess = 0.0103333 and the
        reported rate is excess / 20 = 0.00051667 per metre.  The next
        interior vertex has g1 = g2 = 0.02 and is not a kink."""
        from auto_patch.config import TAXIWAY_MAX_GRADE_CHANGE_PER_M as k
        ways, nodes, ll_to_m = self._profile_ways(cg)
        axis = [([(0.0, 0.0), (60.0, 0.0)], 0.015, 0.015)]
        n_kinks, worst = cg._check_spine_curvature(ways, nodes, ll_to_m,
                                                   axis)
        allowance = k * 0.5 * 40.0 + 0.03 * (1 / 20.0 + 1 / 20.0)
        assert allowance == pytest.approx(0.0096667, abs=1e-6)
        assert n_kinks == 1
        assert worst == pytest.approx((0.02 - allowance) / 20.0, rel=1e-9)

    def test_a_straight_profile_reports_no_kink(self, cg):
        ways, nodes, ll_to_m = self._profile_ways(cg)
        ways[0].elevs = [0.0, 0.2, 0.4, 0.6, 0.0]   # constant 1 % grade
        n_kinks, worst = cg._check_spine_curvature(
            ways, nodes, ll_to_m, [([(0.0, 0.0), (60.0, 0.0)], 0.015, 0.015)])
        assert (n_kinks, worst) == (0, 0.0)

    def test_it_is_not_a_law_family_and_never_reaches_the_census(
            self, cg, report):
        assert "spine_curvature" not in {k for k, _t, _b in cg.LAW_FAMILIES}
        assert not any("curv" in k for k, _t, _b in cg.LAW_FAMILIES)
        assert not any("curv" in f["family"] for f in report["families"])
        # nothing in the census's counted population comes from it
        assert sum(f["n"] for f in report["families"]) == (
            report["lawtrue"]["total"])

    def test_the_printed_line_says_it_is_not_a_defect_count(
            self, cg, tmp_path, capsys):
        """A reader who sees the number must be told what it is not."""
        b = _PatchBuilder(cg)
        # a 0.4 m-wide strip along the axis so every vertex projects onto
        # it inside the reader's 0.6 m capture radius
        ns = [b.node(0, -0.2, 0.0), b.node(20, -0.2, 0.0),
              b.node(40, -0.2, 0.4), b.node(60, -0.2, 0.8),
              b.node(60, 0.2, 0.8), b.node(40, 0.2, 0.4),
              b.node(20, 0.2, 0.0), b.node(0, 0.2, 0.0)]
        b.way(ns + [ns[0]], {"role": "apron", "shapeID": "S1"})
        axis_ll = [[list(b.ll(0, 0)), list(b.ll(60, 0))]]
        osm = b.write(tmp_path / "spine.patch.osm", {
            "anchor": list(ANCHOR), "ruleset": "icao",
            "axes": [[axis_ll[0], 0.015, 0.015]]})
        fam: dict = {}
        cg.run_checks_law_true(osm, family_out=fam, quiet=False, top_n=0)
        out = capsys.readouterr().out
        assert "SPINE PROFILE grade-change" in out
        assert "[reporter-only, not a law family, not censused]" in out
        assert "spine" not in {k for k in fam if not k.startswith("_")}

    def test_the_quiet_census_path_never_prints_it_at_all(
            self, cg, census, tmp_path, capsys):
        osm = _build_fixture(cg, tmp_path)
        census.census_one(osm, cg, top=0)
        assert "SPINE PROFILE" not in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════
# BAND MEMBERSHIP — zero-of-zero is the ABSENCE of a measurement
#
# The cycle-7.5 sweep's headline find, measured live on HEAZ: the build
# logged ``[reach-band] no field could be built`` and, in the SAME run,
# the band-membership instruments rendered a clean universal pass.  The
# mechanism is in ``route_band_violations``' own contract — a vertex
# whose band reads ``None`` is NOT constrained — so a band field that
# fails to build yields zero rows, and zero rows used to print as
# "0 vertex(es) outside their band".
#
# The build's report now publishes the EXAMINED denominator.  These twins
# lock the census side: with ``examined == 0`` the census must say NOT
# MEASURED and must NOT emit a membership count.
# ══════════════════════════════════════════════════════════════════════

def _report_with_band(report: dict, band: dict | None) -> dict:
    """``report`` with ``evidence.band_excess`` replaced (deep enough copy)."""
    out = dict(report)
    ev = dict(out.get("evidence") or {})
    if band is None:
        ev.pop("band_excess", None)
    else:
        ev["band_excess"] = band
    out["evidence"] = ev
    return out


def test_a_band_that_examined_nothing_is_reported_NOT_MEASURED(
        report, census, capsys):
    """KNOWN ANSWER: 0 examined of 4072 candidates, 2485 off-net, 1587
    welded duplicates (the shape HEAZ actually produces).  The census must
    print NOT MEASURED and name the denominator, and must NOT print the
    membership sentence — a build with no band field is not a clean one."""
    census.print_report(_report_with_band(report, {
        "material": 0, "materiality_m": 0.01, "worst_m": 0.0,
        "by_side": {"ceil": 0, "floor": 0, "pinned": 0},
        "examined": 0, "candidates": 4072, "off_net": 2485, "deduped": 1587,
    }), 0)
    out = capsys.readouterr().out
    assert "band membership: NOT MEASURED this build" in out
    assert "ZERO of 4072 candidate vertex(es) were examined" in out
    assert "2485 off-net" in out and "1587 welded duplicate(s)" in out
    assert "not a clean surface" in out
    # The membership sentence — the thing that used to lie — must be absent.
    assert "outside their band by >" not in out
    assert "vertex(es) outside their band" not in out


def test_a_measured_band_reports_its_examined_denominator(
        report, census, capsys):
    """KNOWN ANSWER: 3 material rows of 1200 examined.  The count is only
    meaningful beside the population it was taken over, so the denominator
    is part of the sentence, not a separate line."""
    census.print_report(_report_with_band(report, {
        "material": 3, "materiality_m": 0.01, "worst_m": 0.29,
        "by_side": {"ceil": 2, "floor": 1, "pinned": 0},
        "examined": 1200, "candidates": 4072, "off_net": 2800, "deduped": 72,
    }), 0)
    out = capsys.readouterr().out
    assert "3 of 1200 EXAMINED vertex(es) outside their band by > 0.01 m" in out
    assert "ceil=2 floor=1 pinned=0" in out
    assert "NOT MEASURED" not in out


def test_a_build_predating_the_denominator_says_so_rather_than_implying_zero(
        report, census, capsys):
    """A patch built before the EXAMINED denominator existed carries no
    ``examined`` key.  That is NOT the zero case and must not be rendered
    as one — but it also cannot be trusted as a clean read, so the line
    says which build frame it is in."""
    census.print_report(_report_with_band(report, {
        "material": 0, "materiality_m": 0.01, "worst_m": 0.0,
        "by_side": {"ceil": 0, "floor": 0, "pinned": 0},
    }), 0)
    out = capsys.readouterr().out
    assert "predates the EXAMINED denominator" in out
    assert "ZERO of" not in out


def test_a_structurally_zero_sub_materiality_split_says_so(
        report, census, capsys):
    """``ELEV_ROUNDING_NOISE_M`` (0.03) exceeds the materiality floor
    (0.01), so no row the checker returns can land under the floor: the
    split is zero by construction and is not evidence about the surface.
    The census must carry that statement, not just the number."""
    census.print_report(_report_with_band(report, {
        "material": 1, "materiality_m": 0.01, "worst_m": 0.5,
        "by_side": {"ceil": 1, "floor": 0, "pinned": 0},
        "examined": 10, "candidates": 10, "off_net": 0, "deduped": 0,
        "noise_floor_m": 0.03, "sub_materiality_structurally_zero": True,
    }), 0)
    out = capsys.readouterr().out
    assert "sub-materiality split is STRUCTURALLY ZERO" in out
    assert "not evidence about the surface" in out


def test_the_band_error_case_still_names_the_error(report, census, capsys):
    """Unchanged behaviour, re-pinned: a reader that RAISED is a third
    state, distinct from both "measured" and "examined nothing"."""
    census.print_report(_report_with_band(
        report, {"error": "RuntimeError('band reader blew up')"}), 0)
    out = capsys.readouterr().out
    assert "band membership: NOT MEASURED this build" in out
    assert "band reader blew up" in out


# ══════════════════════════════════════════════════════════════════════
# §10 THE ROAD FAMILY IS IN THE CENSUS'S DOMAIN (S7, the S3 verdict)
# ══════════════════════════════════════════════════════════════════════
# RULINGS 2026-08-13b, "OTHH −639 ADJUDICATED: CENSUS BLINDNESS": the
# corridor round re-roled ~15.5 km of landside pavement perimeter out of
# ``groundside_pavement`` and into ``service_junction`` / ``service_road``,
# and the drainage-minimum walk named only the old role — so 15.5 km of
# emitted surface left the census without a line of output saying so.  The
# structural sweep lives in ``tests/test_harness.py`` (no role set may read
# ``groundside_pavement`` without the roles it is re-roled into); this is
# the MEASURED half: a patch made only of road-family surfaces, censused,
# with every reported row derived.
#
# THE ROAD FIXTURE (metres, same anchor and 20 m squares as §1):
#
#   R1  service_junction  [0, 20]²          corner alts (0.1, 0, 2.0, 0)
#   R2  service_road      [100,120]×[0,20]  flat 5.0
#   R3  service_junction  [120.6,140.6]×[0,20]  flat 7.0
#
# ``config.ROLE_GRADE_LIMITS`` gives both road roles the SAME cap
# (``SERVICE_ROAD_MAX_GRADE``), so every allowance below is that cap.


@pytest.fixture(scope="module")
def road_report(cg, census, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("census_twin_roads")
    b = _PatchBuilder(cg)
    b.square(0, 0, 20, [0.1, 0.0, 2.0, 0.0],
             {"role": "service_junction", "shapeID": "R1"})
    b.square_flat(100, 0, 20, 5.0, {"role": "service_road", "shapeID": "R2"})
    b.square_flat(120.6, 0, 20, 7.0,
                  {"role": "service_junction", "shapeID": "R3"})
    osm = b.write(tmp / "ROADS_auto.patch.osm",
                  {"anchor": list(ANCHOR), "ruleset": "icao"})
    return census.census_one(osm, cg, want_bare=True, top=3)


def test_the_road_family_is_SEEN_by_the_within_shape_law(road_report):
    """WITHIN_SHAPE + ROAD_CROSS_SECTION = 2.  R1's longitudinal cap is
    the service-road limit (8 %), so a 20 m edge allows 8 %·20 + 0.03 =
    1.63 m and the 28.284 m diagonal allows 2.29 m.  Its 2.0 m corner
    breaches both edges that touch it (b-c, c-d) and neither diagonal
    (a-c carries 1.9 m, b-d carries 0).  R2 and R3 lie flat.

    THE SPLIT (owner ruling RULINGS 2026-08-25g, "ROADS ARE LATERALLY
    FLAT"): R1's two breaching edges are perpendicular to each other, so
    whichever way its ring axis falls, exactly ONE of them runs ALONG the
    ring and one runs ACROSS it — the across one is the road's
    CROSS-SECTION and is priced at the road's transverse limit in its own
    family.  The pair COUNT is what this twin is about (the domain: these
    are the roles the corridor round created, and they are read), and the
    count is unchanged — the ruling re-prices rows, it does not mint or
    drop them."""
    assert (_fam(road_report, "within_shape")["n"]
            + _fam(road_report, "road_cross_section")["n"]) == 2
    # ...and it really is one of each, not two of one: the cross-section
    # is a PARTITION of the ring's pairs by angle.
    assert _fam(road_report, "road_cross_section")["n"] == 1


def test_the_road_family_is_SEEN_by_the_step_laws(road_report):
    """R2|R3 sit 0.6 m apart (inside the 1.0 m contact tolerance) with a
    2.0 m height difference, and neither holds a registered exemption
    (``building_to_building`` is the only one).  VERTEX_TO_EDGE = 4 (two
    facing corners each way); MID_EDGE = 10 (five samples on each of the
    two facing edges)."""
    assert _fam(road_report, "vertex_to_edge_step")["n"] == 4
    assert _fam(road_report, "mid_edge_step")["n"] == 10
    assert road_report["lawtrue"]["steps_exempt_by_rule"] == {}


def test_every_road_row_is_reported_GROUNDSIDE(road_report):
    """``layout.GROUNDSIDE_ROLES`` is the one partition — the same set the
    solve's receiver split reads.  A road row that came back airside would
    mean the census and the solver disagree about which side the corridor
    round's new surfaces are on."""
    lt = road_report["lawtrue"]
    assert (lt["airside"], lt["mixed"], lt["unknown"]) == (0, 0, 0)
    assert lt["groundside"] == lt["total"]


# ══════════════════════════════════════════════════════════════════════
# §11 §B3's LANDSIDE HALF IS RETIRED — ZERO BY LAW, NOT BY BLINDNESS
# ══════════════════════════════════════════════════════════════════════
# RULINGS 2026-08-14, "DRAINAGE RULING SCOPE CLARIFIED": what retires is
# "ADDING drainage curvature (crown / minimum-slope requirements) to
# TAXIWAY and ROAD pavement surfaces; those may be flat for the sim …
# the drainage_minimum census family retires only where it demanded
# curvature ON taxiway/road/groundside pavement surfaces."
#
# NOT retired, and measured here as well as in the law twins: the APRON
# half (FAA §5.9.1.1), the drainage SPINE in enclosed areas, the drainage
# slope on ADJACENT GROUND, and the runway crown.
#
# These twins exist because the two zeros are indistinguishable in the
# output.  One week ago this family read zero on landside pavement
# because its walk had gone blind (the 2026-08-13b verdict, 11,932 rows
# across the five baseline airports); it reads zero there now because the
# owner withdrew the law.  Only a test that pins WHICH surfaces are
# walked can tell the round which zero it is holding.


def test_a_FLAT_landside_patch_censuses_no_drainage_row(cg, census,
                                                        tmp_path):
    """Three dead-flat landside surfaces, one per emitted groundside
    pavement role, under the FAA ruleset — the strictest frame, since the
    landside minimum was region-invariant and would have bound under
    both.  §B3 read nine rows here (three consecutive ring pairs per 20 m
    square, every one 0 % against a 1 % minimum).  Zero now."""
    b = _PatchBuilder(cg)
    b.square_flat(0, 0, 20, 3.0, {"role": "groundside_pavement",
                                  "shapeID": "F1"})
    b.square_flat(60, 0, 20, 3.0, {"role": "service_road", "shapeID": "F2"})
    b.square_flat(120, 0, 20, 3.0, {"role": "service_junction",
                                    "shapeID": "F3"})
    osm = b.write(tmp_path / "flat.patch.osm",
                  {"anchor": list(ANCHOR), "ruleset": "faa"})
    rep = census.census_one(osm, cg, top=5)
    assert _fam(rep, "drainage_minimum")["n"] == 0
    assert rep["lawtrue"]["total"] == 0
    assert rep["adjudication"]["pass"] is True


def test_a_FLAT_APRON_still_FAILS_under_the_FAA_ruleset(cg, census,
                                                        tmp_path):
    """The half that did NOT retire, and the twin that keeps the
    retirement honest: if this ever reads zero, the census has lost the
    apron half too and the "flat landside" zero above stops meaning
    anything.

    FAA §5.9.1.1 mandates a minimum 0.5 % apron gradient; the walk reads
    three consecutive ring pairs on a 20 m square, so a dead-flat apron
    is 3 rows, each a 0.5 % shortfall.  ICAO states no number, so the same
    apron is lawful there — jurisdictional fidelity, unchanged."""
    b = _PatchBuilder(cg)
    b.square_flat(0, 0, 20, 3.0, {"role": "apron", "shapeID": "P1"})
    faa = b.write(tmp_path / "apron_faa.patch.osm",
                  {"anchor": list(ANCHOR), "ruleset": "faa"})
    rep = census.census_one(faa, cg, top=5)
    assert _fam(rep, "drainage_minimum")["n"] == 3
    assert rep["lawtrue"]["groundside"] == 0      # an apron is airside
    assert rep["adjudication"]["deferred_total"] == 3, (
        "the apron rows must stay VERSION-DEFERRED (RULINGS d48bc0a) — "
        "the 2026-08-14 retirement withdrew a law, it did not adjudicate "
        "the half that survived")

    b2 = _PatchBuilder(cg)
    b2.square_flat(0, 0, 20, 3.0, {"role": "apron", "shapeID": "P1"})
    icao = b2.write(tmp_path / "apron_icao.patch.osm",
                    {"anchor": list(ANCHOR), "ruleset": "icao"})
    assert _fam(census.census_one(icao, cg, top=5),
                "drainage_minimum")["n"] == 0


def test_the_road_fixtures_drainage_rows_are_GONE_by_LAW(road_report, cg):
    """The §10 road fixture's four drainage rows — the ones the domain
    restoration made visible one commit earlier — are gone with the
    landside half.  Its WITHIN-SHAPE rows are untouched: the restored
    domain still stands in every other family, and what changed is which
    laws judge it.

    The register is the record of which zero this is."""
    assert _fam(road_report, "drainage_minimum")["n"] == 0
    # The within-shape PAIR POPULATION is untouched; RULINGS 2026-08-25g
    # splits it between two families by angle (see
    # ``test_the_road_family_is_SEEN_by_the_within_shape_law``), which is
    # a re-pricing, not a domain change — and the domain is what this
    # twin is the record of.
    assert (_fam(road_report, "within_shape")["n"]
            + _fam(road_report, "road_cross_section")["n"]) == 2
    entry = cg.RETIRED_LAWS["drainage_minimum::groundside"]
    assert not (set(entry["roles"]) & set(cg._DRAINAGE_MIN_ROLES))


def test_the_laws_the_clarification_KEPT_are_still_census_families(cg):
    """The 2026-08-14 clarification names three laws that do NOT retire,
    and ALL THREE are now census families.

    THE OPEN ITEM THIS TWIN CARRIED IS CLOSED (S8, ruled 2026-08-14).
    S7 wrote it as an honest gap: a runway emitted dead flat against a
    declared 0.30 m crown drop censused ZERO rows, because the
    within-shape crown check re-centres each pair on the DESIGNED crown
    and then judges the residue against the runway's own transverse CAP
    — and a 1 % crown sits inside a 1.5 % cap by construction — so the
    minimum was bound only where it is GENERATED
    (``tests/test_crown_minimum_bound.py``).  That file now carries the
    validator half too: ``check_grade._check_runway_crown`` reads the
    per-node DECLARED drop from the axes sidecar (``crown_drops``, the
    same field the solver built to) against the realised fall from the
    ``crown_spine`` ridge breakline.
    """
    registered = {k for k, _t, _b in cg.LAW_FAMILIES}
    assert "drainage_spine" in registered      # enclosed-area water escape
    assert "adjacent_ground_tear" in registered   # adjacent-ground slope
    assert "strip_seam_tear" in registered
    assert "runway_crown" in registered, (
        "the runway crown is one of the three laws the clarification KEPT "
        "— a kept law with no census family is a law we cannot see")
    # …and it is a READER, not a registration: the reader exists and the
    # cited intersection exception is registered with it.
    assert callable(getattr(cg, "_check_runway_crown", None))
    assert cg._CROWN_OUT_OF_SCOPE in cg.OUT_OF_SCOPE_CLASSES
