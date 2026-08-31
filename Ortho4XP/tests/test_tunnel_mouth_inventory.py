"""THE CANONICAL TUNNEL MOUTH, ENUMERATED — the twin for
``tunnel_portal_acceptance._check_mouth_inventory``.

RULINGS 2026-08-30 (owner, OTHH; supersedes 2026-08-25e for the
service-road family):

    At a tunnel mouth the emitted set is exactly: ONE ramp surface
    descending the corridor centre to the mouth line, ONE retaining wall
    (wall + foot) per side, ONE straight end cap.  The ramp reaches the
    mouth line.  No second road shape may share the corridor.  Nested
    wall rings and wall fragments are defects.

WHAT A MOUTH SITE IS, AND WHY IT IS NOT A ``tunnel_mouth`` WAY.  The
first cut of this check keyed its population on ``ref == "tunnel_mouth"``
and MEASURED ZERO on the very airport it adjudicates: the OTHH control
patch (merged main ``127eec15``, 2,600 shapes) carries 22 ``tunnel_ramp``
surfaces, 39 ``tunnel_wall`` and 48 ``tunnel_wall_foot`` pieces and NOT
ONE ``tunnel_mouth`` or ``tunnel_cap`` way — the 2026-08-30j merge note
says so in words ("wrapped ends = end cap").  A check whose population is
empty where it adjudicates is the silent-SKIP failure, so a MOUTH SITE is
the geometry the ruling describes: a cluster of the tunnel's own emitted
road surfaces standing within ``--mouth-cluster-m`` of each other.  One
site is one place a bore surfaces, however many pieces the emitter left
there — which is what makes "ONE ramp surface" countable at all.

The check EXTENDS the acceptance instrument rather than forking a second
one (RULINGS ``7e90032``), so these twins also pin that it reads the
patch through the instrument's own parser and reports SKIPPED — never
PASS — when the bar is not armed.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "tunnel_portal_acceptance.py"
sys.path.insert(0, str(ROOT / "src"))

ANCHOR_LAT, ANCHOR_LON = 25.0, 51.0
_M_PER_DEG_LAT = 111320.0
_M_PER_DEG_LON = 111320.0 * math.cos(math.radians(ANCHOR_LAT))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tpa():
    return _load("tpa_mouth_under_test", TOOL_PATH)


def _ll(x, y):
    return (ANCHOR_LAT + y / _M_PER_DEG_LAT,
            ANCHOR_LON + x / _M_PER_DEG_LON)


class _PatchBuilder:
    """A synthetic emitted patch, in METRES, written as the OSM the
    instrument's own parser reads."""

    def __init__(self):
        self.nodes = []
        self.ways = []
        self._nid = 0
        self._wid = 0

    def rect(self, x0, y0, x1, y1, role, ref, alt=-2.0):
        self._wid += 1
        nids = []
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            self._nid += 1
            la, lo = _ll(x, y)
            self.nodes.append(
                f"<node id='-{self._nid}' lat='{la:.11f}' "
                f"lon='{lo:.11f}'><tag k='alt_abs' v='{alt}'/></node>")
            nids.append(self._nid)
        refs = "".join(f"<nd ref='-{n}'/>" for n in nids)
        self.ways.append(
            f"<way id='-{1000 + self._wid}'>{refs}<nd ref='-{nids[0]}'/>"
            f"<tag k='aeroway' v='taxiway'/><tag k='role' v='{role}'/>"
            f"<tag k='ref' v='{ref}'/>"
            f"<tag k='shapeID' v='{self._wid}'/></way>")
        return f"-{1000 + self._wid}"

    def write(self, directory: Path, name="MOUT_auto.patch.osm") -> Path:
        osm = directory / name
        osm.write_text("\n".join(
            ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
            + self.nodes + self.ways + ["</osm>"]))
        (directory / (name + ".axes.json")).write_text(json.dumps(
            {"anchor": [ANCHOR_LAT, ANCHOR_LON], "ruleset": "icao"}))
        return osm


