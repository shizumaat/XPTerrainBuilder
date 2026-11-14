"""A PAD UNDER A UNIT'S UPPER STOREY (RULINGS 2026-11-13aa (1), #2068; spec
``docs/specs/2068-upper-pad-spec.md``): the reader
(``airport/unit_storey.upper_pads``), the road's arm cut back
(``classify/storey_edge.arm_storeys``) and the pad held as its unit block's
upper level (``planar/group_up``).  Synthetic: a terminal at floor y 0 on an
apron at DEM 30, a tower pad east of it on a hill at DEM 35, a plinth and a
walled body at y +4.7 over it."""
from __future__ import annotations

import types

from auto_patch_v2.airport.unit_storey import upper_pads
from auto_patch_v2.classify.storey_edge import (ARM_PAD_KEY, UPPER_FLOOR_KEY, UPPER_UNIT_KEY,
                                                UPPER_Y_KEY, arm_storeys)
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar.group_up import GROUP_UP, plan_group_up, upper_pad_reads
from auto_patch_v2.planar.overlay import Region
from shapely.geometry import box
from shapely.ops import unary_union
from shapely.strtree import STRtree

LAW = Law.for_airport("SYNT")


def XY(lon, lat):
    return (lon, lat)


def _part(x0, y0, x1, y1, base_y, height=0.0, feet=0, line=False):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    ft = tuple((y0 + (y1 - y0) * k / max(feet, 1), x0, base_y) for k in range(feet))
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 height_m=height, rings=(ring,), feet=ft, line=line,
                                 scatter=False)


class _Dem:
    def __init__(self, hill=35.0, x_hill=90.0, slope=0.0):
        self.hill, self.x_hill, self.slope = hill, x_hill, slope

    def z(self, x, y):
        return self.hill + self.slope * (y + 10.0) if x >= self.x_hill else 30.0


APRON = box(0.0, -80.0, 100.0, -40.0)
TERMINAL = _part(0.0, -40.0, 60.0, 0.0, 0.0, height=10.0, feet=24)
PAD = box(100.0, 0.0, 120.0, 20.0)
PLINTH = _part(100.0, 0.0, 120.0, 20.0, 4.7)
BODY = _part(105.0, 5.0, 115.0, 15.0, 4.7, height=12.0)
TERM_PAD = box(0.0, -40.0, 60.0, 0.0)
PADS = [("building1", TERM_PAD), ("building2", PAD)]


def _airport(parts, dem=None):
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=parts)])
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]),
                                 frame=types.SimpleNamespace(entry=lambda: XY),
                                 dem=_Dem() if dem is None else dem, pack=None, icao="SYNT")


def _read(parts, dem=None):
    return upper_pads(_airport(parts, dem), LAW, APRON, PADS)


def test_a_plinth_and_a_body_on_a_hill_is_an_upper_pad():
    got = _read([TERMINAL, PLINTH, BODY])
    assert len(got) == 1
    up = got[0]
    assert (up.ref, up.unit, up.floor_y, up.y) == ("building2", 0, 0.0, 4.7)
    assert up.cover == 1.0 and up.walled == 1 and up.delta == 5.0


def test_doubt_refuses():
    # a canopy / plinth alone: nothing walled
    assert _read([TERMINAL, PLINTH]) == []
    # a deck over level ground: the ground does not stand a storey up
    assert _read([TERMINAL, PLINTH, BODY], _Dem(hill=30.0)) == []
    # a part reaching down to the floor over the pad
    assert _read([TERMINAL, PLINTH, BODY, _part(102.0, 2.0, 108.0, 8.0, 0.0, 5.0)]) == []
    # a hill three rises up
    assert _read([TERMINAL, PLINTH, BODY], _Dem(hill=30.0 + 3 * 4.7)) == []
    # the pad's own relief over the rise
    assert _read([TERMINAL, PLINTH, BODY], _Dem(slope=0.5)) == []
    # no DEM
    ap = _airport([TERMINAL, PLINTH, BODY])
    ap.dem = None
    assert upper_pads(ap, LAW, APRON, PADS) == []


def test_witness_t1_t3_refuse():
    """Spec 2068 A1 (3): T1 born airside within ``pad_frontage_m`` of the
    pad refuses, and so does a pad no flipped road reaches (KBWI / LOWS);
    T2 a plinth plane under half the pad; T3 no floor pad of the unit
    fronting airside."""
    ap = _airport([TERMINAL, PLINTH, BODY])
    ring = box(94.0, -6.0, 126.0, 26.0).difference(PAD)          # the flipped road
    air = unary_union([APRON, ring])
    got = upper_pads(ap, LAW, air, PADS, born=APRON, flipped=ring)
    assert [u.ref for u in got] == ["building2"]
    # T1: born apron beside the pad
    born = unary_union([APRON, box(120.0, 0.0, 130.0, 20.0)])
    assert upper_pads(ap, LAW, unary_union([born, ring]), PADS, born=born, flipped=ring) == []
    # T1: no flipped road at the pad
    far = box(200.0, 0.0, 210.0, 10.0)
    assert upper_pads(ap, LAW, unary_union([APRON, far]), PADS, born=APRON, flipped=far) == []
    # T2: a plinth over 40 % of the pad
    half = _part(100.0, 0.0, 120.0, 8.0, 4.7)
    body = _part(105.0, 1.0, 115.0, 7.0, 4.7, height=12.0)
    assert upper_pads(_airport([TERMINAL, half, body]), LAW, air, PADS, born=APRON,
                      flipped=ring) == []
    # T3: no floor pad among the pads
    assert upper_pads(ap, LAW, air, [("building2", PAD)], born=APRON, flipped=ring) == []


