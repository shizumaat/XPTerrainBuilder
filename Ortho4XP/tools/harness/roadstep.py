"""roadstep.py — the drawn gate's ROAD layer read on a PATCH's own surface
(a PREDICTION of what ``drawn_gate.py --site`` will draw), for a replay's
``--emit`` patch before any tile is built.

    venv/bin/python tools/harness/roadstep.py PATCH.osm NAME=LAT,LON[,R] [...] [--json OUT]

Each site prints the gate's verdict line and every road run over the bar
(``drawn_roads.road_layer``'s ``over_bar``, worst first), so one defect
never hides another (LEMD old terminal, 2026-11-27: a 3.33 m mouth face
hid three pad-rim steps of 0.6-1.4 m in the same circle).  The surface
is ``tools/patch_faces.PatchFaces`` (the patch's faces, 3 m stand-off;
the header's inset where no face covers); the mouths, floors and walls
the gate never judges come from the patch's ``.axes.json`` sidecar.
Promoted on its second use from a one-miss review's scratch tool
(lane llemd3)."""
from __future__ import annotations

import argparse
import json
import os
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(os.path.dirname(_TOOLS), "src"), _TOOLS,
           os.path.join(_TOOLS, "harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import drawn_roads as DR  # noqa: E402
from drawn_gate import parse_site  # noqa: E402
from patch_faces import PatchFaces  # noqa: E402

#: the faces read around a site reach this far past its radius
_MARGIN_M = 60.0


def _sidecar(patch: str) -> dict:
    for cand in (patch + ".axes.json", patch.replace(".patch.osm", ".axes.json")):
        try:
            with open(cand, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            continue
    return {}


def site_row(patch: str, site, osm_root: str, side: dict) -> dict:
    """The road layer's row for one ``(name, lat, lon, r)`` site on the
    patch surface."""
    _name, lat, lon, r = site
    pf = PatchFaces(patch, (lat, lon), r + _MARGIN_M, standoff=3.0)

    def sample(x, y):
        z = pf.elevation_at_or_none(y, x)
        return float("nan") if z is None else float(z)
    rep = DR.road_layer([site], sample, osm_root, mouths=DR.claimed_mouths(side),
                        floors=DR.floor_rings(side), walls=DR.wall_rings(side))
    return rep["sites"][0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("patch")
    ap.add_argument("sites", nargs="+", metavar="NAME=LAT,LON[,R]")
    ap.add_argument("--osm-root", default=None, help="default: the engine's OSM_data")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    if a.osm_root is None:
        import O4_File_Names as FNAMES
        a.osm_root = FNAMES.OSM_dir
    side = _sidecar(a.patch)
    rows = [site_row(a.patch, parse_site(t), a.osm_root, side) for t in a.sites]
    for r in rows:
        print(f"{r['verdict']} {r['site']}: {r['roads']} road run(s), max step "
              f"{r.get('max_step_m', '-')} m"
              + (f" @{r['lat']},{r['lon']} way {r['way']} ({r['highway']}) patch {r['drawn']}"
                 if r.get("lat") is not None else ""))
        for g in r.get("over_bar", [])[1:]:
            print(f"   also over the bar: way {g['way']} ({g['highway']}) {g['max_step_m']} m "
                  f"@{g['lat']},{g['lon']} patch {g['drawn']}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1)
    return 1 if any(r["verdict"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
