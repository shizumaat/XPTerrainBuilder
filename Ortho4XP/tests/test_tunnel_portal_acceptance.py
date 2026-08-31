"""THE TWIN for ``tools/tunnel_portal_acceptance.py``.

Promoted 2026-08-07 under RULINGS ``7e90032`` (promote-on-second-use) and
spec ``docs/specs/tunnel-fork-sustain-spec.md`` §3.  The rules a promoted
measurement tool has to keep, each one bought by a defect in this repo:

* the CLI is a FORMATTER over the library entry — one code path, so a
  number quoted from a script and a number quoted from the terminal can
  never disagree (the census-wrapper precedent, ``tools/INDEX.md``);
* every ROW COUNT comes from ``tools/harness/census.py`` /
  ``check_grade`` — a private re-count is the census-wrapper defect
  itself;
* the patch is read through ``check_grade._parse_osm``, not a second
  parser;
* the identity join is DETERMINISTIC — a join that depends on set
  iteration order read 8 and 9 on the same bytes;
* the tool is reachable from ``tools/INDEX.md`` (a tool absent from the
  index is treated as absent).
"""
from __future__ import annotations

import importlib.util
import dataclasses
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "tunnel_portal_acceptance.py"
sys.path.insert(0, str(ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tpa():
    return _load("tpa_under_test", TOOL_PATH)


# ──────────────────────────────────────────────────────────────────
# A minimal emitted patch + its sidecar (the law frame refuses without
# one — memory ``check-grade-needs-law-true-frame``).
# ──────────────────────────────────────────────────────────────────
def _patch_text(alt: float, ramp_alt: float = -2.0) -> str:
    def node(i, lat, lon, a):
        return (f"<node id='-{i}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                f"<tag k='alt_abs' v='{a}'/></node>")
    parts = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    # an apron square
    coords = [(25.0000, 51.0000), (25.0000, 51.0004),
              (25.0003, 51.0004), (25.0003, 51.0000)]
    for i, (la, lo) in enumerate(coords, start=1):
        parts.append(node(i, la, lo, alt))
    parts.append("<way id='-101'><nd ref='-1'/><nd ref='-2'/><nd ref='-3'/>"
                 "<nd ref='-4'/><nd ref='-1'/>"
                 "<tag k='aeroway' v='apron'/><tag k='role' v='apron'/>"
                 "<tag k='shapeID' v='1'/></way>")
    # a tunnel ramp beside it
    rcoords = [(25.0010, 51.0000), (25.0010, 51.0002),
               (25.0013, 51.0002), (25.0013, 51.0000)]
    for i, (la, lo) in enumerate(rcoords, start=11):
        parts.append(node(i, la, lo, ramp_alt))
    parts.append("<way id='-102'><nd ref='-11'/><nd ref='-12'/>"
                 "<nd ref='-13'/><nd ref='-14'/><nd ref='-11'/>"
                 "<tag k='aeroway' v='taxiway'/>"
                 "<tag k='role' v='tunnel_ramp'/>"
                 "<tag k='ref' v='tunnel_ramp'/>"
                 "<tag k='shapeID' v='2'/></way>")
    parts.append("</osm>")
    return "\n".join(parts)


def _write_patch(directory: Path, name: str, alt: float,
                 ramp_alt: float = -2.0) -> Path:
    osm = directory / name
    osm.write_text(_patch_text(alt, ramp_alt))
    (directory / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": [25.0, 51.0], "ruleset": "icao"}))
    return osm


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    d = tmp_path_factory.mktemp("tpa")
    return (_write_patch(d, "patch.osm", 10.0),
            _write_patch(d, "control.osm", 10.0))


# ──────────────────────────────────────────────────────────────────
# §1 ONE CODE PATH
# ──────────────────────────────────────────────────────────────────
def test_the_cli_is_a_formatter_over_the_library_entry(tpa, scene, tmp_path,
                                                       capsys):
    """Functional twin: the CLI's JSON IS ``run_acceptance``'s result.  A
    CLI that measured anything itself would drift from the library the
    moment either changed."""
    patch, control = scene
    out = tmp_path / "cli.json"
    rc = tpa.main([str(patch), "--control", str(control),
                   "--site", "M=25.0011,51.0001",
                   "--json", str(out)])
    capsys.readouterr()
    cli = json.loads(out.read_text())["checks"]

    profile = tpa.Profile(name="(cli)",
                          sites={"M": (25.0011, 51.0001)})
    lib = tpa.run_acceptance(patch, control, profile=profile,
                             thresholds=tpa.Thresholds())
    assert [c["name"] for c in cli] == [c.name for c in lib]
    assert [c["verdict"] for c in cli] == [c.verdict for c in lib]
    assert [c["measured"] for c in cli] == [c.measured for c in lib]
    assert rc in (0, 1)


def test_the_cli_entry_does_not_reimplement_a_single_check(tpa):
    src = inspect.getsource(tpa.main)
    assert "run_acceptance(" in src, (
        "main must call run_acceptance — it is the library entry")
    for private in ("_check_site_reach", "_check_covered_span",
                    "_check_geometry_drift", "_check_over_cap_ramp_rows",
                    "_census_rows"):
        assert private not in src, (
            f"main calls {private} directly — that is a second assembly "
            f"of the check list beside run_acceptance")


# ──────────────────────────────────────────────────────────────────
# §2 NO PRIVATE RE-COUNT, NO PRIVATE PARSE
# ──────────────────────────────────────────────────────────────────
def test_every_row_count_comes_from_the_census(tpa):
    src = TOOL_PATH.read_text()
    assert "census_one(" in src, (
        "row counts must come from tools/harness/census.py's census_one")
    assert "load_check_grade()" in src
    # the census-wrapper tell: naming the law's private check functions,
    # or enumerating the family register itself.
    for private in ("_check_within_shape", "_check_vertex_to_edge_step",
                    "_check_mid_edge_step", "_check_cross_shape_proximity",
                    "run_checks("):
        assert private not in src, (
            f"the tool names {private!r} — that is the census-wrapper "
            f"approach that lost nine families from an integration report")
    assert "LAW_FAMILIES" not in src, (
        "the tool enumerates the family register itself")


def test_the_patch_is_read_through_the_law_librarys_parser(tpa):
    src = inspect.getsource(tpa.Patch)
    assert "cg._parse_osm(" in src, (
        "Patch must parse through check_grade._parse_osm — a second "
        "parser is a second population")


def test_the_adjudicated_total_is_the_censuss_own_field(tpa):
    """Never recomputed here: the census publishes the number and the
    ruling it is taken under."""
    rep = {"adjudication": {"adjudicated_total": 7048,
                            "deferred_total": 1773,
                            "out_of_scope_total": 0},
           "lawtrue": {"total": 8821}}
    assert tpa._adjudicated(rep) == 7048
    # the fallback reproduces the census's own definition, not a guess
    assert tpa._adjudicated({"adjudication": {"deferred_total": 1773,
                                              "out_of_scope_total": 0},
                             "lawtrue": {"total": 8821}}) == 7048


# ──────────────────────────────────────────────────────────────────
# §3 THE INSTRUMENT IS DETERMINISTIC AND HONEST
# ──────────────────────────────────────────────────────────────────
def test_the_geometry_join_breaks_ties_deterministically(tpa):
    src = inspect.getsource(tpa._check_geometry_drift)
    assert "most_common(1)" not in src, (
        "a most_common tie is broken by insertion order, which here is "
        "set iteration order — the same bytes measured 8 and 9")
    assert "sorted(cand.items()" in src


def test_a_check_with_no_inputs_reports_SKIPPED_never_PASS(tpa, scene):
    """A missing control must not read as a clean bill of health."""
    patch, _control = scene
    checks = {c.name: c for c in tpa.run_acceptance(
        patch, None, profile=tpa.Profile(name="x",
                                         sites={"M": (25.0011, 51.0001)}))}
    for name in ("geometry_drift", "subgrade_by_role", "adjudicated_delta"):
        assert checks[name].verdict == tpa.SKIP, (
            f"{name} claimed a verdict with no control patch")
    # …and a check whose inputs ARE present still answers.
    assert checks["no_low_connector"].verdict == tpa.PASS


def test_thresholds_are_arguments_not_literals_in_the_checks(tpa, scene):
    """The bar moves with the flag — a threshold baked into a check is a
    number no round can restate."""
    patch, control = scene
    strict = tpa.run_acceptance(
        patch, control, profile=tpa.Profile(name="x",
                                            sites={"M": (25.0011, 51.0001)}),
        thresholds=tpa.Thresholds(site_max_m=0.001))
    loose = tpa.run_acceptance(
        patch, control, profile=tpa.Profile(name="x",
                                            sites={"M": (25.0011, 51.0001)}),
        thresholds=tpa.Thresholds(site_max_m=10000.0))
    by = lambda cs, n: next(c for c in cs if c.name == n)  # noqa: E731
    assert by(strict, "site_reach").verdict == tpa.FAIL
    assert by(loose, "site_reach").verdict == tpa.PASS
    assert by(strict, "site_reach").measured == \
        by(loose, "site_reach").measured, "the MEASURED value moved with the bar"


def test_no_hardcoded_lane_paths_or_airport_literals_in_the_checks(tpa):
    """A promoted tool may ship an airport PROFILE; it may not bake one
    into a check or point at a lane scratch dir."""
    src = TOOL_PATH.read_text()
    body = src.split("SITE_PROFILES: Dict[str, Profile] = {", 1)[1]
    body = body.split("@dataclass\nclass Thresholds", 1)[1]
    assert "/tmp/" not in body, "a lane path is baked into the checks"
    assert "OTHH" not in body, "an airport literal is baked into the checks"
    assert "25.27" not in body, "a site coordinate is baked into a check"


# ──────────────────────────────────────────────────────────────────
# §4 REACHABLE FROM THE INDEX
# ──────────────────────────────────────────────────────────────────
def test_the_tool_is_in_the_tool_index():
    index = (ROOT.parent / "tools" / "INDEX.md")
    assert index.exists(), "tools/INDEX.md not found"
    text = index.read_text()
    assert "tunnel_portal_acceptance.py" in text, (
        "a tool absent from tools/INDEX.md is treated as absent "
        "(RULINGS 7e90032) — land the entry in the same commit")


# ──────────────────────────────────────────────────────────────────
# §5/§6 BORE GEOMETRY ANSWERS A MOUTH — RE-KEYED to ramp/mouth
# (RULINGS 2026-08-31b; ``docs/specs/linear-transport-redesign-spec.md``
# §5.4, consumer census row #40)
#
# WHAT WAS HERE.  Three twins pinned the CLAIM-MEMBERSHIP READ
# (``_check_claim_names_the_bore`` + the ``claim_cover_min`` bar /
# ``--claim-cover-min`` flag): "does R14-1's claim actually NAME this
# bore?"  That question dies with the claim class — the check, the
# threshold and the flag are all deleted from the tool, and their twins
# with them.  Three more twins admitted a below-grade CLAIMED CORRIDOR
# (``ref=tunnel_road``) as bore geometry.  Under the canonical mouth
# (RULINGS 2026-08-30) the only objects that answer a mouth are the
# portal walk's OWN surfaces — a ``tunnel_ramp`` role way, or a
# ``tunnel_mouth`` ref way WITH a face — and that is what is pinned
# below, re-keyed in the SAME batch as the retirement so this battery
# cannot silently go SKIP.
# ──────────────────────────────────────────────────────────────────
def _mouth_scene(directory: Path, mouth_alt: float,
                 walled: bool = True, ref: str = "tunnel_mouth",
                 role: str = "groundside_pavement") -> Path:
    """A mouth site answered by a ``tunnel_mouth`` piece, with a
    ``tunnel_ramp`` (and its own wall) 3 km away.

    The near piece carries ``ref=tunnel_mouth`` on a NON-ramp role: that
    is the re-roled-mouth class the ref arm of the predicate exists for
    (OTHH mouth D shipped its bore surface as ``groundside_pavement``),
    and it is the only spelling that exercises the ``tunnel_mouth``
    admission branch — a piece already wearing ``role=tunnel_ramp`` is
    admitted by the role branch before that branch is reached.

    ``walled`` emits the §2.3 wall face alongside the NEAR piece; the far
    ramp always keeps its own wall, so the coverage table has a
    population in both arms.  §T6.3 admits a mouth piece as bore geometry
    only WITH a face, so the two spellings are the twin's two arms.
    """
    def node(i, lat, lon, a):
        return (f"<node id='-{i}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                f"<tag k='alt_abs' v='{a}'/></node>")
    parts = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    coords = [(25.0000, 51.0000), (25.0000, 51.0004),
              (25.0003, 51.0004), (25.0003, 51.0000)]
    for i, (la, lo) in enumerate(coords, start=1):
        parts.append(node(i, la, lo, mouth_alt))
    parts.append("<way id='-301'><nd ref='-1'/><nd ref='-2'/><nd ref='-3'/>"
                 "<nd ref='-4'/><nd ref='-1'/>"
                 f"<tag k='role' v='{role}'/>"
                 f"<tag k='ref' v='{ref}'/><tag k='shapeID' v='1'/></way>")
    if walled:
        # the §2.3 face: a band hugging the mouth piece's long side
        wc = [(24.99998, 51.0000), (24.99998, 51.0004),
              (25.00002, 51.0004), (25.00002, 51.0000)]
        for i, (la, lo) in enumerate(wc, start=21):
            parts.append(node(i, la, lo, mouth_alt + 4.0))
        parts.append("<way id='-303'><nd ref='-21'/><nd ref='-22'/>"
                     "<nd ref='-23'/><nd ref='-24'/><nd ref='-21'/>"
                     "<tag k='role' v='retaining_wall'/>"
                     "<tag k='ref' v='tunnel_wall'/>"
                     "<tag k='shapeID' v='3'/></way>")
    # a tunnel_ramp far away, so the ramp-only reading is a long distance
    rc = [(25.0300, 51.0000), (25.0300, 51.0002),
          (25.0303, 51.0002), (25.0303, 51.0000)]
    for i, (la, lo) in enumerate(rc, start=11):
        parts.append(node(i, la, lo, -2.0))
    parts.append("<way id='-302'><nd ref='-11'/><nd ref='-12'/>"
                 "<nd ref='-13'/><nd ref='-14'/><nd ref='-11'/>"
                 "<tag k='role' v='tunnel_ramp'/>"
                 "<tag k='ref' v='tunnel_ramp'/><tag k='shapeID' v='2'/></way>")
    # …and ITS wall, so the bore-corridor coverage table always has a
    # walled below-grade ramp to measure.
    fw = [(25.02998, 51.0000), (25.02998, 51.0002),
          (25.03002, 51.0002), (25.03002, 51.0000)]
    for i, (la, lo) in enumerate(fw, start=31):
        parts.append(node(i, la, lo, 2.0))
    parts.append("<way id='-304'><nd ref='-31'/><nd ref='-32'/>"
                 "<nd ref='-33'/><nd ref='-34'/><nd ref='-31'/>"
                 "<tag k='role' v='retaining_wall'/>"
                 "<tag k='ref' v='tunnel_wall'/>"
                 "<tag k='shapeID' v='4'/></way>")
    parts.append("</osm>")
    osm = directory / f"mouth{mouth_alt}_{ref}_{int(walled)}.osm"
    osm.write_text("\n".join(parts))
    (directory / (osm.name + ".axes.json")).write_text(json.dumps(
        {"anchor": [25.0, 51.0], "ruleset": "icao"}))
    return osm


def test_a_walled_tunnel_mouth_answers_the_mouth(tpa, tmp_path):
    """MEASURED (OTHH mouth D, 2026-08-25): the bore surface at the mouth
    was there and this check read 727.6 m, because it looked only for
    ``tunnel_ramp``.  The mouth was answered; the instrument was looking
    for the wrong object.  The canonical mouth's own piece answers it."""
    osm = _mouth_scene(tmp_path, -0.90)
    checks = {c.name: c for c in tpa.run_acceptance(
        osm, None, profile=tpa.Profile(name="x",
                                       sites={"D": (25.00003, 51.00003)}))}
    assert checks["mouth_vertex_reach"].verdict == tpa.PASS
    assert checks["site_reach"].measured < 60.0
    assert "tunnel_mouth" in checks["site_reach"].detail


def test_a_FACELESS_tunnel_mouth_is_not_bore_geometry(tpa, tmp_path):
    """§T6.3: dug, and with NO wall anywhere on it, is a hole in the
    ground, not a bore.  The instrument used to accept it and report the
    mouth answered, which is how a mouth piece "with no ramp and no
    walls" could pass a table (RULINGS 2026-08-28c item 3)."""
    osm = _mouth_scene(tmp_path, -0.90, walled=False)
    checks = {c.name: c for c in tpa.run_acceptance(
        osm, None, profile=tpa.Profile(name="x",
                                       sites={"D": (25.00003, 51.00003)}))}
    assert checks["mouth_vertex_reach"].verdict == tpa.FAIL
    assert checks["site_reach"].measured > 1000.0
    assert "faceless" in checks["site_reach"].detail


def test_the_bore_corridor_wall_coverage_is_reported(tpa, tmp_path):
    """§T6.1's acceptance number exists, RE-KEYED (census #40): the
    population is the portal walk's own BELOW-GRADE ``tunnel_ramp``
    surfaces, not the retired claim's corridors — otherwise the check
    reports SKIP forever, the silent-skip the redesign's §5.4 forbids."""
    osm = _mouth_scene(tmp_path, -0.90)
    checks = {c.name: c for c in tpa.run_acceptance(
        osm, None, profile=tpa.Profile(name="x",
                                       sites={"D": (25.00003, 51.00003)}))}
    assert "claimed_corridor_walls" not in checks, (
        "the retired check name is still registered")
    c = checks["bore_corridor_walls"]
    assert c.verdict == tpa.SKIP, "no bar given ⇒ a REPORT, never a PASS"
    assert 0.0 < c.measured <= 1.0, c.measured
    assert "tunnel_ramp" in c.detail


def test_a_RETIRED_tunnel_road_ref_never_answers_a_mouth(tpa, tmp_path):
    """The successor to the at-grade-claim twin.  ``tunnel_road`` is not
    a class any more (RULINGS 2026-08-31b): a below-grade road surface
    wearing that ref — walled, and sitting right on the site — is mapped
    road pavement, not bore geometry, so the check must still report the
    distance to the real ramp."""
    osm = _mouth_scene(tmp_path, -0.90, ref="tunnel_road")
    checks = {c.name: c for c in tpa.run_acceptance(
        osm, None, profile=tpa.Profile(name="x",
                                       sites={"D": (25.00003, 51.00003)}))}
    assert checks["mouth_vertex_reach"].verdict == tpa.FAIL
    assert checks["site_reach"].measured > 1000.0


def test_the_site_reach_check_uses_the_patchs_own_parser(tpa):
    """No second parser inside the check — the tool's rule, restated on
    the re-keyed check that replaced the claim read."""
    src = inspect.getsource(tpa._check_site_reach)
    assert "ElementTree" not in src and "iterparse" not in src
    assert "patch.pts(" in src
    assert not hasattr(tpa, "_check_claim_names_the_bore"), (
        "the claim-membership check is retired (census #40)")
    assert "claim_cover_min" not in {
        f.name for f in dataclasses.fields(tpa.Thresholds)}


# ──────────────────────────────────────────────────────────────────
# §F1 — WALL TOP IS FLAT ACROSS ITS WIDTH (LEMD ramp/road fidelity)
# ──────────────────────────────────────────────────────────────────
def _wall_band_patch(directory: Path, name: str, inner: float,
                     outer: float, with_foot: bool = False,
                     crest_twist: float = 0.0) -> Path:
    """A patch carrying ONE ``tunnel_wall`` band, 1.0 m across, whose two
    long edges carry ``inner`` and ``outer``.

    The two stations stand ~33 m apart in latitude and the band is ~1 m
    across in longitude, which is the real geometry: the cross-band pair
    is the CLOSE pair, the along-run neighbours are the far ones.
    """
    def node(i, lat, lon, a):
        return (f"<node id='-{i}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                f"<tag k='alt_abs' v='{a}'/></node>")
    parts = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    lon_inner, lon_outer = 51.0000000, 51.0000100      # ~1.0 m apart
    rows = [(25.0000, lon_outer, outer), (25.0003, lon_outer, outer),
            (25.0003, lon_inner, inner), (25.0000, lon_inner, inner)]
    for i, (la, lo, a) in enumerate(rows, start=1):
        parts.append(node(i, la, lo, a))
    twist_nd = ""
    if crest_twist:
        # A SECOND CREST VERTEX AT ONE STATION — the real residual shape
        # (LEMD way -11939, nodes -31647/-31651 1.0 m apart at 564.49 vs
        # 564.15): at a band END the knife leaves two crest vertices
        # side by side, and if they read different stations of the body
        # they carry different values.  Nothing to do with the shelf.
        parts.append(node(7, 25.0000, lon_outer + 0.0000100,
                          outer + crest_twist))
        twist_nd = "<nd ref='-7'/>"
    parts.append("<way id='-201'><nd ref='-1'/>" + twist_nd
                 + "<nd ref='-2'/><nd ref='-3'/>"
                 "<nd ref='-4'/><nd ref='-1'/>"
                 "<tag k='aeroway' v='building'/>"
                 "<tag k='role' v='retaining_wall'/>"
                 "<tag k='ref' v='tunnel_wall'/>"
                 "<tag k='shapeID' v='9'/></way>")
    if with_foot:
        # §T5's shelf, SHARING the face's inner edge node-for-node (one
        # boolean partition of one polygon) and standing inboard of it.
        lon_ramp = 50.9999940
        parts.append(node(5, 25.0000, lon_ramp, inner))
        parts.append(node(6, 25.0003, lon_ramp, inner))
        parts.append("<way id='-202'><nd ref='-4'/><nd ref='-3'/>"
                     "<nd ref='-6'/><nd ref='-5'/><nd ref='-4'/>"
                     "<tag k='aeroway' v='building'/>"
                     "<tag k='role' v='retaining_wall'/>"
                     "<tag k='ref' v='tunnel_wall_foot'/>"
                     "<tag k='shapeID' v='10'/></way>")
    parts.append("</osm>")
    osm = directory / name
    osm.write_text("\n".join(parts))
    (directory / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": [25.0, 51.0], "ruleset": "icao"}))
    return osm


class TestWallTopFlat:
    """The check measures ACROSS the band and adjudicates only when a bar
    is given — the two properties every threshold in this tool has."""

    def _run(self, tpa, patch, **kw):
        thr = tpa.Thresholds(**kw)
        return {c.name: c for c in tpa._check_wall_top_flat(
            tpa.Patch(patch, tpa.load_census().load_check_grade()), thr)}

    def test_a_twisted_band_is_measured(self, tpa, tmp_path):
        patch = _wall_band_patch(tmp_path, "twist.osm", 609.8, 610.6)
        got = self._run(tpa, patch)["wall_top_flat"]
        assert got.measured == pytest.approx(0.8, abs=0.001)

    def test_a_flat_band_measures_zero(self, tpa, tmp_path):
        patch = _wall_band_patch(tmp_path, "flat.osm", 610.6, 610.6)
        got = self._run(tpa, patch)["wall_top_flat"]
        assert got.measured == pytest.approx(0.0, abs=1e-9)

    def test_without_a_bar_it_reports_never_adjudicates(self, tpa,
                                                        tmp_path):
        patch = _wall_band_patch(tmp_path, "report.osm", 609.8, 610.6)
        got = self._run(tpa, patch)["wall_top_flat"]
        assert got.verdict == tpa.SKIP
        assert got.threshold is None

    def test_the_bar_moves_the_verdict_not_the_measurement(self, tpa,
                                                           tmp_path):
        patch = _wall_band_patch(tmp_path, "bar.osm", 609.8, 610.6)
        failing = self._run(tpa, patch, wall_top_delta_max=0.01)
        passing = self._run(tpa, patch, wall_top_delta_max=1.0)
        assert failing["wall_top_flat"].verdict == tpa.FAIL
        assert passing["wall_top_flat"].verdict == tpa.PASS
        assert (failing["wall_top_flat"].measured
                == passing["wall_top_flat"].measured)

    def test_the_along_run_frame_is_not_the_cross_band_one(self, tpa,
                                                           tmp_path):
        """A span narrower than the band finds NO pair and reports
        SKIPPED — never PASS over a population it did not examine."""
        patch = _wall_band_patch(tmp_path, "span.osm", 609.8, 610.6)
        got = self._run(tpa, patch, wall_band_span_m=0.2,
                        wall_top_delta_max=0.01)["wall_top_flat"]
        assert got.verdict == tpa.SKIP

    def test_a_patch_with_no_wall_skips(self, tpa, tmp_path):
        patch = _write_patch(tmp_path, "nowall.osm", 100.0)
        got = self._run(tpa, patch, wall_top_delta_max=0.01)
        assert got["wall_top_flat"].verdict == tpa.SKIP

    # ── THE CREST-ONLY FRAME (ruling 2026-08-29) ─────────────────────

    def test_the_shelf_top_is_not_a_twist(self, tpa, tmp_path):
        """THIS CHECK MEASURES TWIST, NOT HEIGHT.

        With §T5's foot the band is a PARTITION: the ``tunnel_wall_foot``
        shelf sits at ramp level and the ``tunnel_wall`` face RISES from
        the shelf's top to the crest.  The face's inner edge is the
        shelf's top — a shared node of the partition — so pairing it
        against the crest reports the wall's HEIGHT and makes the §F1
        bar unsatisfiable at the same time as R16-2b's owned annulus.
        The crest members are the band vertices the shelf does not
        carry.
        """
        patch = _wall_band_patch(tmp_path, "shelf.osm", 605.0, 610.6,
                                 with_foot=True)
        got = self._run(tpa, patch)["wall_top_flat"]
        assert "CREST-ONLY" in got.detail
        # the 5.6 m face height is EXCLUDED, and what is left is the
        # crest against itself: one value, one station.
        assert got.measured == pytest.approx(0.0, abs=1e-9), got.detail

    def test_a_twist_is_still_caught_with_a_shelf_present(self, tpa,
                                                          tmp_path):
        """The frame excludes the shelf, never the defect: a crest that
        genuinely disagrees with itself across the band still reads."""
        patch = _wall_band_patch(tmp_path, "shelftwist.osm", 605.0,
                                 610.6, with_foot=True, crest_twist=0.4)
        got = self._run(tpa, patch)["wall_top_flat"]
        assert got.measured == pytest.approx(0.4, abs=0.001), got.detail

    def test_no_foot_reads_exactly_as_before(self, tpa, tmp_path):
        """A patch with NO ``tunnel_wall_foot`` has an empty shelf set,
        so every pre-§T5 number stays comparable."""
        patch = _wall_band_patch(tmp_path, "nofoot.osm", 609.8, 610.6)
        got = self._run(tpa, patch)["wall_top_flat"]
        assert got.measured == pytest.approx(0.8, abs=0.001)
        assert "0 shelf node(s) excluded" in got.detail

    def test_the_cli_carries_the_flag_into_the_thresholds(self, tpa):
        args = tpa.build_parser().parse_args(
            ["p.osm", "--wall-top-delta-max", "0.01",
             "--wall-band-span-m", "2.5"])
        assert args.wall_top_delta_max == 0.01
        assert args.wall_band_span_m == 2.5

    def test_the_check_runs_in_the_library_entry(self, tpa):
        source = inspect.getsource(tpa.run_acceptance)
        assert "_check_wall_top_flat" in source
