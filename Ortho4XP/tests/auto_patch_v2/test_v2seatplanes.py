"""RULINGS 2026-09-09b (5): an object's CONNECTED geometry moves as one
rigid body — one delta per connected component of the OBJ8 mesh —
per-vertex deltas exist only BETWEEN disconnected components, and a
horizontal plane is never split from the walls that carry it.

The owner's read: at HECA 190 of 391 written members left 15,729
components with no delta at all (15,716 of them FLAT), so every floor
and ceiling plane stayed at its authored y while its walls moved by up
to 45 m; at OTHH the 44 planes of the interchange drainage basins did
the same at +3.8 … +13.1 m.  The seat mints deltas only for the
THICKNESS-GATED components (the witness gate, 08-26 §2.1); the write
side must be COMPLETE.
"""
from __future__ import annotations


from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import rigid as R

THICK = 0.3          # [structures.basin] min_solid_thickness_m


def _obj(path, verts, tris) -> str:
    """Write a minimal OBJ8 with one TRIS batch over ``tris``."""
    idx = [i for t in tris for i in t]
    lines = ["I", "800", "OBJ", ""]
    for x, y, z in verts:
        lines.append(f"VT {x} {y} {z} 0 1 0 0 0")
    for i in idx:
        lines.append(f"IDX {i}")
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def _quad(v, t, x0, x1, z0, z1, y):
    """A horizontal plane (zero y-extent): four corners, two triangles."""
    n = len(v)
    v += [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    t += [(n, n + 1, n + 2), (n, n + 2, n + 3)]


def _wall(v, t, x0, x1, z, y0, y1):
    """A vertical wall panel: a real y-extent, so a genuine solid."""
    n = len(v)
    v += [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    t += [(n, n + 1, n + 2), (n, n + 2, n + 3)]


def _room(v, t, x0, x1, z0, z1, y0, y1, floor_y=None):
    """Four walls plus a horizontal floor plane, the plane authored as
    its own disjoint patch (a plane inset from the walls: the exporter's
    usual shape, and the shape that stranded at HECA/OTHH)."""
    _wall(v, t, x0, x1, z0, y0, y1)
    _wall(v, t, x0, x1, z1, y0, y1)
    n = len(v)
    v += [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]
    t += [(n, n + 1, n + 2), (n, n + 2, n + 3)]
    n = len(v)
    v += [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)]
    t += [(n, n + 1, n + 2), (n, n + 2, n + 3)]
    fy = y0 if floor_y is None else floor_y
    # inset by 5 cm so the plane is a separate connected component, as
    # the packs author it
    _quad(v, t, x0 + 0.05, x1 - 0.05, z0 + 0.05, z1 - 0.05, fy)


def _per_vertex(geom, comps, by_comp) -> dict[int, float]:
    """``engine_v2._decision``'s per-vertex map over completed deltas."""
    out: dict[int, float] = {}
    for ci, d in by_comp.items():
        for i in set(comps[ci].tris.reshape(-1).tolist()):
            out[i] = d
    return out


def test_plane_never_splits_from_the_walls_that_carry_it(tmp_path):
    """A box with a floor plane and four walls over a sloping mesh moves
    as ONE body: the seat mints a delta for the walls only (the plane is
    under the thickness gate) and the plane follows them."""
    v: list = []
    t: list = []
    _room(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4.0)
    geom = O.parse_obj8(_obj(tmp_path / "room.obj", v, t))
    comps = O.solid_components(geom)
    flat = [i for i, c in enumerate(comps) if c.max_y - c.min_y < THICK]
    thick = [i for i, c in enumerate(comps) if c.max_y - c.min_y >= THICK]
    assert flat and thick, "the fixture must carry a plane and walls"

    # what the seat produces today: only the thickness-gated components
    seat = {i: -3.5 for i in thick}
    assert set(seat) != set(range(len(comps)))          # the plane is stranded

    done = R.complete_component_deltas(geom, comps, seat)
    assert set(done) == set(range(len(comps)))          # COMPLETE
    assert set(done.values()) == {-3.5}                 # ONE rigid body
    pv = _per_vertex(geom, comps, done)
    assert len(pv) == geom.vertices.shape[0]
    assert set(pv.values()) == {-3.5}


def test_two_disconnected_boxes_get_their_own_deltas(tmp_path):
    """Per-vertex deltas exist BETWEEN disconnected components: each
    room's plane follows ITS OWN walls, not the other room's."""
    v: list = []
    t: list = []
    _room(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4.0)
    _room(v, t, 200.0, 210.0, 0.0, 8.0, 0.0, 4.0)
    geom = O.parse_obj8(_obj(tmp_path / "two.obj", v, t))
    comps = O.solid_components(geom)
    left = [i for i, c in enumerate(comps) if c.cx < 100.0]
    right = [i for i, c in enumerate(comps) if c.cx >= 100.0]
    seat = {i: -3.5 for i in left if comps[i].max_y - comps[i].min_y >= THICK}
    seat.update({i: +2.25 for i in right if comps[i].max_y - comps[i].min_y >= THICK})

    done = R.complete_component_deltas(geom, comps, seat)
    assert set(done) == set(range(len(comps)))
    assert {done[i] for i in left} == {-3.5}
    assert {done[i] for i in right} == {+2.25}
    # the two bodies are genuinely apart: two deltas in one file
    assert len({round(d, 6) for d in done.values()}) == 2


def test_welded_floor_and_walls_are_one_component(tmp_path):
    """A floor welded to its walls is ONE connected component, so the
    seat already gives it one delta (the ruling's first half)."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, 0.0, 0.0, 4.0)
    _wall(v, t, 0.0, 10.0, 8.0, 0.0, 4.0)
    _quad(v, t, 0.0, 10.0, 0.0, 8.0, 0.0)      # corners coincide with the walls
    geom = O.parse_obj8(_obj(tmp_path / "welded.obj", v, t))
    comps = O.solid_components(geom)
    assert len(comps) == 1
    done = R.complete_component_deltas(geom, comps, {0: 1.75})
    assert done == {0: 1.75}


def test_ceiling_plane_follows_its_room_not_a_nearer_neighbour(tmp_path):
    """The carrier is the NEAREST component with a delta: a ceiling
    plane 5 cm under its own room's wall tops takes that room's delta
    even with another seated room 40 m away."""
    v: list = []
    t: list = []
    _room(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4.0, floor_y=4.0)     # a ceiling
    _room(v, t, 40.0, 50.0, 0.0, 8.0, 0.0, 4.0)
    geom = O.parse_obj8(_obj(tmp_path / "ceil.obj", v, t))
    comps = O.solid_components(geom)
    seat = {i: (-1.0 if comps[i].cx < 20.0 else +6.0)
            for i, c in enumerate(comps) if c.max_y - c.min_y >= THICK}
    done = R.complete_component_deltas(geom, comps, seat)
    for i, c in enumerate(comps):
        if c.max_y - c.min_y < THICK:
            assert done[i] == (-1.0 if c.cx < 20.0 else +6.0)


def test_nothing_seated_stays_nothing(tmp_path):
    """No carrier, no completion — the caller skips the resource."""
    v: list = []
    t: list = []
    _quad(v, t, 0.0, 10.0, 0.0, 8.0, 0.0)
    geom = O.parse_obj8(_obj(tmp_path / "plane.obj", v, t))
    comps = O.solid_components(geom)
    assert R.complete_component_deltas(geom, comps, {}) == {}


def test_out_of_range_component_indices_are_dropped(tmp_path):
    v: list = []
    t: list = []
    _room(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4.0)
    geom = O.parse_obj8(_obj(tmp_path / "r.obj", v, t))
    comps = O.solid_components(geom)
    done = R.complete_component_deltas(geom, comps, {0: 2.0, 999: 9.0, -1: 8.0})
    assert set(done) == set(range(len(comps)))
    assert set(done.values()) == {2.0}


def test_a_held_component_is_never_completed(tmp_path):
    """A component the seat RULED to stay — a facility cluster (05p), a
    cluster under ``min_delta_m`` (08d d), an A3 refusal — keeps its
    authored y: the completion covers only what the seat never
    considered, and a held component carries nothing with it."""
    v: list = []
    t: list = []
    _room(v, t, 0.0, 10.0, 0.0, 8.0, 0.0, 4.0)          # the held room
    _room(v, t, 200.0, 210.0, 0.0, 8.0, 0.0, 4.0)       # the seated room
    geom = O.parse_obj8(_obj(tmp_path / "held.obj", v, t))
    comps = O.solid_components(geom)
    walls = [i for i, c in enumerate(comps) if c.max_y - c.min_y >= THICK]
    planes = [i for i, c in enumerate(comps) if c.max_y - c.min_y < THICK]
    stays = {min(walls, key=lambda i: comps[i].cx)}      # the seat: this one stays
    seat = {i: -3.5 for i in walls if i not in stays}

    held_room = min(comps[i].cx for i in stays)
    done = R.complete_component_deltas(geom, comps, seat, stays)
    assert stays.isdisjoint(done)                       # never given a delta
    assert set(done.values()) == {-3.5}
    for i in planes:
        if abs(comps[i].cx - held_room) < 50.0:
            # its nearest carrier STAYS, so the plane stays with its walls
            assert i not in done
        else:
            assert done[i] == -3.5
