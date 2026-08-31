"""Twin for ``tools/road_terrain_conformance.py`` — the terrain-conformance
instrument RULINGS 2026-08-31a requires.

The law it states, in the small: a road that RIDES a hill reads
``follow_ratio`` 1 and no cutting; the same road planed FLAT through the
same hill reads ``follow_ratio`` 0 and a cutting as deep as the hill —
while both surfaces are equally lawful to a census, which is the whole
reason the instrument exists.

The DEM is INJECTED (``read_patch(dem_at=...)``), so the twin states the
law on a surface it owns and needs no cached corpus, no network and no
X-Plane install.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "tools"), str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import road_terrain_conformance as RTC                          # noqa: E402

#: A degree of latitude in metres, the frame the fixture's stations are
#: laid out in (the tool's own metre frame is check_grade's).
_M_PER_DEG = 111320.0

LAT0, LON0 = 30.10, 31.40


#: The fixture hill's grade — UNDER the 8 % road cap on purpose, so the
#: whole crossing is lawfully followable and the flat arm's cutting is
#: chosen, never forced.
HILL_GRADE = 0.07


def _hill(lat: float, _lon: float) -> float:
    """A 10.5 m hill over 300 m of road: 7 % up, 7 % down — everywhere
    UNDER the road cap, so the whole crossing is lawfully followable and
    a flat road through it is a pure cutting."""
    s = (lat - LAT0) * _M_PER_DEG
    if s <= 150.0:
        return 100.0 + HILL_GRADE * s
    return 100.0 + HILL_GRADE * 150.0 - HILL_GRADE * (s - 150.0)


def _patch(tmp_path: Path, name: str, levels) -> Path:
    """A chain of ``len(levels)`` square service_road rings marching north,
    each ring flat at its own level; consecutive rings SHARE their two
    touching nodes, which is the chain identity the tool joins on."""
    step_m = 30.0
    half_w = 3.0
    dlat = step_m / _M_PER_DEG
    dlon = half_w / (_M_PER_DEG * math.cos(math.radians(LAT0)))

    lines = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    nid = 0
    node_of: dict = {}

    def node(i_station: int, side: int, z: float) -> str:
        nonlocal nid
        key = (i_station, side)
        if key in node_of:
            return node_of[key]
        nid += 1
        the_id = f"-{nid}"
        lat = LAT0 + i_station * dlat
        lon = LON0 + side * dlon
        lines.append(f"  <node id='{the_id}' lat='{lat:.11f}' "
                     f"lon='{lon:.11f}' version='1'>")
        lines.append(f"    <tag k='alt_abs' v='{z:.3f}' />")
        lines.append("  </node>")
        node_of[key] = the_id
        return the_id

    wid = 0
    for k, z in enumerate(levels):
        # The shared edge takes the FIRST ring's level, exactly as an
        # emitted weld does; the ring's own median is what the tool reads.
        a = node(k, -1, z)
        b = node(k, +1, z)
        c = node(k + 1, +1, z)
        d = node(k + 1, -1, z)
        wid += 1
        lines.append(f"  <way id='-{1000 + wid}' version='1'>")
        for r in (a, b, c, d, a):
            lines.append(f"    <nd ref='{r}' />")
        lines.append("    <tag k='role' v='service_road' />")
        lines.append("    <tag k='aeroway' v='taxiway' />")
        lines.append("  </way>")
    lines.append("</osm>")
    p = tmp_path / name
    p.write_text("\n".join(lines))
    return p


def _levels_following():
    """The road ON the hill: each ring flat at the ground under its own
    MIDPOINT, which is the best a flat ring can do on a slope (its two
    ends sit +-half a step off the ground, and that residual is what the
    conformance floor below allows for)."""
    return [_hill(LAT0 + (k + 0.5) * (30.0 / _M_PER_DEG), LON0)
            for k in range(11)]


def _levels_flat():
    """The road PLANED through the hill at its two end values (both 100 m)
    — the 2026-08-30 regression's shape, and a surface no grade law
    prices."""
    return [100.0] * 11


def _read(patch: Path):
    return RTC.read_patch(patch, dem_at=_hill)


def test_following_road_reads_conformant(tmp_path):
    r = _read(_patch(tmp_path, "FOLLOW.osm", _levels_following()))
    assert len(r["chains"]) == 1, r["chains"]
    ch = r["chains"][0]
    assert ch["rings"] == 11
    # The hill is real and the road is on it.
    assert ch["dem_relief_m"] == pytest.approx(10.5, abs=0.5)
    assert ch["follow_ratio"] == pytest.approx(1.0, abs=0.15)
    # A flat ring on a 7 % slope can be at most half a step off the
    # ground; nothing here is a CUTTING.
    assert ch["cut_max_m"] < 1.5
    # Every DEM step is UNDER the cap, so the whole crossing is followable.
    assert ch["dem_followable_pct"] == pytest.approx(100.0, abs=1e-6)


def test_flat_road_through_the_hill_is_a_cutting(tmp_path):
    r = _read(_patch(tmp_path, "FLAT.osm", _levels_flat()))
    ch = r["chains"][0]
    assert ch["dem_relief_m"] == pytest.approx(10.5, abs=0.5)
    # THE DEFECT, in one number: the road crosses a 10.5 m hill with zero
    # relief of its own and a 10.5 m cutting, and its emitted grade is 0 %
    # against a cap of 8 % — "capped at a visibly low grade, cutting
    # through hills" (owner, 2026-08-31).
    assert ch["emitted_relief_m"] == pytest.approx(0.0, abs=1e-6)
    assert ch["follow_ratio"] == pytest.approx(0.0, abs=1e-6)
    assert ch["cut_max_m"] == pytest.approx(10.5, abs=0.6)
    assert ch["emitted_grade_max_pct"] == pytest.approx(0.0, abs=1e-6)
    assert ch["dem_grade_max_pct"] == pytest.approx(100.0 * HILL_GRADE,
                                                    abs=0.5)
    assert ch["dem_followable_pct"] == pytest.approx(100.0, abs=1e-6)


def test_site_lookup_matches_by_place_not_way_id(tmp_path):
    """A site is a PLACE (``arm_site_read``'s frame rule): the same point
    finds the chain in both arms, whose way ids are identical here only by
    construction."""
    ra = _read(_patch(tmp_path, "A.osm", _levels_following()))
    rb = _read(_patch(tmp_path, "B.osm", _levels_flat()))
    mid_lat = LAT0 + 5 * (30.0 / _M_PER_DEG)
    ca, da = RTC.chain_at_site(ra, mid_lat, LON0)
    cb, db = RTC.chain_at_site(rb, mid_lat, LON0)
    assert ca is not None and cb is not None
    assert da < 10.0 and db < 10.0
    # The instrument separates the two arms at the same place.
    assert ca["follow_ratio"] > 0.8
    assert cb["follow_ratio"] < 0.05


def test_site_outside_the_radius_is_reported_not_zeroed(tmp_path):
    r = _read(_patch(tmp_path, "C.osm", _levels_flat()))
    ch, dist = RTC.chain_at_site(r, LAT0 + 1.0, LON0, radius_m=40.0)
    assert ch is None
    assert dist is not None and dist > 40.0


def test_rank_selects_hill_chains_only(tmp_path):
    """Discovery obeys the spec's own site rule — >= 10 m of DEM relief and
    a real span — and says so rather than returning a short chain."""
    r = _read(_patch(tmp_path, "D.osm", _levels_flat()))
    assert rank_len(r, 10.0, 100.0) == 1
    # A 40 m relief bar excludes this 10.5 m hill: reported empty, never
    # padded with the next-best chain.
    assert rank_len(r, 40.0, 100.0) == 0
    # A 10 km span bar likewise.
    assert rank_len(r, 10.0, 10000.0) == 0


def rank_len(read, relief, span) -> int:
    return len(RTC.rank(read, min_relief_m=relief, min_span_m=span, top=5))


def test_road_family_and_dem_sampler_are_imported_not_respelled():
    """The census-wrapper guard: the tool's road family IS
    ``check_grade._ROAD_FAMILY_ROLES`` and its DEM sampler IS
    ``apron_drape_read``'s — not a second spelling of either."""
    import check_grade as CG
    import apron_drape_read as ADR
    src = Path(RTC.__file__).read_text()
    assert "CG._ROAD_FAMILY_ROLES" in src
    assert "ADR._dem_at" in src and "ADR._load_dem" in src
    # And no private role literal list of its own.
    assert "service_junction\"" not in src and "'service_junction'" not in src
    assert CG._ROAD_FAMILY_ROLES  # the imported set is non-empty
    assert callable(ADR._dem_at)


def test_cap_comes_from_production_config():
    """``dem_followable_pct`` is judged against the OWNER CONSTANT, read
    from ``config.SERVICE_ROAD_MAX_GRADE`` and never a second number."""
    from auto_patch.config import SERVICE_ROAD_MAX_GRADE
    assert RTC.ROAD_CAP == pytest.approx(float(SERVICE_ROAD_MAX_GRADE))
