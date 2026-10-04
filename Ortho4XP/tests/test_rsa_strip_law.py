"""RSA law round (Fable spec 2026-08-04, docs/specs/rsa-law-round-spec.md):
strip PRECEDENCE (§1, standards gap G-1 general) and the ABEAM-LONGITUDINAL
family (§2, gap G-2).

Headless: synthetic geometry and pure law calls only.  What these tests pin
is (a) that the constants say what the cited regulation says, (b) that the
GENERATION-BINDING half really binds — a patch that violates the law cannot
be emitted — and (c) that the emitter and the validator read the SAME law
function, which is the grade-law completeness standard's "twin" requirement
(docs/RULINGS.md).
"""
import math
import os
import sys


_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO, "src"), os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade as CG                                 # noqa: E402


def _straight_runway_ring(length_m=3000.0, half_width_m=22.5):
    return [(0.0, -half_width_m), (length_m, -half_width_m),
            (length_m, half_width_m), (0.0, half_width_m)]


# ── §2 constants vs the primary sources ─────────────────────────────


# ── §2 run splitting (the shared emitter/validator selection) ───────


# ── §2 the generation-binding clamp ─────────────────────────────────


# ── §1/§2: STANDING LAW (the gate is retired) ───────────────────────
# docs/RULINGS.md 2026-08-05, build-complete-then-debug: "NO GATES.
# Every believed-in law becomes standing law; O4_ law gates and their env
# overrides are DELETED as their territory is touched."  The former
# gate-OFF twins below become STANDING-LAW twins: the law is always on,
# and a layout with no runway geometry still yields no zone.


# ── §1 lockstep: emitter march and validator mirror defer together ──


# ── §2 validator twin: the reader over an emitted patch ─────────────

def _write_patch(tmp_path, band_alts, y0=20.0, step=25.0):
    """A minimal patch: one runway way + one graded_strip band whose outer
    row runs ALONG the runway inside the strip, with the given altitudes."""
    lat0, lon0 = 0.0, 0.0
    m_per_deg = math.pi * 6378137.0 / 180.0

    def _ll(x, y):
        return (y / m_per_deg + lat0, x / m_per_deg + lon0)

    nodes = []
    ways = []
    nid = [-1]

    def _way(pts, alts, role, ref):
        ids = []
        for (x, y), a in zip(pts, alts):
            nid[0] -= 1
            lat, lon = _ll(x, y)
            nodes.append(
                f"<node id='{nid[0]}' visible='true' lat='{lat:.11f}' "
                f"lon='{lon:.11f}'><tag k='alt_abs' v='{a:.2f}'/></node>")
            ids.append(nid[0])
        nid[0] -= 1
        body = "".join(f"<nd ref='{i}'/>" for i in ids + [ids[0]])
        ways.append(
            f"<way id='{nid[0]}' visible='true'>{body}"
            f"<tag k='role' v='{role}'/><tag k='ref' v='{ref}'/></way>")

    # Densified long edges, because real runway rings carry many
    # vertices and the fixture matches them.  It used to be LOAD-BEARING:
    # ``runway_axis_and_width`` was a vertex-count-weighted PCA, and a
    # 4-corner ring whose closing vertex repeated one corner tilted that
    # axis by a few milliradians.  Since #190 (ruling 2026-10-02v (7)) the
    # fit is the hull's minimum-area rectangle, so the duplicate is a
    # no-op and the densification is only realism.
    rw = []
    for i in range(21):
        rw.append((i * 150.0, -22.5))
    for i in range(21):
        rw.append(((20 - i) * 150.0, 22.5))
    _way(rw, [100.0] * len(rw), "runway", "09/27")
    n = len(band_alts)
    pts = ([(500.0 + i * step, y0) for i in range(n)]
           + [(500.0 + (n - 1 - i) * step, y0 + 8.0) for i in range(n)])
    _way(pts, list(band_alts) + list(band_alts)[::-1],
         "graded_strip", "adjacent_ground")
    out = tmp_path / "patch.osm"
    out.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
        + "\n".join(nodes) + "\n" + "\n".join(ways) + "\n</osm>\n", encoding="utf-8", newline="")
    return out


def _read_rows(path):
    nodes, ways = CG._parse_osm(path, feature_out={})
    ll_to_m = CG._ll_to_m_factory(nodes)
    return CG._check_strip_longitudinal_grade(ways, nodes, ll_to_m)


def test_reader_reads_the_strip_under_standing_law(tmp_path):
    """The former gate-off silence twin, inverted by the retirement: the
    reader now always reads, so a 40 % along-axis step inside the strip
    flags without any environment set-up."""
    patch = _write_patch(tmp_path, [100.0, 100.0, 110.0, 100.0])
    rows, pairs, _ways = _read_rows(patch)
    assert pairs > 0
    assert rows, "a 40 % along-axis step inside the strip must flag"


def test_reader_flags_an_over_cap_along_axis_pair(tmp_path):
    try:
        cg = CG
        patch = _write_patch(tmp_path, [100.0, 100.0, 110.0, 100.0])
        nodes, ways = cg._parse_osm(patch, feature_out={})
        ll_to_m = cg._ll_to_m_factory(nodes)
        rows, pairs, n_ways = cg._check_strip_longitudinal_grade(
            ways, nodes, ll_to_m)
        assert pairs > 0
        assert rows, "a 40 % along-axis step inside the strip must flag"
        assert rows[0].grade_pct > 1.5
        assert n_ways == 1
    finally:
        pass


# ── §2 completeness: the RESULTING surface, not only emitted pairs ──


