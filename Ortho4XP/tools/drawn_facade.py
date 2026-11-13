"""THE GRADED-FACADE LAYER of the drawn check (#2042): does any foot of a
graded facade hang over the ground X-Plane draws under it?

Reads only products: the WRITTEN pack DSF (each ``.fac`` polygon and the
definition it now names — a lowered copy ``<stem>__g_<hash>.fac`` or the
authored file), that file's own base (``airport/facade_seat``:
its mesh vertices at or below its ground line) and the DRAWN tile mesh.
X-Plane stands a graded facade on the ground at its first wall's centre
and keeps it flat; each foot station's float is that plane plus the
foot's height minus the drawn ground under it (``facade_seat.
station_floats``, the engine's own frame).  One SITE per facade per
``SITE_SPAN_M`` of its run (a 6 km shoreline is judged where it floats,
not as one number); FAIL when a station floats over
``facade_seat.FLOAT_TOL_M``.  Library facades and facades X-Plane builds
from wall quads are not read (``facade_seat.candidates``).
"""
from __future__ import annotations

import os
import typing as _t

from auto_patch_v2.airport import facade_seat as FS

__all__ = ["SITE_SPAN_M", "check"]

#: One drawn-check site per this many metres of a facade's run.
SITE_SPAN_M = 500.0


def _surface(mesh):
    def z(lat, lon):
        return mesh.elevation_at_or_none(lat, lon)

    def many(lats, lons):
        out = []
        for s in mesh.sample_many(lats, lons):
            out.append(None if s is None else float(s.elevation_metres))
        return out
    z.many = many
    return z


def _rows(poly, base, surface) -> list[dict[str, _t.Any]]:
    got = FS.station_floats([(n[0], n[1]) for n in poly.nodes[0]], base, surface)
    if got is None:
        return []
    anchor, az, stations = got
    spans: dict[int, list] = {}
    for st in stations:
        spans.setdefault(int(st[2] // SITE_SPAN_M), []).append(st)
    rows = []
    for k, sts in sorted(spans.items()):
        worst = max(sts, key=lambda s: s[3])
        mid = sts[len(sts) // 2]
        bad = worst[3] > FS.FLOAT_TOL_M
        rows.append({
            "site": f"facade:{poly.def_path}#{poly.index}@{int(k * SITE_SPAN_M)}m",
            "role": "FACADE", "resource": poly.def_path,
            "lat": round(mid[1], 7), "lon": round(mid[0], 7),
            "plane": round(az, 3),
            "anchor": [round(anchor[1], 7), round(anchor[0], 7)],
            "delta": round(worst[3], 2),
            "worst": [round(worst[1], 7), round(worst[0], 7)],
            "verdict": "FAIL" if bad else "PASS",
            "fails": ([f"a foot floats {worst[3]:+.2f} m over the drawn ground at "
                       f"{worst[1]:.6f}, {worst[0]:.6f} (bar {FS.FLOAT_TOL_M} m)"]
                      if bad else []),
            "objects": []})
    return rows


def check(dsf_paths: _t.Iterable[str], pack_root: str, mesh, tmp: str
          ) -> list[dict[str, _t.Any]]:
    """The facade sites of every written DSF in ``dsf_paths`` over ``mesh``
    (a ``MeshElevationSampler`` of the drawn tile)."""
    from auto_patch.dsf_reader import _dsftool_path
    from auto_patch_v2.airport import dsf as dsf_text
    from auto_patch_v2.airport.dsf_write import dump
    surface = _surface(mesh)
    rows: list[dict[str, _t.Any]] = []
    for path in dsf_paths:
        out = os.path.join(tmp, f"fac{len(os.listdir(tmp))}.txt")
        written = dsf_text.read_dump(dump(path, out, _dsftool_path()),
                                     accept_polygon=lambda p: p.lower().endswith(".fac"))
        for poly, _text, base in FS.candidates(written, pack_root):
            rows += _rows(poly, base, surface)
    return rows
