"""ONE FLAT-SITE DECISION (issue #932, owner option B, 2026-10-18; spec
``docs/specs/auto-patch-v2/flat-site-datum-spec.md`` §6).

1. DEM prep decides with the v2 detector and the build READS that record:
   the build never re-measures (the detector is not called), and the
   verdict, Z0 and region it holds are the record's;
2. the mismatch rule: a record that baked a plateau the composed DEM does
   not carry, or a record in another frame, is ``ColdDemFrame``;
3. S1 counts JOINED ends only — a CIFP record with no apt.dat runway no
   longer moves the consensus (v1 read every CIFP end);
4. the extent covers the runways and is cut at the water.

Synthetic only: an in-memory raster, the checked-in CYXY fixture's apt.dat
and CIFP (read-only), no network, no build.
"""
from __future__ import annotations

import math
import shutil
import types
from pathlib import Path

import numpy as np
import pytest
from auto_patch_v2.airport import flat_site as F
from auto_patch_v2.airport import flat_site_prep as PREP
from auto_patch_v2.airport import flat_site_read as READ
from auto_patch_v2.airport.dem_production import ColdDemFrame, TileWater
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

FIX = Path(__file__).resolve().parent / "fixtures" / "CYXY"
ANCHOR = (0.5, 0.5)
Z0 = 3.96


class _TileDem:
    """What ``O4_DEM_Utils.DEM`` shows DEM prep: a working grid over the
    tile (0, 0), constant on land."""

    def __init__(self, value: float = 1.0, n: int = 1201) -> None:
        self.x0 = self.y0 = 0.0
        self.x1 = self.y1 = 1.0
        self.alt_dem = np.full((n, n), float(value), dtype=np.float32)


def _site(thresholds=(Z0, Z0), runway_len_m=1800.0):
    """A boundary about the anchor and ONE runway whose ends stand OUTSIDE
    it (the extent must reach them)."""
    frame = Frame("ZZZZ", ANCHOR, 6)
    to_xy, _ll = frame.transformers()
    ring = [(ANCHOR[1] - 0.004, ANCHOR[0] - 0.003), (ANCHOR[1] + 0.004, ANCHOR[0] - 0.003),
            (ANCHOR[1] + 0.004, ANCHOR[0] + 0.003), (ANCHOR[1] - 0.004, ANCHOR[0] + 0.003)]
    outer = tuple(to_xy(lo, la) for lo, la in ring)
    half = runway_len_m / 2.0
    rw = PREP._Runway((PREP._End((-half, 0.0), thresholds[0]),
                       PREP._End((half, 0.0), thresholds[1])), 45.0)
    return PREP.FlatSiteInputs("ZZZZ", frame, (rw,), (), (PREP._Poly(outer, ()),))


def _decide(site=None, water=None, value=1.0):
    law = Law.for_airport("ZZZZ")
    tw = TileWater(0, 0, water, None)
    return PREP.decide(site or _site(), _TileDem(value), 0, 0, tw, law,
                       out=lambda line: None)


class _ComposedDem:
    """The build's sampler double: the composed raster reads ``z`` and
    hands back DEM prep's record."""

    def __init__(self, rec, z: float) -> None:
        self._rec, self._z = rec, z

    def flat_site_decision(self):
        return self._rec

    def z(self, x, y):
        return self._z

    def posting_m(self):
        return 30.0

    def source_pixel_m(self):
        return None, "base_tier"                # DEM prep's own class here


def _airport(rec, z, origin=ANCHOR):
    return types.SimpleNamespace(icao="ZZZZ", frame=Frame("ZZZZ", origin, 6),
                                 dem=_ComposedDem(rec, z))


# ── 1. one decision ───────────────────────────────────────────────────────

