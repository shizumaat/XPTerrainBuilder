"""RULINGS 2026-09-09z (4) + 2026-09-09ac (2)/(3) — lane `v2planes`.

* **The carrier is the component the plane TOUCHES.**  09b (5) gave a
  free component the NEAREST considered component's delta; the owner's
  read of HECA's Private Hall block (143 of 461 planes) is that a plane
  always follows ITS OWN walls, held or not — so the carrier is the
  component the geometry is in CONTACT with (a carrier vertex within
  ``emit.identity.min_distinct_spacing_m`` of one of its own), the one
  it touches MOST where several do, and nearest-by-distance only when
  nothing touches at all.
* **The basin plate seat is scoped to the basin's own witness
  resource.**  ``[basin] seat = "floor_plate"`` seated EVERY member of
  the region at the deepest member's ``plate_y_m``; at LEMD that stood
  12 terminal slabs 12–17 m off their own feet (spec §11.4).  Only
  ``Basin.witness_id`` — the object whose floor plate the basin cut —
  takes the plate seat now; the rest seat by their feet.
* **``tools/seat_feet_census.py``** (the promoted ``measure6.py``).
"""
from __future__ import annotations

import json

import pytest

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import rigid as R
from auto_patch_v2.model.structures import Basin
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.build import _plate_seats


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


#: ``emit.identity.min_distinct_spacing_m`` — asserted against the law
#: table in ``test_the_contact_tolerance_is_the_identity_spacing``
SPACING = 0.5


# ── fixtures: an OBJ8 built out of quads ────────────────────────────────

