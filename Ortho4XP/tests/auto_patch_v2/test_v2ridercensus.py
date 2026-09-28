"""Twins for THE RIDER CENSUS and the rider seat record's join (issue #31;
jetway-strip spec ``docs/specs/jetway-strip-spec.md`` §4 / §5 bar 4; lane
``ridercensus``).

Measured on HECA's shipped frame before these: the write side joined a
strip's rider to the pristine dump by its round-tripped anchor at 7 dp
and lost 6 of 105 riders (two jetways, which then read ``no_host``); it
took the datum and the gap off the FIRST face of the strip's pad ref
(gaps of 71-300 m on a four-face ref); and it wrote every non-``.agp``
rider on a strip with ANY clamp ``OBJECT_MSL`` (31 rows, 20-318 m from
the nearest clamp).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from auto_patch_v2.airport.anchor_rule import PadRing
from auto_patch_v2.airport.riders import rider_census, riders_for_dump

TOOLS = Path(__file__).resolve().parents[2] / "tools"


class _P:
    def __init__(self, lat, lon, path, kind="OBJECT", elevation=None):
        self.lat, self.lon, self.def_path = lat, lon, path
        self.heading_deg, self.kind, self.elevation = 0.0, kind, elevation


#: a two-face pad ref: the big face at 100 m, a small far face at 104 m —
#: the fold's median over both is 100.0 (6 x 100 + 2 x 104 ... sorted)
BIG = ((10.0001, 19.999), (10.0001, 20.003), (10.001, 20.003),
       (10.001, 19.999))
FAR = ((10.01, 20.01), (10.01, 20.011), (10.011, 20.011))
PADS = (PadRing("terminal", BIG, (100.0,) * 4),
        PadRing("terminal", FAR, (104.0,) * 3))


def _surf(la, lo):
    return 100.0 if lo < 20.0015 else 101.0


def test_the_join_is_the_dump_index_not_the_rounded_anchor():
    """A published anchor 5e-9 deg off its row (the projection round trip)
    that rounds to a different 7-dp key is still joined by its index."""
    rows = (_P(10.00000006, 20.00000006, "Airport/j.agp"),)
    rid = [[10.00000004, 20.00000004, "Airport/j.agp", 5.0, 0, "terminal",
            1.2]]
    strips = [{"id": "s", "pad_ref": "terminal", "riders": rid, "clamps": []}]
    got = riders_for_dump(NS(placements=rows), strips, PADS, _surf,
                          frozenset(), tol_m=0.02, gate_m=40.0)
    assert len(got) == 1 and got[0].index == 0
    # the legacy 4-element record joins by the rounded key and misses it
    legacy = [dict(strips[0], riders=[rid[0][:4]])]
    assert riders_for_dump(NS(placements=rows), legacy, PADS, _surf,
                           frozenset(), tol_m=0.02) == ()
    # an index naming a row of another resource is never trusted
    wrong = [dict(strips[0], riders=[[*rid[0][:2], "lib/x.obj", 5.0, 0]])]
    assert riders_for_dump(NS(placements=rows), wrong, PADS, _surf,
                           frozenset(), tol_m=0.02) == ()


def test_the_datum_folds_every_face_and_the_gap_is_to_the_riders_own_pad():
    rows = (_P(10.0, 20.0, "Airport/j.agp"),)
    strips = [{"id": "s", "pad_ref": "terminal", "clamps": [],
               "riders": [[10.0, 20.0, "Airport/j.agp", 5.0, 0, "terminal",
                           11.1]]}]
    r, = riders_for_dump(NS(placements=rows), strips, PADS, _surf,
                         frozenset(), tol_m=0.02, gate_m=40.0)
    # median over 4 x 100 + 3 x 104 = 100.0; the first face alone agrees
    # here, so ask the far face first as the iteration order would
    r2, = riders_for_dump(NS(placements=rows), strips, PADS[::-1], _surf,
                          frozenset(), tol_m=0.02, gate_m=40.0)
    assert r.seat_z == r2.seat_z == pytest.approx(100.0)
    # the gap is to the NEAREST face of the host ref (11 m south of BIG),
    # never to whichever face came first
    assert r.anchor_gap_m == r2.anchor_gap_m == pytest.approx(11.1, abs=0.2)
    assert r.host_pid == "terminal" and r.seat_why == "on_ground"


def test_msl_only_where_a_clamp_stands_at_the_gate():
    """§4 (1): OBJECT_MSL = datum + offset only on a CLAMPED GATE — a clamp
    within the strip depth of the rider, never any clamp on the strip."""
    rows = (_P(10.0, 20.002, "lib/near.obj"), _P(10.0, 20.0025, "lib/far.obj"))
    rid = [[10.0, 20.002, "lib/near.obj", 5.0, 0, "terminal", 0.0],
           [10.0, 20.0025, "lib/far.obj", 5.0, 1, "terminal", 0.0]]
    # one clamp 11 m from `near`, ~60 m from `far`
    strips = [{"id": "s", "pad_ref": "terminal", "riders": rid,
               "clamps": [[9.9999, 20.002, "taxi", 0.3]]}]
    got = {r.resource: r for r in riders_for_dump(
        NS(placements=rows), strips, PADS, _surf, frozenset(), tol_m=0.02,
        gate_m=40.0)}
    assert got["lib/near.obj"].seat_why == "msl_written"
    assert got["lib/near.obj"].seat_z == pytest.approx(100.0)
    rows2 = (_P(10.0, 20.002, "lib/near.obj"), _P(10.0, 20.0065, "lib/far.obj"))
    got = {r.resource: r for r in riders_for_dump(
        NS(placements=rows2), strips, PADS, _surf, frozenset(), tol_m=0.02,
        gate_m=40.0)}
    assert got["lib/far.obj"].seat_why == "on_ground"
    # gate_m None keeps the whole-strip reading
    got = {r.resource: r for r in riders_for_dump(
        NS(placements=rows2), strips, PADS, _surf, frozenset(), tol_m=0.02)}
    assert got["lib/far.obj"].seat_why == "msl_written"


def _graded_doc():
    """A graded document with one two-face pad ref and one strip."""
    vid = 0
    verts, faces = [], []
    for ring, z in ((BIG, 100.0), (FAR, 104.0)):
        ids = []
        for la, lo in ring:
            verts.append([vid, la, lo, z])
            ids.append(vid)
            vid += 1
        faces.append({"ref": "terminal", "role": "building", "ring": ids})
    # an apron sheet around it so the sampler covers the anchors
    for la, lo in ((9.99, 19.99), (9.99, 20.02), (10.02, 20.02), (10.02, 19.99)):
        verts.append([vid, la, lo, 100.0])
        vid += 1
    return {"vertices": verts, "faces": faces, "breaklines": [],
            "provenance": {"jetway_strips": [{
                "id": "s", "pad_ref": "terminal", "level": 100.0,
                "riders": [[10.0, 20.0, "Airport/Jetway/j.agp", 5.0, 0,
                            "terminal", 11.1]],
                "clamps": []}]}}


def test_the_census_tool_reads_the_one_write_side(tmp_path):
    """The promoted instrument: the §4 (2) counts come from
    ``riders_for_dump`` + ``rider_census`` (never a second seat rule), and
    the name population reads a jetway nobody hosted as ``no_host``."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import jetway_rider_census as JRC
    rows = (_P(10.0, 20.0, "Airport/Jetway/j.agp"),
            _P(10.005, 20.005, "Airport/Jetway/lost.agp"))
    doc = _graded_doc()
    rep = JRC.census(doc, NS(placements=rows), _surf, tol_m=0.02,
                     names="jetway", gate_m=40.0)
    c = rep["counts"]
    ref = rider_census(riders_for_dump(
        NS(placements=rows), doc["provenance"]["jetway_strips"],
        PADS, _surf, frozenset(), tol_m=0.02, gate_m=40.0))
    for k, v in ref.items():
        assert c[k] == v
    assert c["riders"] == 1 and c["riders_unjoined"] == 0
    pc = rep["population_counts"]
    assert (pc["population"], pc["hosted"], pc["no_host"]) == (2, 1, 1)
    lost = [x for x in rep["population"] if x["seat_why"] == "no_host"]
    assert lost[0]["resource"].endswith("lost.agp")
    # the strip table carries the pad and its seated riders
    s, = rep["strips"]
    assert s["pad_ref"] == "terminal" and s["seated"] == 1
    json.dumps(rep)                                      # --json writes it


