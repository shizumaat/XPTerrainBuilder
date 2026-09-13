"""§37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM
(owner RULINGS 2026-09-13j item 5, ruled 13aj; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §37 (6); lane
``v2roadramp``).

KCLT's east access road (``dsf:pol51``) stood +13.24 m over its own DEM
held by NO ROW — the objective, welded by smoothness to the airside fill
beside it, +9.71 m above its own ``preferred_road_z`` target.  The rule
gives the road a target of its own: from each airside contact,
``max(DEM(s), z_contact - road_cap * s)`` along the ROUTE, at the design-
target weight, with a HARD ceiling ``target + [cockpit] visual_m``.

The readings, all synthetic:

* the ramp DESCENDS AT THE CAP from a mouth above the DEM and follows the
  DEM from there (the reach is ``drop / cap``, walked along the route);
* the DEM is read ALONG THE ROUTE, never under the kerb — the defect this
  lane's first arm measured: a per-vertex DEM target on a road crossing a
  side slope is transversely infeasible (KCLT ``dsf:pol51`` cut 2.40 ->
  **7.43 m**), so both kerbs of a section take the centreline's value;
* a road with NO airside contact targets the DEM;
* the ceiling is HARD — its ruling head is registered in ``[design]
  hard_rulings`` — and the target SUPERSEDES ``preferred_road_z`` for
  every vertex it governs (one target per vertex, never two authorities);
* built: the road comes down to its ground and stands nowhere above
  ``target + visual_m``, where its own §37 (1) pair law admits it.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.airport.road_profile import preferred_road_z
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import GENERATORS, generate
from auto_patch_v2.airport.road_ramp import (road_ramp_targets,
                                              with_road_ramp)
from auto_patch_v2.constraints.road_ramp import (RULING, RULING_CEILING,
                                                 road_ramp_rows)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Band, Linear
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design_roles import hard_rulings, ruling_head
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot

RUN_LEN = 1200.0
PLATEAU_Z = 712.0           # the apron's ground
FALL = 0.06                 # the hillside the road descends, 6 % (under the
                            # 8 % road cap: the DEM is followable)
HILL_START = 60.0           # x at which the plateau ends
HILL_LEN = 200.0            # and the fall runs for this long
ROAD_W = 8.0                # a service-road page (KCLT's are 6.7-10.3 m)


class _Hill:
    """A plateau that falls away at ``FALL`` beyond ``HILL_START`` — the
    airport on its shelf, the access road running off it.  ``cross`` adds a
    transverse slope, so the two kerbs of one road section sit at DIFFERENT
    terrain heights (the side-slope reading)."""

    provenance = {"synthetic": "plateau + hillside"}

    def __init__(self, cross: float = 0.0) -> None:
        self.cross = cross

    def z(self, x: float, y: float) -> float:
        # ``_rect`` lays the road out along the map's y axis, so the
        # hillside falls along y and the CROSS slope runs along x
        t = min(HILL_LEN, max(0.0, y - HILL_START))
        return PLATEAU_Z - FALL * t + self.cross * (x + 200.0)

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _airport(law, dem):
    r = _rot(0.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      PLATEAU_Z, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      PLATEAU_Z, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, PLATEAU_Z, (rw,), (), (), {},
                   (), (), (), (), (), (), (), pack, dem, law.ruleset_key), r


def _cells(r, *, contact: bool = True, road_len: float = 300.0):
    """The runway, an APRON on the plateau, and a service road running from
    the apron's edge down the hillside.  ``contact=False`` moves the road
    clear of the apron: the road then has no mouth."""
    gap = 0.0 if contact else 40.0
    x0 = -20.0 + gap
    return (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH,
                                         RUN_LEN / 2, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(r, -220.0, 150.0, -20.0, 250.0), (),
             None, "D", "airside", "apron", {}),
        Cell(2, "service_road", "roadA",
             _rect(r, x0, 200.0 - ROAD_W / 2.0, x0 + road_len,
                   200.0 + ROAD_W / 2.0), (), None, "D", "groundside",
             "service_road", {}),
    )


def _map(law, airport, cells, *, ramp: bool = True):
    """The pipeline's own order at the road stage: the core's road profile,
    then §37 (6) LAST (``pipeline/build.py``).  ``ramp=False`` is THE
    CONTROL — main before this round."""
    import dataclasses as _dc
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pref, _rep, _p = preferred_road_z(airport, pm, law)
    pm = _dc.replace(pm, preferred_z=pref)
    rep: dict = {}
    if ramp:
        pm = with_road_ramp(pm, law, airport, rep)
    return pm, rep


def _road_vertices(pm):
    out: set[int] = set()
    for f in pm.faces.values():
        if f.role in ("service_road", "service_junction"):
            for ring in (f.ring, *f.holes):
                out.update(pm.ring_vertices(ring))
    return sorted(out)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def hill(law):
    airport, r = _airport(law, _Hill())
    pm, rep = _map(law, airport, _cells(r))
    return airport, pm, rep, law


# ── (1) THE RAMP DESCENDS AT THE CAP AND THEN FOLLOWS THE DEM ───────────

def test_the_target_is_the_dem_wherever_the_dem_is_reachable(hill):
    """The road's mouth is on the plateau, and the ground under the road
    falls away at 6 % — under the 8 % cap — so the ramp meets the DEM at
    once and the target IS the terrain from there on."""
    airport, pm, rep, law = hill
    tg = road_ramp_targets(pm, law, airport).targets
    assert rep["mouths"] > 0, rep
    assert rep["targets"] == len(tg) > 0
    dem = airport.dem
    far = [v for v in tg if pm.vertices[v].xy[1] > HILL_START + 60.0]
    assert far, "the fixture's road must run down the hill"
    for v in far:
        x, y = pm.vertices[v].xy
        assert tg[v] == pytest.approx(dem.z(x, y), abs=0.35), (v, tg[v])


def test_the_ramp_descends_at_the_cap_from_a_mouth_above_the_dem(law):
    """A mouth 12 m above the ground under it (an apron on fill): the
    target leaves the contact at the ROAD CAP and reaches the DEM after
    ``drop / cap``, never before — the ramp, not a cliff."""
    class _Shelf(_Hill):
        """The apron stands on a shelf 12 m over the plain, and the ground
        falls off it at 30 % — FOUR TIMES the road's own cap, so no lawful
        road follows it and the ramp is the answer."""

        def z(self, x, y):
            return PLATEAU_Z - 12.0 * min(1.0, max(0.0, y / 40.0))

    airport, r = _airport(law, _Shelf())
    pm, rep = _map(law, airport, _cells(r))
    tg = road_ramp_targets(pm, law, airport).targets
    cap = rep["cap"]
    assert cap == pytest.approx(0.08)
    ground = PLATEAU_Z - 12.0
    reach = 12.0 / cap
    for v in tg:
        x, y = pm.vertices[v].xy
        s = max(0.0, y + 20.0)                       # route distance ~ y
        envelope = max(ground, PLATEAU_Z - cap * s)
        # THE HIGHER ENVELOPE: the ramp where the ground is under it, the
        # ground where the ground is above it (§37 (6)'s ``max``)
        assert tg[v] <= max(envelope, airport.dem.z(x, y)) + 0.6, (v, s, tg[v])
        assert tg[v] >= airport.dem.z(x, y) - 0.35, (v, tg[v])
        if s > reach + 20.0:
            assert tg[v] == pytest.approx(ground, abs=0.1), (v, s, tg[v])
    assert rep["on_ramp"] > 0 and rep["max_above_dem_m"] > 1.0, rep


# ── (2) THE DEM IS READ ALONG THE ROUTE, NEVER UNDER THE KERB ───────────

def test_both_kerbs_of_a_section_take_the_centreline_value(law):
    """THE FIRST ARM'S DEFECT, twinned.  On a side slope the two kerbs of
    one 8 m section stand 0.4 m apart in terrain; a per-vertex DEM target
    is a cross-section the road's own 2 % law forbids (KCLT ``dsf:pol51``:
    a 45 m page spanning 13.6 m of DEM, cut 7.43 m).  §37 (6)'s ``DEM(s)``
    is the terrain at the ROUTE STATION, and both kerbs take it."""
    airport, r = _airport(law, _Hill(cross=0.05))     # 5 % across the road
    pm, _rep = _map(law, airport, _cells(r))
    tg = road_ramp_targets(pm, law, airport).targets
    by_station: dict[int, list[int]] = {}
    for v in tg:
        _x, y = pm.vertices[v].xy
        by_station.setdefault(int(round(y)), []).append(v)
    pairs = [vs for vs in by_station.values() if len(vs) >= 2]
    assert pairs, "the fixture must carry both kerbs at one station"
    spread_target = max(max(tg[v] for v in vs) - min(tg[v] for v in vs)
                        for vs in pairs)
    spread_dem = max(max(pm.vertices[v].dem_z for v in vs)
                     - min(pm.vertices[v].dem_z for v in vs) for vs in pairs)
    assert spread_dem > 0.3, spread_dem          # the kerbs DO differ ...
    assert spread_target < 0.1, spread_target    # ... and the target does not


# ── (3) A ROAD WITH NO AIRSIDE CONTACT TARGETS THE DEM ──────────────────

def test_a_road_with_no_contact_targets_the_dem(law):
    airport, r = _airport(law, _Hill())
    pm, rep = _map(law, airport, _cells(r, contact=False))
    tg = road_ramp_targets(pm, law, airport).targets
    assert rep["mouths"] == 0 and rep["no_contact"] == len(tg) > 0, rep
    for v in tg:
        x, y = pm.vertices[v].xy
        assert tg[v] == pytest.approx(airport.dem.z(x, y), abs=0.35)


# ── (4) THE ROWS: A DESIGN TARGET AND A HARD CEILING ────────────────────

def test_the_rows_are_a_target_and_a_ceiling_and_the_ceiling_is_hard(hill):
    airport, pm, _rep, law = hill
    rows = road_ramp_rows(pm, law, airport)
    tgt = [r for r in rows if isinstance(r, Linear)]
    ceil = [r for r in rows if isinstance(r, Band)]
    assert len(tgt) == len(ceil) == len(pm.road_ramp_z) > 0
    vis = float(law.tables.emit.cockpit.visual_m)
    for t, c in zip(tgt, ceil):
        assert t.lo == t.hi                       # a two-sided design target
        assert c.lo is None and c.hi == pytest.approx(t.hi + vis)
    # THE CEILING IS A CONSTRAINT, NOT ONE MORE WEIGHT (13aj: the objective
    # already won that contest)
    heads = hard_rulings(law)
    assert ruling_head(ceil[0]) in heads
    assert ruling_head(tgt[0]) not in heads
    assert "road_ramp" in dict(GENERATORS)


def test_the_ramp_supersedes_the_core_road_fit(hill):
    """One target per vertex: every vertex the ramp governs is GONE from
    ``preferred_z`` (§37 (6)), and no other vertex is touched."""
    airport, pm, rep, law = hill
    before, _r, _p = preferred_road_z(airport, pm, law)
    assert rep["preferred_withdrawn"] > 0, rep
    assert not (set(pm.road_ramp_z) & set(pm.preferred_z))
    # the map the publisher returned kept every OTHER preferred vertex
    kept = {v for v in before if v not in pm.road_ramp_z}
    assert set(pm.preferred_z) == kept


def test_a_bridge_deck_is_not_a_road_on_the_ground(hill, monkeypatch):
    """A mapped bridge's deck piece is a face of role ``service_road``
    named ``bridge_deck:<way>`` (``planar/structures.py``), and its level
    is STATED by the structure (§33 (4): tied to its two mapped ends, over
    the ramp's clearance).  §37 (6) must not pull it to the terrain under
    the crossing: measured on the LEMD capture, the deck refs took targets
    4.72 / 4.20 m below their core profile.  The population is read off
    the map's own ``structures`` records, never off the ref string."""
    import types
    airport, pm, _rep, law = hill
    face = next(f for f in pm.faces.values() if f.role == "service_road")
    fake = types.SimpleNamespace(decks=(types.SimpleNamespace(ref=face.ref),))
    import dataclasses as _dc
    pm2 = _dc.replace(pm, structures=(fake,))
    from auto_patch_v2.airport.road_ramp import deck_refs
    assert deck_refs(pm2) == {face.ref}
    tg2 = road_ramp_targets(pm2, law, airport).targets
    on_deck = set(pm.ring_vertices(face.ring))
    assert not (set(tg2) & on_deck), "a deck vertex took a ramp target"


def test_a_map_without_the_channel_mints_nothing(law):
    """The derivation has ONE site: a map the publisher never ran over
    (an old capture, a probe) mints no row rather than deriving a second
    time — the taxi / apron trend rule."""
    airport, r = _airport(law, _Hill())
    pm, _rep = _map(law, airport, _cells(r), ramp=False)
    assert not road_ramp_rows(pm, law, airport)


# ── (5) BUILT: THE ROAD COMES DOWN TO ITS GROUND ────────────────────────

def test_built_the_road_stands_on_its_ramp_target(law):
    airport, r = _airport(law, _Hill())
    cells = _cells(r)
    pm, _rep = _map(law, airport, cells)
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep2 = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    z = np.asarray(sol.z, float)
    vis = float(law.tables.emit.cockpit.visual_m)
    tg = pm.road_ramp_z
    worst_high = max(z[v] - tg[v] for v in tg)
    worst = max(abs(z[v] - tg[v]) for v in tg)
    assert worst_high <= vis + 0.05, worst_high      # the ceiling holds
    assert worst < 1.0, worst                        # and the target is met
    # the far end is ON the hillside, not flying over it
    far = max(tg, key=lambda v: pm.vertices[v].xy[1])
    x, y = pm.vertices[far].xy
    assert abs(z[far] - airport.dem.z(x, y)) < 1.0
