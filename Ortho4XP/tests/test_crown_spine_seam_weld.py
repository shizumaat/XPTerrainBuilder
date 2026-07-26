"""The re-extended crown-spine TERMINUS welds into the ring it lands on
(owner ruling 2026-07-25, gate ``O4_CROWN_SPINE_SEAM_WELD``).

R1 (``test_crown_seam_ramp.py``) re-extends a runway's crown spine out to
the tile-CUT edge the ``_SPINE_EDGE_CLEAR_M`` erosion pulled it back from.
The terminus it snaps to is ``axis ∩ cut-back edge`` — the geometric
MIDPOINT of that ring edge — while ``conformance.densify_long_edges``
splits the same edge into ``ceil(L/60)`` EQUAL parts.  So the terminus
coincides with a ring vertex iff that part count is EVEN, and BOTH
parities shipped broken:

* ODD (SPLP, L = 148.09 m → 3 parts): the terminus sat mid-edge as an
  UNWELDED T-VERTEX — same coordinates as the edge it lies on, but its own
  node and its own stale profile value (measured forks -0.015 m at
  -13/-77 and -0.085 m at -13/-78).  No weld could catch it: crown spines
  are not ``layout.shapes`` (they live on ``layout.crown_spines`` as
  ``(latlon, alts)`` tuples), so ``enforce_conformance`` never sees them.
* EVEN: ``to_osm`` minted the spine's node ids unconditionally, with no
  coordinate lookup, so the terminus emitted as a LITERAL coincident
  DUPLICATE node — the Triangle4XP degenerate class the
  ``gap_interior_rings`` first-node reuse already guards against.

What these tests pin:

W1  the terminus is INSERTED into its host ring as a T-vertex, valued by
    that edge's own lerp (the ring is the value authority — the seam ramp
    has driven the crown to zero at the cut edge by design, so the spine's
    own profile value there is the stale party);
W2  a terminus that ALREADY coincides with a ring vertex inserts nothing
    and still adopts the ring's value;
W3  ``to_osm`` REUSES the interned node at a spine coordinate instead of
    minting a second one — one node, the ring's altitude, no duplicate;
W4  the welded coordinate is protected from BOTH decimators (it is
    3D-redundant by construction, and neither decimator's vote can see the
    spine that needs it);
G   ``O4_CROWN_SPINE_SEAM_WELD=0`` restores the pre-ruling behaviour —
    separate node, no ring insert, the stale spine value.

Hermetic: hand-built layouts, no fixtures, no DEM, no network.
"""
from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest
from shapely.geometry import Polygon

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_patch.pipeline  # noqa: F401,E402  (import-cycle order)
from auto_patch import config as CFG                        # noqa: E402
from auto_patch import crown as CR                          # noqa: E402
from auto_patch import emit_decimate as ED                  # noqa: E402
from auto_patch.canonical_points import (                   # noqa: E402
    CanonicalPointRegistry)
from auto_patch.layout import (                             # noqa: E402
    BuiltShape, PavementLayout, ROLE_RUNWAY)


# ── synthetic world ──────────────────────────────────────────────────
# Anchored ON the integer longitude line lon == 1, so in local metres the
# seam is x == 0 and the two cut-back lines are x == ±TILE_CUT_HALF_WIDTH_M
# (the same frame ``test_crown_seam_ramp.py`` uses).
ANCHOR_LAT = 0.5
ANCHOR_LON = 1.0
M_PER_DEG = 111320.0
HALF = CFG.TILE_CUT_HALF_WIDTH_M
# Half of SPLP's measured 148.09 m oblique cut-back edge.
CHL = 74.045
# The cut edge ramps linearly with y; the axis crosses it at y == 0.
ALT_LO, ALT_MID, ALT_HI = 90.0, 92.0, 94.0
FAR_ALT = 100.0
# Stand-in welded terminus for the decimator tests, held well clear of the
# integer graticule (the pass force-keeps tile-seam vertices of its own).
WELD_PT = (200.0, 0.0)
# The runway's own profile at the terminus station (x == HALF): 100 m at
# station 0 rising 12 m over the 1200 m axis.  Deliberately far from the
# ring's 92.0 so "which value won" is unambiguous.
PROFILE_AT_CUT = 100.0 + 12.0 * HALF / 1200.0


