"""``tools/void_census.py`` — the airside-enclosed VOID census twin.

Promoted 2026-08-07 from the enclave attribution lane's scratchpad on its
second use (``tools/INDEX.md`` rule 3).  Known-answer fixtures only: a
hand-written patch whose voids, contents and areas are exact by
construction, so the tool's report can be asserted value-for-value.

What this pins:

  * the VOID set IS the enclave topology — interior rings of the
    airside∪building union, read with the engine's own role vocabulary
    (``auto_patch.enclaves``), not a hand-typed copy;
  * the POCKET flag reads the gap law's own ``GAP_FILL_MAX_WIDTH_M``;
  * the ESCAPE clause — a touching tunnel ramp takes a void out of the
    no-escape population;
  * CONTENTS and BARE GROUND — the wall inventory, the per-class table
    and the remainder that carries no shape at all;
  * the gap-treated flag reads the emitted ``gap_fill_spine`` face;
  * the anchor frame comes from the axes sidecar (so this tool and the
    harness census read one geometry), and a patch without one still
    censuses — with no lat/lon.
"""
from __future__ import annotations

import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import void_census as VC  # noqa: E402
from auto_patch.config import GAP_FILL_MAX_WIDTH_M  # noqa: E402

ANCHOR = (30.0, 31.0)
R_EARTH = 6_378_137.0


def _ll(x, y):
    """Metres → lat/lon in the anchor frame (``layout._projection``)."""
    lat0, lon0 = ANCHOR
    lat = lat0 + math.degrees(y / R_EARTH)
    lon = lon0 + math.degrees(x / (R_EARTH * math.cos(math.radians(lat0))))
    return lat, lon


class _Patch:
    """A tiny patch-OSM writer in metre space."""

    def __init__(self):
        self.nodes = []
        self.ways = []
        self._nid = -1000
        self._wid = -10000

    def way(self, ring, **tags):
        nids = []
        for x, y in ring:
            self._nid -= 1
            lat, lon = _ll(x, y)
            self.nodes.append(
                f"<node id='{self._nid}' visible='true' "
                f"lat='{lat:.11f}' lon='{lon:.11f}' />")
            nids.append(self._nid)
        self._wid -= 1
        body = "".join(f"<nd ref='{n}' />" for n in nids + [nids[0]])
        body += "".join(f"<tag k='{k}' v='{v}' />" for k, v in tags.items())
        self.ways.append(f"<way id='{self._wid}' visible='true'>{body}</way>")
        return self._wid

    def rect(self, x0, y0, x1, y1, **tags):
        return self.way([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **tags)

    def write(self, path, sidecar=True):
        path.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
            + "\n".join(self.nodes) + "\n" + "\n".join(self.ways)
            + "\n</osm>\n")
        if sidecar:
            (path.parent / (path.name + ".axes.json")).write_text(
                json.dumps({"anchor": list(ANCHOR), "ruleset": "icao"}))
        return path


# The hole: x in [30, 130], y in [30, 90] → 100 x 60 = 6,000 m².
HOLE = (30.0, 30.0, 130.0, 90.0)


def _frame(patch):
    x0, y0, x1, y1 = HOLE
    patch.rect(0.0, 0.0, 160.0, y0, role="runway", aeroway="runway")
    patch.rect(0.0, y1, 160.0, 120.0, role="runway", aeroway="runway")
    patch.rect(0.0, y0, x0, y1, role="stub", aeroway="taxiway")
    patch.rect(x1, y0, 160.0, y1, role="stub", aeroway="taxiway")


def _one(tmp_path, build, name="TEST.osm", sidecar=True):
    patch = _Patch()
    build(patch)
    return VC.census(patch.write(tmp_path / name, sidecar=sidecar))


def test_the_frame_has_exactly_one_void(tmp_path):
    report = _one(tmp_path, _frame)
    assert report["voids"] == 1
    assert report["no_escape"] == 1
    rec = report["records"][0]
    x0, y0, x1, y1 = HOLE
    assert rec["area_m2"] == pytest.approx((x1 - x0) * (y1 - y0), rel=1e-3)
    assert rec["short_side_m"] == pytest.approx(y1 - y0, rel=1e-3)
    assert rec["pocket"] is True
    assert rec["bare_frac"] == pytest.approx(1.0)
    assert rec["walls"] == []
    assert rec["gap_treated"] is False


def test_the_pocket_flag_is_the_gap_laws_own_width(tmp_path):
    wide = 3.0 * GAP_FILL_MAX_WIDTH_M

    def build(patch):
        patch.rect(0.0, 0.0, wide + 60.0, 30.0, role="runway")
        patch.rect(0.0, 30.0 + wide, wide + 60.0, wide + 60.0, role="runway")
        patch.rect(0.0, 30.0, 30.0, 30.0 + wide, role="stub")
        patch.rect(30.0 + wide, 30.0, wide + 60.0, 30.0 + wide, role="stub")

    report = _one(tmp_path, build)
    assert report["voids"] == 1
    rec = report["records"][0]
    assert rec["short_side_m"] > GAP_FILL_MAX_WIDTH_M
    assert rec["pocket"] is False
    assert report["pocket"] == 0