def _canonical_site(b: _PatchBuilder, x0=0.0):
    """ONE canonical mouth: a ramp running north into a mouth plate, one
    wall + foot on each side, one end cap across the mouth line."""
    #        y
    #   cap    ---------------- 40
    #   mouth  [ 34 .. 39 ]   x 0..20
    #   ramp   [  0 .. 34 ]   x 0..20
    b.rect(x0 + 0.0, 0.0, x0 + 20.0, 34.0, "tunnel_ramp", "tunnel_ramp")
    b.rect(x0 + 0.0, 34.0, x0 + 20.0, 39.0, "tunnel_ramp", "tunnel_mouth")
    # walls: one per side, standing clear of the corridor
    b.rect(x0 - 2.0, 0.0, x0 - 1.0, 39.0, "retaining_wall", "tunnel_wall")
    b.rect(x0 + 21.0, 0.0, x0 + 22.0, 39.0, "retaining_wall", "tunnel_wall")
    # feet: the annulus between ramp edge and wall face, one per side
    b.rect(x0 - 1.0, 0.0, x0 - 0.4, 39.0, "retaining_wall",
           "tunnel_wall_foot")
    b.rect(x0 + 20.4, 0.0, x0 + 21.0, 39.0, "retaining_wall",
           "tunnel_wall_foot")
    # one straight end cap across the mouth line
    b.rect(x0 - 2.0, 39.0, x0 + 22.0, 40.0, "retaining_wall", "tunnel_cap")


_SEQ = [0]


def _inventory(tpa, tmp_path, builder, **thr_kw):
    cg = tpa.load_census().load_check_grade()
    _SEQ[0] += 1
    osm = builder.write(tmp_path, f"MOUT{_SEQ[0]}_auto.patch.osm")
    patch = tpa.Patch(osm, cg)
    thr = tpa.Thresholds(**thr_kw)
    return tpa._check_mouth_inventory(patch, thr)[0]


class TestTheCanonicalMouthPasses:

    def test_one_ramp_one_wall_and_foot_per_side_one_cap(
            self, tpa, tmp_path):
        b = _PatchBuilder()
        _canonical_site(b)
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.PASS, c.detail
        assert c.measured == 0
        assert "1 tunnel mouth site(s), 0 NOT canonical" in c.detail
        assert "ramp=1 plate=1" in c.detail
        assert "wall L/R=1/1 foot L/R=1/1" in c.detail

    def test_two_independent_mouths_are_both_canonical(self, tpa, tmp_path):
        """The mouth radius must not let one mouth read the other's
        band — the acceptance enumerates EVERY mouth."""
        b = _PatchBuilder()
        _canonical_site(b, x0=0.0)
        _canonical_site(b, x0=200.0)
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.PASS, c.detail
        assert "2 tunnel mouth site(s), 0 NOT canonical" in c.detail


