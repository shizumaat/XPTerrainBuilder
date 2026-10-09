"""zonefloor: pickle the EXACT arguments ``planar/overlay`` hands ``zone_regions`` on a
capture (the replay's own prelude: capture state, clusters, classify, weld) — the frame
``tests/auto_patch_v2/test_zone_floor.py`` reads.  The claim's union is input-chaotic, so
the twin needs the build's own cells, not a re-derivation of them.

    cd Ortho4XP && venv/bin/python ../docs/briefs/zonefloor/zone_args.py CAPTURE.pkl OUT.pkl
"""
import pickle
import sys
from pathlib import Path

sys.path[:0] = ["src", ".", "tools"]


class _Grabbed(Exception):
    pass


def main() -> None:
    import auto_patch_v2.planar.overlay as _ov
    import v2_solve_replay as _r
    got: dict = {}

    def _zr(cells, law, *rest):
        got["args"] = (cells, *rest)
        raise _Grabbed()
    _ov.zone_regions = _zr
    try:
        _r.replay_problem(Path(sys.argv[1]), "classify", [], None, (), placement={}, sites=[],
                          pad_read_only=True)
    except _Grabbed:
        pass
    cells, keepouts, dem, roads, _report, declared, wedge, walls = got["args"]
    with open(sys.argv[2], "wb") as fh:
        pickle.dump({"cells": cells, "keepouts": keepouts, "dem": dem, "roads": roads,
                     "declared": declared, "shore_wedge_m": wedge, "pack_walls": walls}, fh)
    print("zone_regions args ->", sys.argv[2], "cells", len(cells))


if __name__ == "__main__":
    main()
