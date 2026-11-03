"""#1819: a runway whose crown spine is emitted as TWO features (a ridge
chain split at a tile seam) is read against BOTH, as the generator reads
every ridge chain.  Reading only the first priced the second piece's own
ridge vertices against the first piece's short seam stub — a pure
along-axis offset read as a 0.135 m ``crown_floor`` DEFECT (KPHX 08/26,
15.5 m east of the seam)."""

from __future__ import annotations

from types import SimpleNamespace as NS

from auto_patch_v2.law import Law
from auto_patch_v2.verify.runway import runway_transverse

# West piece ends in a 1 m N-S stub at x = 100 (the seam stitch); the east
# piece starts at x = 109.  Vertex 4 is the east piece's own ridge vertex,
# 15.5 m east of the stub and 2 cm below its crest: on its own crown.
XY = {0: (0.0, 0.5), 1: (100.0, 0.5), 2: (100.0, -0.5),
      3: (109.0, 0.0), 4: (115.5, 0.0), 5: (200.0, 0.0)}
Z = {0: 10.0, 1: 10.0, 2: 10.0, 3: 9.99, 4: 9.98, 5: 9.97}


def _patch():
    law = Law.for_airport("ZZZZ")
    def ring(ids):
        return tuple((*XY[i], Z[i]) for i in ids)
    feats = [NS(feature="crown_spine", ref="R", closed_ring=ring([0, 1, 2])),
             NS(feature="crown_spine", ref="R", closed_ring=ring([3, 4, 5]))]
    shape = NS(role="runway", ref="R", key=1, vertex_ids=(0, 1, 2, 3, 4, 5),
               code_letter="E", code_number=4)
    return NS(law=law, features=feats, shapes=[shape], xy=XY, z=Z,
              ll={v: (0.0, float(v)) for v in XY},
              publication={"runway_axes": [["R", 0, 0, 0, 0, 23.0]]},
              side=lambda role: "airside")


def test_a_split_spines_second_piece_reads_its_own_ridge():
    assert runway_transverse(_patch()) == []