def test_the_build_reads_dem_preps_record_and_never_measures(monkeypatch):
    rec = _decide()
    assert rec["verdict"] == "flat_candidate" and rec["z0_m"] == pytest.approx(Z0)
    rec["plateau"] = True                        # the bake landed it
    monkeypatch.setattr(F, "detect", lambda *a, **k: pytest.fail("re-measured"))
    fv, how = READ.verdict_for_build(_airport(rec, Z0), Law.for_airport("ZZZZ"))
    assert how == "decided in DEM prep"
    assert (fv.verdict, fv.auto_verdict, fv.z0_m, fv.source) == (
        rec["verdict"], rec["auto_verdict"], rec["z0_m"], rec["source"])
    assert fv.region == F.from_record(rec).region and fv.region
    assert fv.signals["decided_in"] == "dem_prep"
    assert fv.signals["plateau_offset_m"] == pytest.approx(0.0, abs=1e-6)
    assert fv.signals["s4"]["pass"] is None      # S4: a report, no objects


def test_no_record_measures_with_the_same_detector():
    """Flat-site mode off / an airport DEM prep never saw: the build says
    so and measures with the ONE detector."""
    law = Law.for_airport("ZZZZ")
    rec = _decide()
    site = _site()
    dem = _ComposedDem(None, 1.0)
    ap = types.SimpleNamespace(icao="ZZZZ", frame=site.frame, runways=site.runways,
                               pavements=(), boundaries=site.boundaries, dem=dem)
    fv, how = READ.verdict_for_build(ap, law)
    assert how.startswith("measured in the build")
    assert fv.verdict == rec["verdict"]


# ── 2. the mismatch rule ──────────────────────────────────────────────────

def test_a_composed_dem_without_the_plateau_is_cold():
    rec = _decide()
    rec["plateau"] = True
    with pytest.raises(ColdDemFrame, match="off Z0"):
        READ.verdict_for_build(_airport(rec, Z0 + 3.0), Law.for_airport("ZZZZ"))


def test_a_plateau_that_did_not_land_is_not_required():
    """The bake refused (all water, a bake error): the record says so and
    the build does not demand a plateau the DEM was never given."""
    rec = _decide()
    rec["plateau"] = "the whole extent is water"
    fv, _how = READ.verdict_for_build(_airport(rec, Z0 + 3.0), Law.for_airport("ZZZZ"))
    assert fv.substitutes and "plateau_offset_m" not in fv.signals


def test_a_record_in_another_frame_is_cold():
    rec = _decide()
    with pytest.raises(ColdDemFrame, match="frame"):
        READ.verdict_for_build(_airport(rec, Z0, origin=(0.6, 0.5)),
                               Law.for_airport("ZZZZ"))


# ── 3. S1 reads joined ends ───────────────────────────────────────────────

def test_s1_counts_only_ends_joined_to_an_apt_dat_runway(tmp_path):
    law = Law.for_airport("CYXY")
    cifp = tmp_path / "CYXY.dat"
    shutil.copyfile(FIX / "CIFP" / "CYXY.dat", cifp)
    base = PREP.site_inputs("CYXY", str(FIX), str(cifp), law)
    n_base = sum(e.threshold_elev_m is not None for r in base.runways for e in r.ends)
    with open(cifp, "a", encoding="utf-8", newline="\n") as fh:
        # a CIFP threshold 60 km away, 500 ft higher, no apt.dat runway
        fh.write("RWY:RW09 ,     ,      ,02800, ,    , ,   ;N61200000,W136000000,0000;\n")
    joined = PREP.site_inputs("CYXY", str(FIX), str(cifp), law)
    elevs = [e.threshold_elev_m for r in joined.runways for e in r.ends
             if e.threshold_elev_m is not None]
    assert n_base > 0 and len(elevs) == n_base
    assert max(elevs) < 2800 * 0.3048 - 1.0


# ── 4. the extent: runways in, water out ──────────────────────────────────