def test_the_strip_publishes_each_riders_identity_host_and_gap():
    """The DESIGN side hands the write side the rider's dump row
    (``dsf:obj<i>``), its OWN host pad ref and its gap — the write side
    never re-derives them."""
    from auto_patch_v2.model.jetway import RiderAnchor
    from auto_patch_v2.pipeline.publication import jetway_strips_ll
    planar = NS(vertices={})
    airport = NS(frame=NS(transformers=lambda: (None, lambda x, y: (y, x))),
                 dsf_objects=(NS(id="dsf:obj17", path="Airport/j.agp",
                                 xy=(20.0, 10.0)),))
    ra = RiderAnchor("dsf:obj17", "Airport/j.agp", (20.0, 10.0), "building7",
                     3, 1.42, 5.0)
    strips = NS(riders=(ra,), strips=(NS(
        id="strip:u", pad_ref="building9", riders=("dsf:obj17",),
        region=(), vertices=()),))
    rep = NS(ran=True, strips=[{"id": "strip:u", "level": 99.0}])
    s, = jetway_strips_ll(planar, airport, strips, rep)
    assert s["riders"] == [[10.0, 20.0, "Airport/j.agp", 5.0, 17,
                            "building7", 1.42]]


def test_bar_1_reads_the_pad_plane_at_the_rider():
    """Spec-author ruling on #31 (Q-32a (d)): bar 1 is |terrain − THE PAD
    PLANE evaluated at the rider's anchor| <= 0.05 — not the pad's median
    datum.  A strip that took the plane publishes its vertices' targets ON
    the plane; a rider draped on it reads 0 off the plane while standing
    well off the median.  A gated strip (no plane) reads the host pad's own
    least-squares plane (``pad_fit``)."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import jetway_rider_census as JRC
    import math
    g = 0.01                                  # 1 % tilt along +lon
    kx = 111_320.0 * math.cos(math.radians(10.0))

    def plane(la, lo):
        return 100.0 + g * (lo - 20.0) * kx

    doc = _graded_doc()
    s = doc["provenance"]["jetway_strips"][0]
    s["plane"] = [100.0, g, 0.0, 0.0, 0.0]
    s["vertices_ll"] = [[la, lo, plane(la, lo)] for la, lo in
                        ((9.9999, 19.999), (9.9999, 20.003), (10.0001, 20.003),
                         (10.0001, 19.999))]
    rider = (10.0, 20.002)
    s["riders"] = [[rider[0], rider[1], "Airport/Jetway/j.agp", 5.0, 0,
                    "terminal", 0.1]]
    rows = (_P(rider[0], rider[1], "Airport/Jetway/j.agp"),)
    rep = JRC.census(doc, NS(placements=rows), plane, tol_m=0.02,
                     names="jetway", gate_m=40.0)
    x, = rep["population"]
    assert x["plane_src"] == "strip"
    assert abs(x["terrain_minus_plane"]) <= 1e-3
    assert abs(x["terrain_minus_datum"]) > 1.0          # 2.2 m up the tilt
    assert rep["population_counts"]["on_plane_0p05"] == 1
    assert rep["population_counts"]["on_datum_0p05"] == 0
    assert rep["counts"]["riders_on_plane_0p05"] == 1
    # gated: no plane published -> the host pad's own least-squares plane
    s["plane"], s["level"] = None, None
    rep = JRC.census(doc, NS(placements=rows), lambda la, lo: 100.0,
                     tol_m=0.02, names="jetway", gate_m=40.0)
    x, = rep["population"]
    assert x["plane_src"] == "pad_fit"
    assert x["plane_z"] is not None


def test_bar_1_reads_the_published_plane_in_the_documents_frame():
    """The strip's published ``plane`` ``(z0, gx, gy, x0, y0)`` is read in
    the graded document's own ``frame``; a GATED strip (level None) still
    publishes the frontage fit and reads ``strip_gated``."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import jetway_rider_census as JRC
    from pyproj import Transformer
    crs = "+proj=tmerc +lat_0=10 +lon_0=20 +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform

    def plane(la, lo):
        x, y = fwd(lo, la)
        return 100.0 + 0.008 * (x - 5.0) - 0.003 * (y + 2.0)

    doc = _graded_doc()
    doc["frame"] = {"crs": crs}
    s = doc["provenance"]["jetway_strips"][0]
    s["plane"] = [100.0, 0.008, -0.003, 5.0, -2.0]
    rider = (10.0, 20.002)
    s["riders"] = [[rider[0], rider[1], "Airport/Jetway/j.agp", 5.0, 0,
                    "terminal", 0.1]]
    rows = (_P(rider[0], rider[1], "Airport/Jetway/j.agp"),)
    for level, src in ((100.0, "strip"), (None, "strip_gated")):
        s["level"] = level
        rep = JRC.census(doc, NS(placements=rows), plane, tol_m=0.02,
                         names="jetway", gate_m=40.0)
        x, = rep["population"]
        assert x["plane_src"] == src
        assert abs(x["terrain_minus_plane"]) <= 1e-3