class TestEachDefectClassIsCaught:

    def test_a_ramp_that_stops_short_of_the_mouth_fails(
            self, tpa, tmp_path):
        """RULINGS 2026-08-28c items 2/3 and the 2026-08-30 mouth law:
        'the ramp reaches the mouth line'.  The owner's own site was a
        ramp stopping 2.6 m short."""
        b = _PatchBuilder()
        b.rect(0.0, 0.0, 20.0, 30.0, "tunnel_ramp", "tunnel_ramp")
        b.rect(0.0, 34.0, 20.0, 39.0, "tunnel_ramp", "tunnel_mouth")
        b.rect(-2.0, 0.0, -1.0, 39.0, "retaining_wall", "tunnel_wall")
        b.rect(21.0, 0.0, 22.0, 39.0, "retaining_wall", "tunnel_wall")
        b.rect(-1.0, 0.0, -0.4, 39.0, "retaining_wall", "tunnel_wall_foot")
        b.rect(20.4, 0.0, 21.0, 39.0, "retaining_wall", "tunnel_wall_foot")
        b.rect(-2.0, 39.0, 22.0, 40.0, "retaining_wall", "tunnel_cap")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL
        assert "reach=4.00" in c.detail

    def test_two_ramps_at_one_mouth_fail(self, tpa, tmp_path):
        """'ONE ramp surface' — the dual-adjacent-ramps class of the
        2026-08-28c item-2 site."""
        b = _PatchBuilder()
        _canonical_site(b)
        b.rect(-6.0, 0.0, 0.0, 34.5, "tunnel_ramp", "tunnel_ramp")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL

    def test_a_second_wall_on_one_side_fails(self, tpa, tmp_path):
        """The 2026-08-30j residual class: 7 wall pieces where the law
        says one per side."""
        b = _PatchBuilder()
        _canonical_site(b)
        b.rect(-4.0, 0.0, -3.0, 39.0, "retaining_wall", "tunnel_wall")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL
        assert c.measured == 1

    def test_a_duplicate_corridor_surface_fails(self, tpa, tmp_path):
        """The class R14-1's claim minted beside the synthetic ramp —
        two tunnel road surfaces sharing ground."""
        b = _PatchBuilder()
        _canonical_site(b)
        b.rect(1.0, 5.0, 7.0, 30.0, "tunnel_ramp", "tunnel_ramp")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL
        assert "ramp=2" in c.detail
        assert "dup=1" in c.detail

    def test_a_nested_wall_ring_fails(self, tpa, tmp_path):
        b = _PatchBuilder()
        _canonical_site(b)
        b.rect(-1.8, 5.0, -1.2, 20.0, "retaining_wall", "tunnel_wall")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL
        assert "nested=" in c.detail

    def test_a_wall_fragment_fails(self, tpa, tmp_path):
        b = _PatchBuilder()
        _canonical_site(b)
        b.rect(40.0, 30.0, 40.3, 30.3, "retaining_wall", "tunnel_wall")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL

    def test_a_missing_end_cap_fails(self, tpa, tmp_path):
        b = _PatchBuilder()
        b.rect(0.0, 0.0, 20.0, 34.0, "tunnel_ramp", "tunnel_ramp")
        b.rect(0.0, 34.0, 20.0, 39.0, "tunnel_ramp", "tunnel_mouth")
        b.rect(-2.0, 0.0, -1.0, 39.0, "retaining_wall", "tunnel_wall")
        b.rect(21.0, 0.0, 22.0, 39.0, "retaining_wall", "tunnel_wall")
        b.rect(-1.0, 0.0, -0.4, 39.0, "retaining_wall", "tunnel_wall_foot")
        b.rect(20.4, 0.0, 21.0, 39.0, "retaining_wall", "tunnel_wall_foot")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.FAIL
        assert "cap=0" in c.detail
        # the wrapped-end evidence: the two ENDS are open, so the site is
        # not capped by 2026-08-30j's wrapped-end reading either
        frac = float(c.detail.split("open=")[1].split()[0])
        assert frac > 0.10


class TestTheInstrumentRules:

    def test_it_reports_skipped_when_the_bar_is_not_armed(
            self, tpa, tmp_path):
        """SKIPPED, never PASS — the whole instrument's rule."""
        b = _PatchBuilder()
        _canonical_site(b)
        c = _inventory(tpa, tmp_path, b)
        assert c.verdict == tpa.SKIP
        assert "1 tunnel mouth site(s)" in c.detail

    def test_a_patch_with_no_corridor_surface_skips(self, tpa, tmp_path):
        b = _PatchBuilder()
        b.rect(0.0, 0.0, 8.0, 34.0, "retaining_wall", "tunnel_wall")
        c = _inventory(tpa, tmp_path, b, mouth_canonical=True)
        assert c.verdict == tpa.SKIP
        assert "no tunnel corridor surface" in c.detail

    def test_the_full_inventory_is_printed_for_every_mouth(
            self, tpa, tmp_path):
        """'Quote the full inventory' is the acceptance — one line per
        mouth, always, whatever the verdict."""
        b = _PatchBuilder()
        _canonical_site(b, x0=0.0)
        _canonical_site(b, x0=200.0)
        c = _inventory(tpa, tmp_path, b)
        assert c.detail.count("    site ") == 2

    def test_it_is_registered_in_the_batteries_check_list(self, tpa):
        src = __import__("inspect").getsource(tpa.run_acceptance)
        assert "_check_mouth_inventory(patch, thr)" in src

    def test_the_tool_is_reachable_from_the_index(self):
        index = (ROOT.parent / "tools" / "INDEX.md").read_text(
            encoding="utf-8")
        assert "mouth_inventory" in index, (
            "a tool capability absent from tools/INDEX.md is treated as "
            "absent (RULINGS 7e90032)")
