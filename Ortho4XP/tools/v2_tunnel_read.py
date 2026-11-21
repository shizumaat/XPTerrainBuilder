"""THE TUNNEL READ OF A CAPTURE (promoted from lanes lkrdue2 / ltunnel2,
#2221): replay a ``v2_solve_replay`` capture's planar stage on THIS tree
and print, as JSON, what the tunnel pipeline made of every mapped bore —
the pack portals and the bore ends at grade (``airport/portal_objects``),
the portal-reader refusals, §34 (12) (5)'s witness verdict per bore
(``planar/structure_service``), the mouths ``structure_approach.mouths``
kept, the Tunnel structures and object floors in the planar map, and a
digest of the map (faces + vertex positions) for an identity check.

    cd Ortho4XP && venv/bin/python tools/v2_tunnel_read.py DIR/ICAO.pkl > OUT.json

Reads only; writes nothing.  Run from ``Ortho4XP/``.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import inspect
import io
import json
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
_ROOT = os.getcwd()
sys.path[:0] = [os.path.join(_ROOT, "tools"), os.path.join(_ROOT, "src")]

_SEEN: dict = {"witness": [], "mouths": {}}


def _instrument():
    """Wrap the three readers whose verdicts the planar map does not keep."""
    B = importlib.import_module("auto_patch_v2.planar.build")
    SS = importlib.import_module("auto_patch_v2.planar.structure_service")
    SA = importlib.import_module("auto_patch_v2.planar.structure_approach")
    ST = importlib.import_module("auto_patch_v2.planar.structures")
    build, witness, mouths = B.build, SS.terrain_tunnel_witness, SA.mouths

    def _build(*a, **k):
        r = build(*a, **k)
        _SEEN["ps"] = r[1]
        return r

    def _witness(*a, **k):
        f = witness(*a, **k)

        def g(bore):
            r = f(bore)
            _SEEN["witness"].append(["+".join(str(w.id) for w in bore.ways),
                                     round(bore.line.length, 1), r[0], r[1][:300]])
            return r
        return g

    def _mouths(bores, osm, law, reach, on_field=None, *a, **k):
        r = mouths(bores, osm, law, reach, on_field, *a, **k)
        _SEEN["mouths"] = {
            "kept": ["%s@%.0f,%.0f" % ("+".join(str(i) for i in m.ways), m.xy[0], m.xy[1])
                     for m in r[0]],
            "dropped": [str(x)[:120] for x in r[1]],
            "no_portal": [str(x)[:250] for x in getattr(on_field, "no_portal", None) or ()],
            "not_terrain": [str(x)[:300] for x in getattr(on_field, "not_terrain", None) or ()]}
        return r
    B.build, SS.terrain_tunnel_witness = _build, _witness
    SA.mouths = ST.mouths = _mouths


def _digest(pm) -> str:
    h = hashlib.sha256()
    for f in sorted(pm.faces):
        fc = pm.faces[f]
        h.update(repr((f, getattr(fc, "ref", None), getattr(fc, "kind", None))).encode())
    for v in sorted(pm.vertices):
        xy = pm.vertices[v].xy
        h.update(repr((v, round(float(xy[0]), 3), round(float(xy[1]), 3))).encode())
    return h.hexdigest()[:16]


def main(pkl: str) -> dict:
    _instrument()
    import v2_solve_replay as R
    sig = inspect.signature(R.replay_problem).parameters
    kw = {k: v for k, v in dict(placement={}, sites=[], pad_read_only=True).items()
          if k in sig}
    with contextlib.redirect_stdout(io.StringIO()):
        res = R.replay_problem(pathlib.Path(pkl), "planar", [], None, (), **kw)
    pm, to = res["pm"], getattr(_SEEN.get("ps"), "tunnel_objects", None)
    return {
        "tunnels": [f"{t.id} ways={getattr(t, 'ways', '')}" for t in pm.structures],
        "object_floors": ["%s obj=%s zero=%.2f floor=%.2f" % (f.id, f.object_id, f.zero_z,
                                                             f.floor_z)
                          for f in getattr(pm, "object_floors", ())],
        "portals": [f"{p.object_id} way={p.way_id} {os.path.basename(p.resource)} "
                    f"depth={p.depth_m:.2f}" for p in getattr(to, "portals", ())],
        "grade_ends": [f"{g.object_id} way={g.way_id} {os.path.basename(g.resource)}"
                       for g in getattr(to, "grade_ends", ())],
        "portal_refusals": [r for r in getattr(to, "refused", ())
                            if "bore" in r or "portal" in r],
        "witness": _SEEN["witness"],
        "mouths": _SEEN["mouths"],
        "map_digest": _digest(pm),
        "counts": [len(pm.vertices), len(pm.edges), len(pm.faces)],
    }


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), indent=1))
