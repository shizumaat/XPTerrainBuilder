"""padspec3 scratch: v2_solve_replay with §56 (2) 4 (b) DELETED (absorb the wall-extended
routes too) — the planar / solve / emit proof of the `absorb_all` arm.
usage (from Ortho4XP/): venv/bin/python <this> --replay CAP.pkl --from classify --emit DIR [...]
(the patch is at module level so the work pool's spawned workers carry it; main is guarded)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src")); sys.path.insert(0, str(Path.cwd() / "tools"))
from auto_patch_v2.classify import road_absorb as ra
_real = ra.absorb_near_roads
def _all(cells, law, outline, **kw):
    kw["wall_extended"] = None
    return _real(cells, law, outline, **kw)
ra.absorb_near_roads = _all
if __name__ == "__main__":
    import v2_solve_replay
    sys.exit(v2_solve_replay.main())