class _Shape:
    def __init__(self, role, polygon, *, ref=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = node_altitudes
        self.adopts_apron_grade = False
        self.is_bridge = False
        self.source_axis = None
        self.from_single_poly = True


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry()
        self.anchor = (ANCHOR_LAT, ANCHOR_LON)
        self.apt_taxi_centerlines = []
        self.crown_spines = []
        self._seam_anchor_keys = {(0, 0)}      # the ramp's trigger
        self._runway_redistributed_profiles = {
            "02/20": {
                "axis_a": (0.0, 0.0),
                "axis_d": (1200.0, 0.0),
                "fractions": [0.0, 1.0],
                "elevs": [100.0, 112.0],
                "crown_drop_m": 0.15,
            },
        }

    def m_to_ll(self, x, y):
        return (ANCHOR_LAT + float(y) / M_PER_DEG,
                ANCHOR_LON + float(x) / M_PER_DEG)

    def ll_to_m(self, lat, lon):
        return ((float(lon) - ANCHOR_LON) * M_PER_DEG,
                (float(lat) - ANCHOR_LAT) * M_PER_DEG)


def _cut_edge_alt(y):
    """The cut edge's own linear value at station ``y``."""
    return ALT_MID + (ALT_HI - ALT_LO) / 2.0 * (y / CHL)


def _runway_layout(n_parts):
    """A runway piece cut at ``x == HALF``, its 148.09 m cut-back edge
    pre-split into ``n_parts`` EQUAL parts (the densifier's own rule).

    ``n_parts`` odd ⇒ the axis (y == 0) crosses the MIDDLE sub-edge and
    the terminus is a T-vertex; even ⇒ it lands on a split vertex.
    """
    ys = [-CHL + 2.0 * CHL * k / n_parts for k in range(n_parts + 1)]
    ring = [(HALF, y) for y in ys] + [(1000.0, CHL), (1000.0, -CHL)]
    alts = [_cut_edge_alt(y) for y in ys] + [FAR_ALT, FAR_ALT]
    shape = _Shape(ROLE_RUNWAY, Polygon(ring), ref="02/20",
                   node_altitudes=alts + [alts[0]])
    return _Layout([shape]), shape


def _emit(layout, cr=CR):
    """Run the runway branch of the spine emitter on ``layout``."""
    return cr.emit_crown_spines(layout, [(0.0, 0.0)], {}, [0.0], {})


def _terminus_alt(layout):
    """Altitude the emitted spine carries at its CUT end."""
    assert layout.crown_spines, "no spine emitted"
    pts, alts = layout.crown_spines[0]
    xs = [layout.ll_to_m(la, lo)[0] for (la, lo) in pts]
    return alts[0] if xs[0] < xs[-1] else alts[-1]


def _cut_edge_vertices(shape):
    return [(x, y) for (x, y) in shape.polygon.exterior.coords[:-1]
            if abs(x - HALF) < 1e-6]


# ── W1: odd part count — the terminus is inserted as a T-vertex ──────

def test_odd_split_terminus_is_inserted_into_the_ring():
    """SPLP's parity: 3 equal parts, so ``axis ∩ cut edge`` is the MIDPOINT
    of the middle sub-edge — a T-vertex until this weld inserts it."""
    L, rwy = _runway_layout(3)
    assert len(_cut_edge_vertices(rwy)) == 4        # 3 parts, 4 vertices
    assert _emit(L) >= 1

    verts = _cut_edge_vertices(rwy)
    assert len(verts) == 5, "the terminus must join the ring"
    ys = sorted(y for (_x, y) in verts)
    assert any(abs(y) < 1e-6 for y in ys), "inserted at the axis crossing"

    # index-aligned altitude: the inserted vertex carries the EDGE's lerp.
    ring = list(rwy.polygon.exterior.coords)[:-1]
    idx = next(i for i, (x, y) in enumerate(ring)
               if abs(x - HALF) < 1e-6 and abs(y) < 1e-6)
    assert len(rwy.node_altitudes) == len(ring) + 1
    assert rwy.node_altitudes[idx] == pytest.approx(ALT_MID, abs=1e-6)


def test_odd_split_terminus_adopts_the_ring_value_not_the_profile():
    """The ring is the VALUE AUTHORITY: the crown has ramped to zero at
    the cut edge, so the spine's own profile value there is the stale
    party (SPLP: 55.60 spine vs 55.615 ring lerp)."""
    L, _rwy = _runway_layout(3)
    _emit(L)
    assert PROFILE_AT_CUT != pytest.approx(ALT_MID, abs=0.01)
    assert _terminus_alt(L) == pytest.approx(ALT_MID, abs=0.01)


def test_welded_coordinate_is_published_for_the_decimators():
    L, _rwy = _runway_layout(3)
    _emit(L)
    welds = getattr(L, "_crown_spine_weld_xy", None)
    assert welds and len(welds) == 1
    (wx, wy) = welds[0]
    assert wx == pytest.approx(HALF, abs=1e-3)
    assert wy == pytest.approx(0.0, abs=1e-3)


# ── W2: even part count — already a ring vertex ──────────────────────

def test_even_split_terminus_inserts_nothing_and_still_adopts_the_ring():
    L, rwy = _runway_layout(2)
    assert len(_cut_edge_vertices(rwy)) == 3        # 2 parts, 3 vertices
    _emit(L)
    assert len(_cut_edge_vertices(rwy)) == 3, (
        "the terminus already IS a ring vertex — nothing to insert")
    assert _terminus_alt(L) == pytest.approx(ALT_MID, abs=0.01)


# ── W1/W2 negatives ──────────────────────────────────────────────────

def test_a_point_off_every_edge_welds_nothing():
    """Interior of the runway: no host edge, so no insert and no value."""
    L, rwy = _runway_layout(3)
    before = len(rwy.polygon.exterior.coords)
    assert CR._weld_terminus_into_rings(L, 500.0, 0.0) is None
    assert len(rwy.polygon.exterior.coords) == before


def test_runway_with_no_cut_edge_emits_no_weld():
    """A runway the tile cut never touched: the spine is never re-extended,
    so there is no terminus to weld (a strict no-op)."""
    L, rwy = _runway_layout(3)
    far = [(x + 4000.0, y) for (x, y) in rwy.polygon.exterior.coords]
    rwy.polygon = Polygon(far)
    L._runway_redistributed_profiles["02/20"]["axis_a"] = (3900.0, 0.0)
    before = len(rwy.polygon.exterior.coords)
    _emit(L)
    assert not getattr(L, "_crown_spine_weld_xy", None)
    assert len(rwy.polygon.exterior.coords) == before


# ── G: the gate ──────────────────────────────────────────────────────

def test_gate_off_leaves_the_terminus_unwelded_and_stale(monkeypatch):
    """OFF must reproduce the diagnosed defect exactly: no ring insert,
    and the terminus keeps the spine's own profile value."""
    monkeypatch.setenv("O4_CROWN_SPINE_SEAM_WELD", "0")
    cfg = importlib.reload(CFG)
    cr = importlib.reload(CR)
    try:
        assert cfg.CROWN_SPINE_SEAM_WELD is False
        L, rwy = _runway_layout(3)
        before = len(rwy.polygon.exterior.coords)
        cr.emit_crown_spines(L, [(0.0, 0.0)], {}, [0.0], {})
        assert len(rwy.polygon.exterior.coords) == before
        assert not getattr(L, "_crown_spine_weld_xy", None)
        pts, alts = L.crown_spines[0]
        xs = [L.ll_to_m(la, lo)[0] for (la, lo) in pts]
        term = alts[0] if xs[0] < xs[-1] else alts[-1]
        assert term == pytest.approx(PROFILE_AT_CUT, abs=0.01)
    finally:
        monkeypatch.delenv("O4_CROWN_SPINE_SEAM_WELD", raising=False)
        importlib.reload(CFG)
        importlib.reload(CR)


def test_gate_off_still_re_extends_the_spine(monkeypatch):
    """The weld gate is STRICTLY narrower than O4_CROWN_SEAM_RAMP: OFF
    must not revert the spine extension itself."""
    monkeypatch.setenv("O4_CROWN_SPINE_SEAM_WELD", "0")
    importlib.reload(CFG)
    cr = importlib.reload(CR)
    try:
        L, _rwy = _runway_layout(3)
        cr.emit_crown_spines(L, [(0.0, 0.0)], {}, [0.0], {})
        pts, _alts = L.crown_spines[0]
        xs = sorted(L.ll_to_m(la, lo)[0] for (la, lo) in pts)
        assert xs[0] == pytest.approx(HALF, abs=1e-2), (
            "the ramp ruling's re-extension is a separate feature")
    finally:
        monkeypatch.delenv("O4_CROWN_SPINE_SEAM_WELD", raising=False)
        importlib.reload(CFG)
        importlib.reload(CR)


# ── W4: neither decimator may drop the welded vertex ─────────────────

def _decimatable_runway():
    """A runway ring long enough for the emit decimator to work on, whose
    edge vertex at ``WELD_PT`` is 3D-REDUNDANT (exactly on its neighbours'
    chord, in XY and in altitude) — i.e. removable on every test the
    decimator applies.  Held well clear of the integer graticule so the
    pass's own tile-seam force-keep is not what saves it."""
    ring = [(200.0, -25.0), WELD_PT, (200.0, 25.0),
            (240.0, 25.0), (280.0, 25.0), (280.0, -25.0), (240.0, -25.0)]
    alts = [90.0, 91.0, 92.0, 92.0, 92.0, 90.0, 90.0]
    return _Shape(ROLE_RUNWAY, Polygon(ring), ref="02/20",
                  node_altitudes=alts + [alts[0]])


def _has_weld_pt(shape):
    return [p for p in shape.polygon.exterior.coords[:-1]
            if abs(p[0] - WELD_PT[0]) < 1e-6 and abs(p[1] - WELD_PT[1]) < 1e-6]


def test_emit_decimator_drops_the_redundant_vertex_without_the_weld():
    """Baseline for the next test: nothing else keeps that vertex."""
    shape = _decimatable_runway()
    ED.decimate_emit_nodes(_Layout([shape]), "TEST")
    assert not _has_weld_pt(shape), (
        "the vertex is 3D-redundant — the decimator drops it")


def test_emit_decimator_force_keeps_a_welded_terminus():
    shape = _decimatable_runway()
    L = _Layout([shape])
    L._crown_spine_weld_xy = [WELD_PT]
    ED.decimate_emit_nodes(L, "TEST")
    assert _has_weld_pt(shape), (
        "dropping the welded T-vertex re-opens the unwelded terminus — "
        "and no in-layout vote can see the spine that needs it")


# ── W3: to_osm reuses the node instead of minting a twin ─────────────

_NODE_RE = re.compile(
    r"""<node id='(-?\d+)'[^>]*lat='([^']+)' lon='([^']+)'""")
_NODE_ALT_RE = re.compile(
    r"""<node id='(-?\d+)'[^>]*?>\s*<tag k='alt_abs' v='([^']+)'""",
    re.DOTALL)
_WAY_RE = re.compile(r"<way id='(-?\d+)'[^>]*>(.*?)</way>", re.DOTALL)
_ND_RE = re.compile(r"""<nd ref='(-?\d+)'""")
_TAG_RE = re.compile(r"""<tag k='([^']+)' v='([^']+)'""")


def _emit_and_parse(layout):
    with tempfile.NamedTemporaryFile(
            mode="r", suffix=".osm", delete=False) as f:
        path = f.name
    try:
        layout.to_osm(path)
        text = Path(path).read_text()
    finally:
        Path(path).unlink()
    nodes = {int(m.group(1)): (float(m.group(2)), float(m.group(3)))
             for m in _NODE_RE.finditer(text)}
    node_alts = {int(m.group(1)): float(m.group(2))
                 for m in _NODE_ALT_RE.finditer(text)}
    ways = []
    for m in _WAY_RE.finditer(text):
        body = m.group(2)
        ways.append((int(m.group(1)),
                     [int(x) for x in _ND_RE.findall(body)],
                     dict(_TAG_RE.findall(body))))
    return nodes, ways, node_alts


# The runway ring's own value at the shared vertex, and the STALE value
# the spine would carry there without the ruling.
RING_V, SPINE_V = 92.0, 99.0


def _spine_layout():
    """One runway ring with a vertex at (5, 0), and a crown spine whose
    FIRST point is that same coordinate carrying a different value."""
    layout = PavementLayout(icao="KFAKE", anchor=(51.87, -0.37))
    ring = [(5.0, -10.0), (5.0, 0.0), (5.0, 10.0),
            (100.0, 10.0), (100.0, -10.0)]
    # Deliberately NOT on the (5,-10)->(5,10) altitude chord, so to_osm's
    # own emit-time decimation cannot claim the vertex is redundant.
    alts = [90.0, RING_V, 100.0, 100.0, 90.0]
    layout.shapes.append(BuiltShape(
        polygon=Polygon(ring), role=ROLE_RUNWAY, ref="02/20",
        node_altitudes=alts + [alts[0]]))
    layout.crown_spines = [(
        [layout.m_to_ll(5.0, 0.0), layout.m_to_ll(30.0, 0.0),
         layout.m_to_ll(60.0, 0.0)],
        [SPINE_V, 93.0, 94.0])]
    return layout


def _spine_way(ways):
    for wid, nds, tags in ways:
        if tags.get("o4_feature") == "crown_spine":
            return wid, nds
    raise AssertionError("no crown_spine way emitted")


def _runway_way(ways):
    for wid, nds, tags in ways:
        if tags.get("role") == ROLE_RUNWAY:
            return wid, nds
    raise AssertionError("no runway way emitted")


def test_to_osm_reuses_the_ring_node_for_a_coincident_spine_point():
    layout = _spine_layout()
    nodes, ways, node_alts = _emit_and_parse(layout)
    _swid, snds = _spine_way(ways)
    _rwid, rnds = _runway_way(ways)
    assert len(snds) == 3
    assert snds[0] in rnds, (
        "the spine must reference the ring's own node, not a twin")
    # exactly ONE node at that coordinate anywhere in the file
    ll = nodes[snds[0]]
    same = [n for n, p in nodes.items()
            if abs(p[0] - ll[0]) < 1e-9 and abs(p[1] - ll[1]) < 1e-9]
    assert same == [snds[0]]
    # ... and the RING's value survives, not the spine's.
    assert node_alts[snds[0]] == pytest.approx(RING_V, abs=0.005)


def test_to_osm_still_mints_nodes_for_free_spine_points():
    """Only COINCIDENT points reuse; the rest of the spine is untouched."""
    layout = _spine_layout()
    nodes, ways, node_alts = _emit_and_parse(layout)
    _swid, snds = _spine_way(ways)
    _rwid, rnds = _runway_way(ways)
    assert snds[1] not in rnds and snds[2] not in rnds
    assert node_alts[snds[1]] == pytest.approx(93.0, abs=0.005)
    assert node_alts[snds[2]] == pytest.approx(94.0, abs=0.005)


def test_to_osm_gate_off_mints_the_coincident_duplicate(monkeypatch):
    """OFF is the pre-ruling emission: a LITERAL coincident duplicate node
    at the shared coordinate, carrying the spine's own stale value."""
    monkeypatch.setattr(CFG, "CROWN_SPINE_SEAM_WELD", False)
    layout = _spine_layout()
    nodes, ways, node_alts = _emit_and_parse(layout)
    _swid, snds = _spine_way(ways)
    _rwid, rnds = _runway_way(ways)
    assert snds[0] not in rnds
    ll = nodes[snds[0]]
    same = sorted(n for n, p in nodes.items()
                  if abs(p[0] - ll[0]) < 1e-9 and abs(p[1] - ll[1]) < 1e-9)
    assert len(same) == 2, "the duplicate class the ruling removes"
    assert node_alts[snds[0]] == pytest.approx(SPINE_V, abs=0.005)


def test_to_osm_without_spines_is_unchanged_by_the_gate(monkeypatch):
    layout = _spine_layout()
    layout.crown_spines = []
    on_nodes, on_ways, _ = _emit_and_parse(layout)
    monkeypatch.setattr(CFG, "CROWN_SPINE_SEAM_WELD", False)
    layout2 = _spine_layout()
    layout2.crown_spines = []
    off_nodes, off_ways, _ = _emit_and_parse(layout2)
    assert on_nodes == off_nodes
    assert on_ways == off_ways


def test_welded_coordinate_survives_to_osms_own_decimation():
    """The second decimator (to_osm's chain-aware sweep) is exempted the
    same way — a welded terminus IS redundant on its host chord."""
    layout = PavementLayout(icao="KFAKE", anchor=(51.87, -0.37))
    ring = [(5.0, -10.0), (5.0, 0.0), (5.0, 10.0),
            (100.0, 10.0), (100.0, -10.0)]
    alts = [90.0, 92.0, 94.0, 94.0, 90.0]       # (5,0) ON the chord
    layout.shapes.append(BuiltShape(
        polygon=Polygon(ring), role=ROLE_RUNWAY, ref="02/20",
        node_altitudes=alts + [alts[0]]))
    layout.crown_spines = [(
        [layout.m_to_ll(5.0, 0.0), layout.m_to_ll(30.0, 0.0),
         layout.m_to_ll(60.0, 0.0)], [92.0, 93.0, 94.0])]
    layout._crown_spine_weld_xy = [(5.0, 0.0)]
    _nodes, ways, _alts = _emit_and_parse(layout)
    _swid, snds = _spine_way(ways)
    _rwid, rnds = _runway_way(ways)
    assert snds[0] in rnds, (
        "the emit-time sweep dropped the welded vertex from the ring")
