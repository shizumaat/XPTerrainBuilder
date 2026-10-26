"""#1149: a vertex on the faces of TWO runways is read against the runway
whose own edge it lies on, in the generator and in the verify alike.

Two parallel runways 50 m apart, half width 15 m: A's shoulder face reaches
B's south edge (y = 35).  That edge vertex lies 20 m beyond A's half width
and 0 m beyond B's, so it is B's — A's cross-fall never holds it (EDTK: 12/30's
shoulder held 11/29's SE corner 1.8 m above 11/29's own level)."""

from __future__ import annotations

from types import SimpleNamespace as NS

from auto_patch_v2.constraints.runway_profile import _transverse_owners as gen_owners
from auto_patch_v2.verify.runway import _transverse_owners as verify_owners

XY = {0: (0.0, 0.0), 1: (100.0, 0.0),        # A's ridge (y = 0)
      2: (0.0, 50.0), 3: (100.0, 50.0),      # B's ridge (y = 50)
      4: (50.0, 35.0),                       # B's south edge, on A's shoulder face too
      5: (50.0, 15.0)}                       # A's own edge, A's face only
FACES = [NS(id=1, ref="A", vs=[0, 1, 4, 5]), NS(id=2, ref="B", vs=[2, 3, 4])]
HALF = {"A": 15.0, "B": 15.0}


def test_generator_gives_the_shared_edge_to_the_runway_it_bounds():
    vw = NS(xy=XY, faces_of_role=lambda roles: FACES,
            face_vertices=lambda fid: next(f.vs for f in FACES if f.id == fid))
    owners = gen_owners(vw, {"A": [[0, 1]], "B": [[2, 3]]}, HALF)
    assert owners == {4: "B"}


def test_verify_reads_the_same_owner():
    shapes = [NS(role="runway", ref=f.ref, vertex_ids=f.vs) for f in FACES]
    spines = {"A": [[(0.0, 0.0, 10.0), (100.0, 0.0, 10.0)]],
              "B": [[(0.0, 50.0, 8.0), (100.0, 50.0, 8.0)]]}
    p = NS(shapes=shapes, xy=XY)
    owners = verify_owners(p, spines, [s for v in spines.values() for s in v], HALF)
    assert owners == {4: "B"}


def test_a_runway_end_corner_stays_its_own_runways():
    """#1363 (PAAQ: 16S/34S's end corners on 16/34's shoulder face): B's
    ridge ENDS at the corner's station, so the corner has no interior foot
    on it.  The generator's clamped foot still gives it to B; the verify
    must read the same distance, or the corner falls to A's shoulder face
    and is read against A's crown — a row the generator never states."""
    xy = {**XY, 3: (49.5, 50.0)}               # B's ridge stops short of x = 50
    vw = NS(xy=xy, faces_of_role=lambda roles: FACES,
            face_vertices=lambda fid: next(f.vs for f in FACES if f.id == fid))
    assert gen_owners(vw, {"A": [[0, 1]], "B": [[2, 3]]}, HALF) == {4: "B"}
    shapes = [NS(role="runway", ref=f.ref, vertex_ids=f.vs) for f in FACES]
    spines = {"A": [[(0.0, 0.0, 10.0), (100.0, 0.0, 10.0)]],
              "B": [[(0.0, 50.0, 8.0), (49.5, 50.0, 8.0)]]}
    p = NS(shapes=shapes, xy=xy)
    owners = verify_owners(p, spines, [s for v in spines.values() for s in v], HALF)
    assert owners == {4: "B"}