def _obj(path, verts, tris) -> str:
    lines = ["I", "800", "OBJ", ""]
    for x, y, z in verts:
        lines.append(f"VT {x} {y} {z} 0 1 0 0 0")
    idx = [i for t in tris for i in t]
    for i in idx:
        lines.append(f"IDX {i}")
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def _wall(v, t, x0, x1, z, y0=0.0, y1=4.0):
    """A vertical panel across ``x0..x1`` at ``z`` — a genuine solid."""
    n = len(v)
    v += [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    t += [(n, n + 1, n + 2), (n, n + 2, n + 3)]


def _strip_plane(v, t, x0, x1, z0, z1, y, cells):
    """A horizontal plane (zero y-extent) tessellated into ``cells``
    strips along x, so it carries ``cells + 1`` vertices on EACH of its
    two long edges — the contact count the rule reads."""
    n = len(v)
    xs = [x0 + (x1 - x0) * i / cells for i in range(cells + 1)]
    for x in xs:
        v += [(x, y, z0), (x, y, z1)]
    for i in range(cells):
        a, b = n + 2 * i, n + 2 * i + 2
        t += [(a, b, b + 1), (a, b + 1, a + 1)]


def _comps(tmp_path, name, v, t):
    geom = O.parse_obj8(_obj(tmp_path / name, v, t))
    return geom, O.solid_components(geom)


def _plane_index(comps):
    flat = [i for i, c in enumerate(comps) if c.max_y - c.min_y < 1e-9]
    assert len(flat) == 1, "the fixture must carry exactly one plane"
    return flat[0]


# ── 09z (4): the carrier is the component it TOUCHES ────────────────────

def test_the_contact_tolerance_is_the_identity_spacing(law):
    """The tolerance is a LAW value the caller passes; ``rigid`` holds
    no number of its own."""
    assert law.tables.emit.identity.min_distinct_spacing_m == SPACING
    import inspect
    src = inspect.getsource(R)
    assert "min_distinct_spacing_m" in src        # named, never spelled
    assert f"{SPACING}" not in src.replace("(5)", "").replace("(4)", "")


def test_a_plane_follows_the_wall_it_shares_more_vertices_with(tmp_path):
    """A floor plane between two walls: wall A runs the plane's whole
    long edge (five contacts), wall B is a stub at one corner (one) —
    and B is the NEARER of the two.  09b (5) gave the plane B's delta;
    09z (4) gives it A's, because that is the wall carrying it."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 1.0, 8.05)        # B: the stub, 0.05 m off the far edge
    _wall(v, t, 0.0, 10.0, -0.1)       # A: the full edge, 0.10 m off
    _strip_plane(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4)
    geom, comps = _comps(tmp_path, "carried.obj", v, t)
    assert len(comps) == 3
    plane = _plane_index(comps)
    b = next(i for i, c in enumerate(comps) if abs(c.cz - 8.05) < 0.01)   # the stub
    a = next(i for i, c in enumerate(comps) if abs(c.cz + 0.10) < 0.01)   # the full edge
    seat = {b: -1.0, a: +2.0}

    # the pre-09z rule: B is nearest (0.05 < 0.10), so the plane took −1.0
    assert R.complete_component_deltas(geom, comps, seat)[plane] == -1.0
    # 09z (4): both TOUCH within the identity spacing; A touches MORE
    done = R.complete_component_deltas(geom, comps, seat, contact_tol_m=SPACING)
    assert done[plane] == +2.0
    assert set(done) == {0, 1, 2}


def test_a_canopy_that_touches_nothing_falls_back_to_the_nearest(tmp_path):
    """Nothing within the identity spacing: the carrier is the nearest
    by distance, exactly as 09b (5) ruled (a canopy on its masts, 30 m
    of open air to either wall)."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, -30.0)      # 30 m away
    _wall(v, t, 0.0, 10.0, +68.0)      # 60 m away
    _strip_plane(v, t, 0.0, 10.0, 0.0, 8.0, 6.0, 4)
    geom, comps = _comps(tmp_path, "canopy.obj", v, t)
    plane = _plane_index(comps)
    near = next(i for i, c in enumerate(comps) if abs(c.cz + 30.0) < 0.01)
    far = next(i for i, c in enumerate(comps) if abs(c.cz - 68.0) < 0.01)
    seat = {near: -1.5, far: +4.0}
    done = R.complete_component_deltas(geom, comps, seat, contact_tol_m=SPACING)
    assert done[plane] == -1.5                     # the nearest, no contact
    # and the fallback agrees with the pre-09z rule
    assert R.complete_component_deltas(geom, comps, seat)[plane] == -1.5


def test_a_plane_over_held_walls_stays_with_them(tmp_path):
    """09z (4): held or not, a plane follows its walls.  The plane
    touches only the HELD wall — so it is never given a delta, even
    though a moving wall stands 20 m away."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, -0.1)       # the held wall, touching
    _wall(v, t, 0.0, 10.0, 28.0)       # a moving wall, 20 m past the plane
    _strip_plane(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4)
    geom, comps = _comps(tmp_path, "held.obj", v, t)
    plane = _plane_index(comps)
    held_wall = next(i for i, c in enumerate(comps) if abs(c.cz + 0.10) < 0.01)
    mover = next(i for i, c in enumerate(comps) if abs(c.cz - 28.0) < 0.01)
    done = R.complete_component_deltas(geom, comps, {mover: +3.0}, held=(held_wall,),
                                       contact_tol_m=SPACING)
    assert done == {mover: +3.0}                   # the plane STAYS with its wall
    assert plane not in done


def test_the_contact_winner_is_deterministic_on_a_tie(tmp_path):
    """Equal contact counts resolve to the lowest component index, so
    the write is reproducible."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, -0.1)
    _wall(v, t, 0.0, 10.0, 8.1)
    _strip_plane(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4)
    geom, comps = _comps(tmp_path, "tie.obj", v, t)
    plane = _plane_index(comps)
    lo, hi = sorted(i for i in range(3) if i != plane)
    seat = {lo: -1.0, hi: +1.0}
    for _ in range(3):
        done = R.complete_component_deltas(geom, comps, seat, contact_tol_m=SPACING)
        assert done[plane] == seat[lo]


def test_contact_zero_keeps_the_pre_09z_rule(tmp_path):
    """``contact_tol_m = 0`` is the default and the pure-nearest rule:
    the module holds no law value of its own."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 1.0, 8.05)
    _wall(v, t, 0.0, 10.0, -0.1)
    _strip_plane(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4)
    geom, comps = _comps(tmp_path, "off.obj", v, t)
    plane = _plane_index(comps)
    b = next(i for i, c in enumerate(comps) if abs(c.cz - 8.05) < 0.01)
    a = next(i for i, c in enumerate(comps) if abs(c.cz + 0.10) < 0.01)
    seat = {b: -1.0, a: +2.0}
    assert R.complete_component_deltas(geom, comps, seat, contact_tol_m=0.0) == \
        R.complete_component_deltas(geom, comps, seat)


def test_the_engine_passes_the_identity_spacing_as_the_contact_tolerance(law):
    """The write half's caller reads the law table (no literal, no
    default): a silent revert to pure-nearest is impossible."""
    import inspect
    from auto_patch import engine_v2
    src = inspect.getsource(engine_v2)
    assert "law.tables.emit.identity.min_distinct_spacing_m" in src
    sig = inspect.signature(engine_v2._decision_from_seats)
    assert "contact_tol_m" in sig.parameters


# ── 09ac (2): the basin plate seat is the WITNESS resource's ────────────

def _basin(**kw) -> Basin:
    base = dict(id="basin:0", objects=("t4.obj",), floor_z=588.95,
                floor_ref="basin_floor:0", wall_ref="basin_wall:0",
                ring=((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)),
                plate_y_m=-7.048, member_ids=("dsf:obj0", "dsf:obj1"),
                witness_id="dsf:obj0")
    base.update(kw)
    return Basin(**base)


class _PM:
    """The planar map the plate seat reads: no structures, one basin."""

    def __init__(self, basins):
        self.structures = ()
        self.basins = tuple(basins)


def test_only_the_basins_own_witness_takes_the_plate_seat(law):
    """Two resources at ONE ``plate_y``: the object whose floor plate
    the basin cut (``witness_id``) is plate-seated onto the floor; the
    other — a terminal slab that merely shares the plate y — is not in
    the plate map at all, so it seats by its feet like any other
    resource (RULINGS 2026-09-09ac (2); LEMD's 12 claimed members)."""
    assert law.tables.structures.basin.seat == "floor_plate"
    seats = _plate_seats(_PM([_basin()]), law)
    assert set(seats) == {"dsf:obj0"}
    assert seats["dsf:obj0"][0] == pytest.approx(-7.048)
    assert "dsf:obj1" in _basin().member_ids          # still a MEMBER of the region


def test_a_basin_with_no_witness_plate_seats_nothing(law):
    """A record from before the field exists carries no witness: it
    plate-seats nobody rather than falling back to every member."""
    assert _plate_seats(_PM([_basin(witness_id="")]), law) == {}


def test_the_witness_is_the_deepest_member_the_plate_y_was_read_from():
    """``planar/basins`` records the witness at the same site it reads
    ``plate_y_m`` / ``seat_expect_m`` from — the deepest genuine solid
    — so the two can never name different objects."""
    import inspect
    from auto_patch_v2.planar import basins as B
    src = inspect.getsource(B.build_basins)
    assert "plate_y = smin_z - deepest.anchor_z - deepest.agl_m" in src
    assert "str(deepest.id)" in src


def test_the_witness_reaches_the_sidecar():
    """The publication carries it beside ``member_ids`` so an offline
    read can tell the witness from the other members."""
    import inspect
    from auto_patch_v2.pipeline import publication as P
    assert '"witness_id": b.witness_id' in inspect.getsource(P)


# ── 09ac (3): the promoted census tool ──────────────────────────────────

def _load_census():
    import importlib.util
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[2] / "tools" / "seat_feet_census.py"
    spec = importlib.util.spec_from_file_location("seat_feet_census", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FlatMesh:
    """A mesh at a constant elevation with one raised patch."""

    def __init__(self, z=100.0, bump=None):
        self.z, self.bump = z, bump

    def elevation_at_or_none(self, lat, lon):
        if self.bump and self.bump[0] <= lat <= self.bump[1]:
            return self.z + self.bump[2]
        return self.z


def test_seat_feet_census_measures_the_residual_at_the_feet(tmp_path):
    """The tool's arithmetic: |Δ| = mesh(foot) − (mesh(anchor) + y_foot
    + delta(component)).  A 4 m wall standing on flat ground with NO
    delta reads 0; the same wall with a +2 m delta reads −2."""
    M = _load_census()
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, 0.0, 0.0, 4.0)
    _obj(pack / "objects" / "hangar.obj", v, t)
    dump = tmp_path / "tile.text"
    dump.write_text("OBJECT_DEF objects/hangar.obj\n"
                    "OBJECT 0 -3.5600 40.4700 0.000\n"
                    "OBJECT_DEF lib/airport/x.obj\n"
                    "OBJECT 1 -3.5610 40.4710 0.000\n")
    defs, plc = M.read_placements(str(dump))
    assert defs == ["objects/hangar.obj", "lib/airport/x.obj"] and len(plc) == 2

    rows = M.measure(str(pack), str(dump), _FlatMesh(), {}, {})
    seated = [r for r in rows if r["kind"] == "measured"]
    assert len(seated) == 1 and seated[0]["dmax"] == pytest.approx(0.0)
    assert [r["kind"] for r in rows if r["kind"] != "measured"] == ["stock"]

    rows = M.measure(str(pack), str(dump), _FlatMesh(),
                     {"objects/hangar.obj": {0: 2.0}}, {})
    assert [r for r in rows if r["kind"] == "measured"][0]["dmax"] == pytest.approx(-2.0)


def test_seat_feet_census_reads_the_authored_file_not_the_baked_one(tmp_path):
    """Restore-before-read: an ``.anchor_bak`` beside a baked file is
    what the census measures, so a pack mid-bake still censuses the
    seat that is being judged."""
    M = _load_census()
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, 0.0, 0.0, 4.0)
    _obj(pack / "objects" / "h.obj.anchor_bak", v, t)
    v2: list = []
    t2: list = []
    _wall(v2, t2, 0.0, 10.0, 0.0, 9.0, 13.0)      # the LIVE file, baked +9 m
    _obj(pack / "objects" / "h.obj", v2, t2)
    feet = M.read_feet(str(pack), "objects/h.obj")
    assert feet["base"] == pytest.approx(0.0)      # the AUTHORED base


