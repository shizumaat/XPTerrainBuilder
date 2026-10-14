#!/usr/bin/env python3
"""OBJ8 TOP SURFACE — the highest authored ``y`` of one placed object over
a square grid around a site, printed as a map (north up).

Lane ramp516 (issue #516): the question *where does this object's deck
stand, and which way does it climb?* — read off the authored file and its
DSF placement alone, with no build.  It is the raster
``airport/sunken_ramp`` judges a ramp on (``_top_surface``: the highest
solid triangle over each cell centre), so a reading here is the engine's
own.  Promoted on its second use (RULINGS ``7e90032``): the SPJC ramp end
(deck 0.2 rising 5.6 % from −12.0318118, −77.1134626) and KASE's fire
station (a roof pitching 17-22 %, not a ramp).

    venv/bin/python tools/obj8_top_surface.py OBJ LAT0 LON0 HEADING \
        SITE_LAT SITE_LON [--radius 60] [--cell 6]

``OBJ`` is the authored file (the ``.anchor_bak`` when the pack carries
one), ``LAT0 LON0 HEADING`` the placement (``Member.origin`` /
``heading_deg`` in the rebake plan).  ``.`` = no solid over the cell.
Measures no law and counts no defects.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def top_grid(obj: str, lat0: float, lon0: float, heading: float,
             site_lat: float, site_lon: float, radius: float, cell: float):
    """``(ys, xs, T)``: cell centres in metres east / north of the site
    and the top surface over them (NaN where nothing stands)."""
    from auto_patch_v2.airport import obj8
    from auto_patch_v2.airport.rebake_plan import _mpd
    from auto_patch_v2.airport.sunken_ramp import _top_surface
    g = obj8.parse_obj8(obj)
    v = g.vertices
    h = math.radians(heading)
    s0, c0 = math.sin(h), math.cos(h)
    ml, mo = _mpd(lat0)
    e = v[:, 0] * c0 - v[:, 2] * s0 + (lon0 - site_lon) * mo
    n = -v[:, 0] * s0 - v[:, 2] * c0 + (lat0 - site_lat) * ml
    tris = np.column_stack([e, n, v[:, 1]])[g.solid]
    xs = np.arange(-radius + 0.5 * cell, radius, cell)
    ys = np.arange(-radius + 0.5 * cell, radius, cell)
    T = _top_surface(tris, xs, ys, np.ones((len(ys), len(xs)), dtype=bool))
    return ys, xs, T


def render(ys, xs, T) -> list[str]:
    out = [f"rows north->south, cols west->east; cell {xs[1] - xs[0]:g} m; "
           f"the site is the centre"]
    for i in range(len(ys) - 1, -1, -1):
        out.append(f"{ys[i]:7.0f} " + "".join(
            "    . " if np.isnan(t) else f"{t:6.1f}" for t in T[i]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("obj")
    for k in ("lat0", "lon0", "heading", "site_lat", "site_lon"):
        ap.add_argument(k, type=float)
    ap.add_argument("--radius", type=float, default=60.0)
    ap.add_argument("--cell", type=float, default=6.0)
    a = ap.parse_args(argv)
    ys, xs, T = top_grid(a.obj, a.lat0, a.lon0, a.heading, a.site_lat,
                         a.site_lon, a.radius, a.cell)
    print("\n".join(render(ys, xs, T)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