def _face():
    block = box(60.0, -40.0, 80.0, 30.0)
    neck = box(80.0, 7.0, 94.0, 13.0)
    collar = box(94.0, -6.0, 126.0, 26.0).difference(PAD)
    return unary_union([block, neck, collar])


def _cells():
    return [types.SimpleNamespace(ring=tuple(APRON.exterior.coords)[:-1], holes=(),
                                  role="apron", side="airside")]


def _final():
    ev = {"kind": "apron", "source_class": "strip", "airside_edge_was": "service_road",
          "airside_edge_flip": 1.0, "airside_edge_m": 20.0}
    return [["apron", "pol1", _face(), None, ev, "apron"]]


def test_the_road_round_an_upper_pad_is_cut_back_to_its_arm():
    final = _final()
    got = arm_storeys(final, _cells(), PADS,
                      _airport([TERMINAL, PLINTH, BODY]), LAW, 1.0)
    assert got == {"building2": {UPPER_Y_KEY: 4.7, UPPER_FLOOR_KEY: 0.0, UPPER_UNIT_KEY: 0.0}}
    rest = [f for f in final if f[0] == "apron"]
    arm = [f for f in final if f[0] == "service_road"]
    assert len(rest) == 1 and rest[0][1] == "pol1"
    assert rest[0][2].distance(APRON) == 0.0               # the kept apron at the apron
    assert rest[0][2].distance(PAD) > 7.0                  # and off the pad
    assert arm and all(f[4][ARM_PAD_KEY] == "building2" and f[1].startswith("pol1#")
                       and "airside_edge_was" not in f[4] for f in arm)
    assert unary_union([f[2] for f in arm]).distance(PAD) == 0.0
    # A1 (1): the arm starts beyond the floor pad (the terminal keeps its frontage)
    assert unary_union([f[2] for f in arm]).distance(TERM_PAD) > 0.0
    assert abs(sum(f[2].area for f in final) - _face().area) < 1e-6


def test_no_upper_pad_no_change():
    final = _final()
    assert arm_storeys(final, _cells(), PADS,
                       _airport([TERMINAL, PLINTH]), LAW, 1.0) == {}
    assert len(final) == 1 and final[0][2].equals(_face())


def _regions():
    term = box(0.0, -40.0, 60.0, 0.0)
    return [Region("building", "building1", term, None, None, "airside", "cell"),
            Region("building", "building2", PAD, None, None, "airside", "cell")]


def test_the_upper_pad_is_its_unit_blocks_upper_level():
    reg = Registries()
    reg.held["building1"] = {"unit": "building1", "verdict": "one_block"}
    counts: dict = {}
    air = [APRON]
    upper = {"building2": (4.7, 0.0, 0)}
    done = plan_group_up(_regions(), upper, air, STRtree(air),
                         _airport([TERMINAL, PLINTH, BODY]), LAW, 0.5, counts, reg)
    refs = sorted(str(r.ref) for r in done["building2"])
    assert "building1/p1" in refs
    rec = reg.landings["building1/p1"]
    assert (rec["block"], rec["y"], rec["witness"], rec["pad"]) == (
        "building1", 4.7, GROUP_UP, "building2")
    assert rec["kind"] == "upper_level"
    # no held block of the unit: refused, nothing minted
    reg2 = Registries()
    counts2: dict = {}
    assert plan_group_up(_regions(), upper, air, STRtree(air),
                         _airport([TERMINAL, PLINTH, BODY]), LAW, 0.5, counts2, reg2) == {}
    assert counts2["upper_pads_refused"] and not reg2.landings


def test_the_pad_reading_rides_the_cell():
    c = types.SimpleNamespace(ref="building2", role="building",
                              evidence={UPPER_Y_KEY: 4.7, UPPER_FLOOR_KEY: 0.0,
                                        UPPER_UNIT_KEY: 0.0})
    other = types.SimpleNamespace(ref="building1", role="building", evidence={})
    arm = types.SimpleNamespace(ref="pol1#1", role="service_road",
                                evidence={ARM_PAD_KEY: "building2"})
    assert upper_pad_reads([c, other, arm]) == {"building2": (4.7, 0.0, 0, ("pol1#1",))}