def test_a_touching_tunnel_ramp_is_an_escape(tmp_path):
    def build(patch):
        _frame(patch)
        x0, _y0, x1, y1 = HOLE
        patch.rect((x0 + x1) / 2 - 5.0, y1 - 2.0,
                   (x0 + x1) / 2 + 5.0, y1 + 8.0, role="tunnel_ramp")

    report = _one(tmp_path, build)
    assert report["voids"] == 1
    assert report["no_escape"] == 0
    rec = report["records"][0]
    assert rec["no_escape"] is False
    assert len(rec["escapes"]) == 1
    assert rec["escapes"][0]["role"] == "tunnel_ramp"


def test_a_distant_ramp_is_not_an_escape(tmp_path):
    def build(patch):
        _frame(patch)
        patch.rect(400.0, 400.0, 420.0, 420.0, role="tunnel_ramp")

    report = _one(tmp_path, build)
    assert report["no_escape"] == 1


def test_contents_walls_and_bare_ground(tmp_path):
    def build(patch):
        _frame(patch)
        # A 20 m² retaining wall and a 50 m² groundside sliver inside.
        patch.rect(60.0, 50.0, 70.0, 52.0,
                   role="retaining_wall", ref="adjacent_ground_wall")
        patch.rect(90.0, 50.0, 100.0, 55.0,
                   role="groundside_pavement", ref="groundside")

    report = _one(tmp_path, build)
    rec = report["records"][0]
    assert report["walls_in_no_escape_voids"] == 1
    assert report["voids_with_wall"] == 1
    assert len(rec["walls"]) == 1
    assert rec["walls"][0]["ref"] == "adjacent_ground_wall"
    assert rec["walls"][0]["area_m2"] == pytest.approx(20.0, rel=1e-3)
    assert rec["contents"]["groundside_pavement/groundside"][0] == 1
    assert rec["contents"]["groundside_pavement/groundside"][1] == \
        pytest.approx(50.0, rel=1e-3)
    # 6,000 − 20 − 50 = 5,930 m² of ground carrying no shape at all.
    assert rec["bare_m2"] == pytest.approx(5930.0, rel=1e-3)


def test_a_gap_face_marks_the_void_treated(tmp_path):
    def build(patch):
        _frame(patch)
        x0, y0, x1, y1 = HOLE
        patch.rect(x0, y0, x1, y1,
                   role="graded_strip", ref="gap_fill_spine")

    report = _one(tmp_path, build)
    rec = report["records"][0]
    assert rec["gap_treated"] is True
    assert report["gap_treated"] == 1
    assert rec["bare_frac"] == pytest.approx(0.0, abs=1e-6)


def test_buildings_join_the_surround(tmp_path):
    """Owner, CYXY building4: a vehicle cannot leave through a building,
    so a building CLOSES a void the pavement alone leaves open."""
    def open_frame(patch):
        x0, y0, x1, y1 = HOLE
        patch.rect(0.0, 0.0, 160.0, y0, role="runway")
        patch.rect(0.0, y1, 160.0, 120.0, role="runway")
        patch.rect(0.0, y0, x0, y1, role="stub")
        # East side left OPEN — no void.

    assert _one(tmp_path, open_frame, "open.osm")["voids"] == 0

    def closed_by_building(patch):
        open_frame(patch)
        x0, y0, x1, y1 = HOLE
        patch.rect(x1, y0, 160.0, y1, role="building", aeroway="building")

    report = _one(tmp_path, closed_by_building, "closed.osm")
    assert report["voids"] == 1
    assert report["records"][0]["pocket"] is True


def test_a_patch_without_a_sidecar_still_censuses(tmp_path):
    """No sidecar: the topology is unchanged (it is geometry), the frame
    falls back to the node mean and lat/lon are not reported."""
    report = _one(tmp_path, _frame, "bare.osm", sidecar=False)
    assert report["voids"] == 1
    assert report["anchor"] is None
    rec = report["records"][0]
    assert rec["lat"] is None and rec["lon"] is None
    assert rec["area_m2"] == pytest.approx(6000.0, rel=1e-3)


def test_the_role_vocabulary_is_the_engines_own():
    """No hand-typed role list — the census-wrapper precedent."""
    from auto_patch import enclaves as EN

    assert VC.ENCLAVE_SURROUND_ROLES is EN.ENCLAVE_SURROUND_ROLES
    assert VC.ENCLAVE_ESCAPE_ROLES is EN.ENCLAVE_ESCAPE_ROLES
    assert VC.ENCLAVE_ESCAPE_CONTACT_M == EN.ENCLAVE_ESCAPE_CONTACT_M


def test_the_cli_writes_its_json(tmp_path, capsys):
    patch = _Patch()
    _frame(patch)
    path = patch.write(tmp_path / "cli.osm")
    out = tmp_path / "voids.json"
    assert VC.main([str(path), "--json", str(out)]) == 0
    data = json.loads(out.read_text())
    assert len(data) == 1 and data[0]["voids"] == 1
    assert "voids=1" in capsys.readouterr().out