def test_the_region_covers_the_runways_and_excludes_water():
    dry = _decide(_site(runway_len_m=2400.0))
    gate = F.from_record({"verdict": "x", "region": dry["gate"]}).region
    region = Polygon(gate[0][0], list(gate[0][1]))
    assert region.covers(box(-1150.0, -20.0, 1150.0, 20.0))    # the runway's ends
    # sea over the tile east of the anchor (tile-relative degrees)
    wet = _decide(_site(runway_len_m=2400.0),
                  water=box(ANCHOR[1] + 0.001, 0.0, 1.0, 1.0))
    assert wet["signals"]["region_water_cut_m2"] > 0.0
    assert wet["signals"]["region_area_m2"] > 0.0
    # past the shore only the runway itself stands (the airport's own
    # surfaces are land by declaration, §37 (11) (4)); the margin does not
    lon_max = max(p[0] for o, _h in wet["region_ll"] for p in o)
    assert lon_max <= ANCHOR[1] + 1200.0 / 111319.49 + 1e-4
    assert wet["signals"]["region_area_m2"] < dry["signals"]["region_area_m2"]
    assert math.isclose(dry["z0_m"], wet["z0_m"])


# ── 5. the plateau fills, it does not cut (RULINGS 2026-10-26r, #1208) ────

def test_the_record_publishes_its_pavement_not_its_boundary():
    """``pavement`` is the apt.dat pavements ∪ runways at margin 0 — the
    one ground the bake keeps at Z0 — never the boundary's grass."""
    rec = _decide(_site(runway_len_m=2400.0))
    pav = F.from_record({"verdict": "x", "region": rec["pavement"]}).region
    pavement = Polygon(pav[0][0], list(pav[0][1]))
    assert pavement.covers(box(-1150.0, -20.0, 1150.0, 20.0))
    assert not pavement.contains(Polygon([(-300, 200), (300, 200), (300, 300),
                                          (-300, 300)]))   # boundary grass
    assert rec["pavement_ll"] and len(rec["pavement_ll"]) == len(rec["pavement"])


class _PavedOnlyDem(_ComposedDem):
    """Z0 on the runway strip of pavement, real ground 3 m above off it."""

    def z(self, x, y):
        return Z0 if abs(y) <= 22.5 else Z0 + 3.0


def test_the_plateau_check_reads_the_pavement_not_the_boundary():
    """Off the pavement the composed DEM keeps ground above Z0 (the fill-
    only rule); the mismatch rule reads the pavement, so it is not cold."""
    rec = _decide()
    rec["plateau"] = True
    dem = _PavedOnlyDem(rec, Z0)
    ap = types.SimpleNamespace(icao="ZZZZ", frame=Frame("ZZZZ", ANCHOR, 6), dem=dem)
    fv, _how = READ.verdict_for_build(ap, Law.for_airport("ZZZZ"))
    assert fv.signals["plateau_offset_m"] == pytest.approx(0.0, abs=1e-6)


def test_the_packs_draped_pavement_joins_the_pavement(monkeypatch):
    """RULINGS 2026-10-27d: pavement stays flat — the pack's draped
    ``.pol`` pages (``pack_pavement``) are pavement too."""
    apron = box(-300.0, 150.0, 300.0, 280.0)        # boundary grass, no apt.dat row
    seen = {}

    def _pages(root, name, lat, lon, to_xy, own, mod_cache_root, xplane_root):
        seen["mod_cache_root"] = mod_cache_root
        return [apron]
    monkeypatch.setattr(PREP._pack_pavement, "pavement_pages", _pages)
    law = Law.for_airport("ZZZZ")
    rec = PREP.decide(_site(), _TileDem(1.0), 0, 0, TileWater(0, 0, None, None),
                      law, out=lambda line: None, mod_cache_root="/cache")
    assert seen["mod_cache_root"] == "/cache"
    pav = F.from_record({"verdict": "x", "region": rec["pavement"]}).region
    got = unary_union([Polygon(o, list(h)) for o, h in pav])
    assert got.covers(apron.buffer(-1.0))
