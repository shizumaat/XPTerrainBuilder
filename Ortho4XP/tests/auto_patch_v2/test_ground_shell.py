"""Issue #2056 (SBGL): a GROUND SHELL -- a large photo-textured skin too
flat for a terrain model, its edges dropping as a skirt -- lies flat on our
ground at a seat where no edge floats, or is hidden; seated, it never
stands over the airside surface.  Synthetic OBJ8s, no corpus."""
import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import test_terrain_model as TTM  # noqa: E402
from auto_patch_v2.airport import ground_shell as GS  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_shaped as TS  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402

SKIRT_M = 60.0


def _skin(x, z):
    """A level ground skin 1.5 m under its origin, its edges dropping 30 m
    over the last ``SKIRT_M`` (the bay's sea floor)."""
    d = TTM.HALF - max(abs(x), abs(z))
    return -1.5 if d >= SKIRT_M else -1.5 - 28.5 * (1.0 - d / SKIRT_M)


def _plate(x, z):
    return -1.5


def _ground(z):
    """The DEM under a placement at the frame origin, heading 0."""
    return lambda xs, ys: np.full(len(xs), float(z))


def _shells(path, dem):
    return GS.placement_shells([("dsf:obj1", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")],
                               lambda d: path, lambda d: parse_obj8(path), dem)


def test_a_skirted_photo_skin_is_a_ground_shell_and_no_terrain_model(tmp_path):
    path = TTM._write(tmp_path, "m.obj", _skin)
    s = GS.shape_of(path)
    assert s is not None and s.grid.relief_m >= TS.MIN_RELIEF_M
    assert TM.shape_of(path) is None


def test_a_flat_plate_an_atlas_skin_and_a_hill_are_not(tmp_path):
    assert GS.shape_of(TTM._write(tmp_path, "p.obj", _plate)) is None
    assert GS.shape_of(TTM._write(tmp_path, "a.obj", _skin, uv="atlas")) is None
    assert GS.shape_of(TTM._write(tmp_path, "h.obj", TTM._hill)) is None


def test_a_roof_over_the_ground_and_a_soft_skin_are_not(tmp_path):
    """AT GRADE: a roof stands over its origin's ground; HARD: a skin no
    wheel rolls on is scenery, not ground."""
    roof = TTM._write(tmp_path, "r.obj", lambda x, z: _skin(x, z) + 12.0)
    assert GS.shape_of(roof) is None
    soft = tmp_path / "s.obj"
    soft.write_text(open(TTM._write(tmp_path, "k.obj", _skin), encoding="utf-8").read()
                    .replace("ATTR_hard\n", ""), encoding="utf-8", newline="\n")
    assert GS.shape_of(str(soft)) is None


def test_a_skin_on_level_ground_is_seated_flush_under_its_skirts(tmp_path):
    """The no-float seat alone would stand the skirts' feet on the ground
    and the skin 28.5 m over it; the fit lays the skin on the ground."""
    m = _shells(TTM._write(tmp_path, "m.obj", _skin), _ground(4.0))["dsf:obj1"]
    assert m.ground == GS.SEATED
    assert abs(m.z0 - 5.5) < 0.05 and m.fit_m > TS.MIN_FOLLOW


def test_a_skin_no_seat_lays_flat_is_hidden_alone(tmp_path):
    """SBGL's case: the skin slants against the ground; the seat where no
    edge floats buries it -- HIDDEN, its own row only, no cut."""
    path = TTM._write(tmp_path, "m.obj", _skin)

    def tilted(xs, ys):
        return 4.0 + 0.012 * np.asarray(xs, dtype=float)
    m = _shells(path, tilted)["dsf:obj1"]
    assert m.ground == GS.HIDDEN
    airport = types.SimpleNamespace(terrain_models=(("dsf:obj1", "m.obj", m, 0.0),))
    rec, = TM.seat_records(airport)
    assert rec["seat"] == TS.HIDDEN_SEAT and "cut" not in rec


def test_a_seated_shell_never_stands_over_airside(tmp_path):
    path = TTM._write(tmp_path, "m.obj", _skin)
    m = _shells(path, _ground(4.0))["dsf:obj1"]
    rows = (("dsf:obj1", "m.obj", m, 0.0),)
    v = types.SimpleNamespace
    surf = v(faces=(v(side="airside", ring=(0,), holes=()), v(side="groundside", ring=(1,),
                                                              holes=())),
             vertices=(v(id=0, ll=(0.0, 0.0), z=3.2), v(id=1, ll=(0.001, 0.0), z=0.0)))
    capped = GS.airside_capped(rows, surf, lambda lon, lat: (lon * 1e5, lat * 1e5))
    assert abs(capped[0][2].z0 - (3.2 + 1.5)) < 1e-6
    # no airside vertex under it: unchanged
    surf2 = v(faces=surf.faces[1:], vertices=surf.vertices)
    assert GS.airside_capped(rows, surf2, lambda lon, lat: (lon, lat))[0][2] is m


def test_the_log_names_the_verdict(tmp_path):
    m = _shells(TTM._write(tmp_path, "m.obj", _skin), _ground(4.0))["dsf:obj1"]
    assert "SEATED" in GS.log_line("XXXX", [m])
    assert TM.log_line("XXXX", [m]).endswith("none")


def test_a_rider_of_a_hidden_shell_is_no_pit():
    """SBGL's fence stood on the shell 5 m under its origin: with the shell
    hidden its below-grade reading is dropped, so it is seated on its feet
    and not kept buried as a pit's solid."""
    from auto_patch_v2.airport.obj8 import FloorWitness, PlacedObject
    o = PlacedObject("dsf:obj2", "f.obj", "/f.obj", (0.0, 0.0), 0.0, 0.0, "OBJECT", 3.0,
                     object(), None, -2.5, -5.5, None, None,
                     (FloorWitness.__new__(FloorWitness),), below_grade_comps=(0, 1))
    r = GS.off_the_shell(o)
    assert r.below_grade is None and r.witnesses == () and r.below_grade_comps == ()
    assert r.solid_min_z is None and r.solid_min_depth_m is None
    assert (r.id, r.xy, r.anchor_z) == (o.id, o.xy, o.anchor_z)