def test_seat_feet_census_reads_a_seat_result_or_a_replay_result(tmp_path):
    """Both spellings of the seat record, and the plate unit's delta
    standing in for a member with no part deltas."""
    M = _load_census()
    rec = {"units": [{"datum": "plate", "delta_m": 6.0,
                      "members": [{"resource": "a.obj", "part_deltas": [[0, 1, -1.5],
                                                                        [1, 1, None]]},
                                  {"resource": "b.obj", "part_deltas": []}]}]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rec))
    deltas, member = M.read_result(str(p))
    assert deltas["a.obj"] == {0: -1.5}            # a None part is NOT a delta
    assert member == {"b.obj": 6.0, "a.obj": 6.0}
    p.write_text(json.dumps({"seat": rec}))        # the replay's wrapper
    assert M.read_result(str(p))[0]["a.obj"] == {0: -1.5}


def pathlib_tmp():
    import tempfile
    import pathlib
    return pathlib.Path(tempfile.mkdtemp())


def test_seat_feet_census_never_generates_a_dsf_dump():
    """The churn ruling: the census READS the cached DSFTool dump and
    returns None when there is none — it never runs DSFTool."""
    M = _load_census()
    import inspect
    src = "".join(l for l in inspect.getsource(M).splitlines(True)
                  if not l.lstrip().startswith(("#", '"""', "*", "``")))
    # the generator (which SHELLS OUT to DSFTool) is never called here;
    # only the pure path helper that names an existing dump is
    assert "ensure_dsf_text_path" not in src
    assert "_default_pack_text_cache_path" in src
    assert M.find_dsf_dump(str(pathlib_tmp())) is None


def test_seat_feet_census_is_in_the_tool_index():
    """Owner ruling 7e90032: a tool absent from the index is absent."""
    import pathlib
    idx = pathlib.Path(__file__).resolve().parents[3] / "tools" / "INDEX.md"
    assert "seat_feet_census.py" in idx.read_text()
