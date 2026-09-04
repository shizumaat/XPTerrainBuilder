"""Twins for lane v2hecalemd (M5i): the structure generator joins a
tunnel's faces by the tunnel's OWN refs, and a vertex two structures pin
keeps the senior structure's datum (``precedence.toml [structures]``).

LEMD 2026-09-05 (RULINGS 05d/05e, the 5.99 m tier-8 yield): basin 22's
wall band (role ``retaining_wall``, ref ``basin_wall:22``) was joined by
ROLE to tunnel -5938 and pinned at the DEM of its projection onto the
tunnel's wall path (616.99) while the basin pinned the same vertex at its
own crest (611.00) — two hard pins, the whole IIS.  Fixed at the join;
the precedence row settles a vertex two structures GENUINELY share.
"""
from __future__ import annotations

import dataclasses as _dc

from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import (WALL_REF, reconcile_datums, structure_of,
                                                  wall_faces_of)
from auto_patch_v2.model.constraints import Diff, Pin, Source
from auto_patch_v2.model.planar import Face

from test_m4 import law, synthetic  # noqa: F401  (the tunnel fixture; rootdir imports)


def test_a_basin_wall_is_never_a_tunnels_wall(synthetic, law):
    """A ``retaining_wall`` face refed ``basin_wall:<k>`` whose centroid
    lies nearest a tunnel's wall path is NOT that tunnel's wall: the join
    is by the tunnel's own ref (the oracle's population key)."""
    airport, cl2, tunnels, st, pm, stats = synthetic
    walls = wall_faces_of(pm, tunnels)
    own = [f for fs in walls.values() for f in fs]
    assert own and all(f.ref.split("#")[0] == WALL_REF for f in own)
    # a basin wall with EXACTLY a tunnel wall's geometry (the nearest path
    # is that tunnel's) — the old join claimed it
    twin = own[0]
    fid = max(pm.faces) + 1
    faces = dict(pm.faces)
    faces[fid] = Face(fid, "retaining_wall", "basin_wall:7", twin.ring, twin.holes)
    pm2 = _dc.replace(pm, faces=faces)
    walls2 = wall_faces_of(pm2, tunnels)
    assert all(f.id != fid for fs in walls2.values() for f in fs)
    assert sum(len(fs) for fs in walls2.values()) == len(own)


def test_two_structure_pins_on_one_vertex_keep_the_senior_datum(law):
    """``precedence.toml [structures] datum_order``: the tunnel's crest pin
    stays, the basin's rim pin on the same vertex is withdrawn; a basin
    pin on a vertex no tunnel pins stays; nothing else is touched."""
    assert law.tables.precedence.structures.datum_order == ("tunnel", "basin")
    tun = Source("structures", "tunnel.crest = dem (2026-09-03b L1)", ("tunnel:-1@0", "osm:-1"))
    bas = Source("structures", "basin.rim = ground (2026-09-04d)", ("basin:22", "obj:x"))
    other = Source("seams", "seam pin", ("seam",))
    rows = [Pin(5, 616.99, tun), Pin(5, 611.0, bas), Pin(6, 611.0, bas),
            Pin(7, 600.0, other), Pin(7, 601.0, tun), Diff(5, 6, 0.01, 10.0, bas)]
    out, n = reconcile_datums(rows, law)
    assert n == 1
    pins = {(r.v, r.z) for r in out if isinstance(r, Pin)}
    assert pins == {(5, 616.99), (6, 611.0), (7, 600.0), (7, 601.0)}
    assert any(isinstance(r, Diff) for r in out)
    assert structure_of(rows[0]) == "tunnel" and structure_of(rows[1]) == "basin"
    assert structure_of(rows[3]) is None


def test_generate_reports_the_withdrawn_count(synthetic, law):
    airport, cl2, tunnels, st, pm, stats = synthetic
    _cs, counts, walls = generate(pm, law, airport)
    assert counts["structure_datum_withdrawn"] == 0
    assert "structure_datum_withdrawn" in walls


# ── THE CACHED CERTIFICATE AND THE BOUNDED NEIGHBOURHOOD (iis.py) ────────

from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS  # noqa: E402
from auto_patch_v2.solve import Options  # noqa: E402
from auto_patch_v2.solve.iis import (Certificate, RowIndex, feasible,  # noqa: E402
                                     neighbourhood_certificate, row_vertices)
from auto_patch_v2.solve.relax import envelope_free, solve_relaxed  # noqa: E402
from test_relax import hangar  # noqa: F401, E402  (the hard-infeasible hangar row)


def test_the_cached_certificate_frees_rows_in_place_and_hot_starts(hangar):
    """The with-envelope model names an infeasible support; freed of those
    rows it re-runs from its basis and reports the rest — feasible on the
    hangar row (one site), and a freed row is never named again."""
    airport, pm, cs = hangar
    n = len(pm.vertices)
    c = Certificate(n, cs.rows())
    assert c.cols <= n and c.rows > 0
    sup = c.ray(60.0)
    assert sup, "the hangar row is hard-infeasible"
    assert not feasible(n, list(sup)), "the support is a certificate on its own"
    freed = c.free(sup)
    assert freed >= 1
    again = c.ray(60.0)
    assert again is None or not ({id(r) for r in again} & {id(r) for r in sup})


def test_the_neighbourhood_certificate_is_a_true_certificate_found_in_few_hops(hangar):
    """Seeded with the vertices the envelope names, the first infeasible
    neighbourhood's support is INFEASIBLE ON ITS OWN (a subset's Farkas
    certificate is the model's), every row of it lies within the hops
    grown, and the trace records the LPs run."""
    airport, pm, cs = hangar
    n = len(pm.vertices)
    sup0 = Certificate(n, cs.rows()).ray(60.0)
    seed = {v for r in sup0 for v in row_vertices(r)}
    free = envelope_free(cs)
    index = RowIndex(free.rows())
    trace: dict = {}
    sup = neighbourhood_certificate(n, index, seed, trace=trace)
    assert sup, trace
    assert not feasible(n, list(sup))
    hops = trace["hops"]
    V, rows_in = index.neighbourhood(seed, hops)
    ids = {id(r) for r in rows_in}
    assert all(id(r) in ids for r in sup)
    assert trace["lps"] and trace["lps"][-1]["infeasible"] and trace["lps"][-1]["hops"] == hops
    # every row excluded stays out of a later neighbourhood
    _V2, rows2 = index.neighbourhood(seed, hops, exclude={id(r) for r in sup})
    assert not ({id(r) for r in rows2} & {id(r) for r in sup})


def test_the_last_resort_reports_its_certificate_path(hangar):
    airport, pm, cs = hangar
    from auto_patch_v2.law import Law
    law = Law.for_airport("ZZZZ")
    sol, rep, cs2 = solve_relaxed(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert sol is not None and rep.applied
    kinds = [c["kind"] for c in rep.certificates]
    assert kinds[0] == "cached_envelope"
    assert kinds[1] in ("neighbourhood", "whole_model")
    assert rep.as_dict()["certificates"] == rep.certificates
