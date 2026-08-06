"""FLEX AUDIT — where the runway flexed, what grade were the feeding
taxiways at, and how much slack did the least-slack one have?

Compares a flex-ON patch against a flex-OFF patch of the same airport:

1. Flex displacement map: runway-family node values ON vs OFF, matched
   by rounded lat/lon (geometry is flex-independent).
2. For each flexed cluster (|d| >= 0.10 m, coarse ~100 m bins): the taxi
   axes passing within 60 m (from the ON patch's exact-axes sidecar);
   for each, the max emitted grade along the axis within 200 m of the
   spot vs that axis's declared cap.  The LEAST-SLACK axis is reported
   (cap − grade, smallest first) — a MEASUREMENT, not a verdict.

THIS TOOL DOES NOT ADJUDICATE FLEX-LAST (RULINGS 2026-08-06, binding
point 2).  It used to print ``<< TAXI NOT AT CAP`` whenever the reported
slack exceeded a hard-coded 0.003, a number that appears nowhere in
``auto_patch.config`` and is not the flex materiality floor
(``RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M``).  The FLEX-LAST law lives in
``runway_redistribute.flex_slack_at`` / ``_largest_lawful_move``; the
numbers below are the inputs to that ruling, not the ruling.

Usage:
    venv/bin/python tools/flex_audit.py A.osm B.osm
        [--roles runway|all] [--tol M] [--map-only]

``--roles all`` widens step 1's displacement map from the runway family
to EVERY emitted role, and ``--map-only`` stops after it — that is the
"did this change move the surface, and by how much" reading (cycle-5
canyon-flex round: the plateau-unchanged acceptance), reported as the
count over ``--tol`` (default 0.10 m; pass the 0.01 m materiality floor
for an acceptance read), the worst displacement and the p50/p95.

FRAMES.  The header stamps both patches' provenance sha + dirty flag (so
an A/B ACROSS two source trees is distinguishable from one WITHIN a
tree), the lat/lon rounding the node join uses, and — for step 2 — how
many axes loaded and under WHICH sidecar spelling.  ``axes_exact`` is the
law spelling (``check_grade.SIDECAR_LAW_KEYS``); ``axes`` is classified
LEGACY evidence and its caps come from a hard-coded table inside
``verification.taxi_axes_ll`` that ignores both the ``TAXI_GRADE_BY_WIDTH``
gate and the region ruleset, so on an FAA airport with code-A/B taxiways
it reports 3.0 % where the law caps at 1.5 %.  Reading it silently would
be a wrong cap under a right-looking number.

Step 2 needs the ON patch's ``.axes.json`` sidecar (every emit writes one
since 2026-08-05; it used to require O4_LOG_VERBOSITY=1).  Its absence is
an announced SKIP, and a sidecar that yields ZERO axes is a REFUSAL —
never "no taxi axis nearby" printed for every cluster, which reads as an
exculpatory finding.  ``--map-only`` does not read the sidecar, so two
patches without sidecars still compare.

Found the 2026-07-06 HECA over-flex: 17.8 m one-sided profile drops
(sequential rounds let the first runway absorb the whole inter-runway
deficit) and a 16.6 m flex whose least-slack taxi axis had +0.45% slack.
"""
import json
import math
import os
import re
import sys
from collections import defaultdict

RUNWAY_ROLES = {"runway", "runway_crossing"}
METERS_PER_DEG_LAT = 111320.0

#: Sidecar spellings for the taxi axes, LAW FIRST.  ``axes_exact`` is the
#: law key (``check_grade.SIDECAR_LAW_KEYS``); ``axes`` is legacy evidence
#: (``check_grade.SIDECAR_EVIDENCE_KEYS``) whose caps come from a private
#: table, not from ``config.taxi_grade_cap_for_letter``; ``taxi_axes`` has
#: never been a sidecar key at all and is kept only so a hand-made fixture
#: from before the rename still reads.
AXES_KEYS = ("axes_exact", "axes", "taxi_axes")
AXES_KEY_STATUS = {
    "axes_exact": "LAW (check_grade.SIDECAR_LAW_KEYS)",
    "axes": "LEGACY EVIDENCE — caps from verification.taxi_axes_ll's private "
            "table, which ignores TAXI_GRADE_BY_WIDTH and the ruleset",
    "taxi_axes": "NOT A SIDECAR KEY the emitter writes",
}
#: The node join's rounding, in decimal places of latitude/longitude.
JOIN_ROUND_DP = 6
#: How near an emitted node must be to an axis vertex to supply its value.
VALUE_SNAP_M = 1.0


def load_axes(sidecar):
    """``(axes, spelling)`` — the taxi axes under the FIRST spelling present.

    Law spelling first.  The spelling is returned so the report can stamp
    it: the two spellings do not carry the same caps, so a number quoted
    without its spelling is a number without its law.
    """
    for key in AXES_KEYS:
        v = sidecar.get(key)
        if v:
            return list(v), key
    return [], None


def patch_frame(path):
    """``(sha, dirty)`` from the patch's own provenance stamp, or ``(None,
    reason)``.  Decoded by ``auto_patch.provenance`` — the one parser
    ``tools/patch_provenance.py`` uses, never a second reader."""
    try:
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from auto_patch.provenance import parse_patch_provenance
    except Exception as exc:                            # pragma: no cover
        return None, f"parser unavailable ({exc.__class__.__name__})"
    try:
        prov = parse_patch_provenance(path)
    except Exception as exc:                            # pragma: no cover
        return None, f"unreadable ({exc.__class__.__name__})"
    if prov is None:
        return None, "no provenance stamp on the <osm> root"
    return (prov.get("sha") or "absent"), prov.get("dirty")


def load(path, roles=RUNWAY_ROLES):
    """(node values keyed by rounded lat/lon for ``roles``, all nodes).

    ``roles=None`` takes every way regardless of role — the whole-surface
    displacement map."""
    nodes = {}
    current_node = None
    node_re = re.compile(
        r"<node id='([-\d]+)'[^>]*lat='([-\d.]+)' lon='([-\d.]+)'")
    alt_re = re.compile(r"<tag k='alt_abs' v='([-\d.]+)'")
    with open(path) as fh:
        for line in fh:
            m = node_re.search(line)
            if m:
                nodes[m.group(1)] = (float(m.group(2)),
                                     float(m.group(3)), None)
                current_node = m.group(1) if "/>" not in line else None
                continue
            if current_node is not None:
                a = alt_re.search(line)
                if a:
                    lat, lon, _ = nodes[current_node]
                    nodes[current_node] = (lat, lon, a.group(1))
                if "</node>" in line:
                    current_node = None
    text = open(path).read()
    runway_values = {}
    for m in re.finditer(r"<way id='([-\d]+)'.*?</way>", text, re.S):
        tags = dict(re.findall(r"<tag k='([^']*)' v='([^']*)'", m.group(0)))
        if roles is not None and tags.get("role") not in roles:
            continue
        for nid in re.findall(r"<nd ref='([-\d]+)'", m.group(0)):
            lat, lon, alt = nodes.get(nid, (None, None, None))
            if lat is None or alt is None:
                continue
            runway_values[(round(lat, JOIN_ROUND_DP),
                           round(lon, JOIN_ROUND_DP))] = float(alt)
    return runway_values, nodes


def main() -> int:
    argv = [a for a in sys.argv[1:]]
    roles = RUNWAY_ROLES
    tol = 0.10
    map_only = False
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--roles":
            i += 1
            roles = None if argv[i] == "all" else RUNWAY_ROLES
        elif a == "--tol":
            i += 1
            tol = float(argv[i])
        elif a == "--map-only":
            map_only = True
        else:
            positional.append(a)
        i += 1
    if len(positional) < 2:
        print(__doc__)
        return 2
    on_path, off_path = positional[0], positional[1]

    # ── FRAME STAMP (RULINGS 2026-08-06 binding point 3) ──────────────
    # Both patches' source sha + dirty flag: an A/B across two trees and
    # an A/B within one tree are different measurements and must not look
    # alike in the report.
    on_sha, on_dirty = patch_frame(on_path)
    off_sha, off_dirty = patch_frame(off_path)

    def _stamp(label, path, sha, dirty):
        if sha is None:
            return f"{label} {os.path.basename(path)}: source sha {dirty}"
        flag = {"true": " DIRTY", "false": "",
                "unknown": " (dirty unknown)"}.get(dirty, f" (dirty={dirty})")
        return f"{label} {os.path.basename(path)}: source sha {sha}{flag}"

    print(_stamp("frame ON ", on_path, on_sha, on_dirty))
    print(_stamp("frame OFF", off_path, off_sha, off_dirty))
    if on_sha is not None and off_sha is not None and on_sha != off_sha:
        print("frame: the two patches carry DIFFERENT source shas — this is "
              "a cross-tree A/B")
    elif on_sha is not None and on_sha == off_sha:
        print("frame: both patches carry the SAME source sha — this is a "
              "within-tree A/B")
    print(f"join: node values matched on lat/lon rounded to "
          f"{JOIN_ROUND_DP} decimal place(s)")

    on_values, on_nodes = load(on_path, roles)
    off_values, _ = load(off_path, roles)

    what = "runway node(s)" if roles is not None else "node(s), ALL roles"
    moved = []
    for key, value in on_values.items():
        baseline = off_values.get(key)
        if baseline is not None and abs(value - baseline) >= tol:
            moved.append((key[0], key[1], value - baseline))
    matched = sum(1 for k in on_values if k in off_values)
    print(f"displacement: {len(moved)} {what} moved >= {tol:g} m "
          f"(of {matched} matched; {len(on_values)} on / "
          f"{len(off_values)} off)")
    if moved:
        worst = max(moved, key=lambda t: abs(t[2]))
        print(f"worst displacement: {worst[2]:+.2f} m at "
              f"({worst[0]:.6f},{worst[1]:.6f})")
        mags = sorted(abs(t[2]) for t in moved)
        print(f"moved |d|: p50 {mags[len(mags) // 2]:.3f} m, p95 "
              f"{mags[min(len(mags) - 1, int(0.95 * len(mags)))]:.3f} m")
    if map_only:
        return 0

    # ── STEP 2 GUARD ──────────────────────────────────────────────────
    # An absent sidecar used to raise here, AFTER step 1 had printed, with
    # no statement that step 2 never ran; a sidecar that yielded no axes
    # used to print "no taxi axis nearby" for every cluster, which READS
    # AS AN EXCULPATORY FINDING.  Both are announced now.
    side_path = on_path + ".axes.json"
    if not os.path.isfile(side_path):
        print(f"step 2 SKIPPED (no sidecar at {side_path}) — the taxi-axis "
              f"grade/cap read needs the ON patch's .axes.json")
        return 0
    try:
        with open(side_path) as fh:
            sidecar = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"step 2 SKIPPED (sidecar at {side_path} unreadable: "
              f"{exc.__class__.__name__}: {exc})")
        return 0
    axes, axes_key = load_axes(sidecar)
    if not axes:
        present = ", ".join(sorted(sidecar)) or "(no keys)"
        print(f"REFUSING step 2: the sidecar {side_path} yields ZERO taxi "
              f"axes under any of {list(AXES_KEYS)}.  Reporting 'no taxi "
              f"axis nearby' for every cluster would read as a finding when "
              f"it is a missing input.\n  sidecar keys present: {present}")
        return 1
    print(f"axes: {len(axes)} loaded from sidecar key '{axes_key}' — "
          f"{AXES_KEY_STATUS.get(axes_key, 'unclassified spelling')}")
    print(f"axis grade lookup: nearest emitted node within "
          f"{VALUE_SNAP_M:.2f} m of each axis vertex")
    mean_lat = (sum(k[0] for k in on_values) / len(on_values)
                if on_values else 0.0)
    meters_per_deg_lon = (METERS_PER_DEG_LAT
                          * math.cos(math.radians(mean_lat)))

    grid = defaultdict(list)
    for nid, (lat, lon, alt) in on_nodes.items():
        if alt is None:
            continue
        grid[(int(lat * 2000), int(lon * 2000))].append(
            (lat, lon, float(alt)))

    def value_at(lat, lon):
        best = None
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for (nlat, nlon, alt) in grid[(int(lat * 2000) + ox,
                                               int(lon * 2000) + oy)]:
                    d = math.hypot((nlat - lat) * METERS_PER_DEG_LAT,
                                   (nlon - lon) * meters_per_deg_lon)
                    if d < VALUE_SNAP_M and (best is None or d < best[0]):
                        best = (d, alt)
        return best[1] if best else None

    clusters = {}
    for (lat, lon, d) in moved:
        key = (int(lat * 1000), int(lon * 1000))
        if key not in clusters or abs(d) > abs(clusters[key][2]):
            clusters[key] = (lat, lon, d)
    print(f"{len(clusters)} flexed cluster(s); auditing worst 12 by |d|:")

    def audit_spot(spot_lat, spot_lon):
        """``(findings, diag)``.

        ``diag`` counts the stages an axis can drop out at, so an empty
        ``findings`` can be NAMED instead of collapsed into one bucket.
        The old single label "no taxi axis nearby" conflated four distinct
        states and read as an exculpatory finding in three of them.
        """
        findings = []
        diag = {"axes": len(axes), "near": 0, "segments_in_range": 0,
                "segments_valued": 0, "axes_graded": 0, "axes_no_cap": 0}
        for entry in axes:
            points, caps = entry[0], entry[1]
            near = any(
                math.hypot((p[0] - spot_lat) * METERS_PER_DEG_LAT,
                           (p[1] - spot_lon) * meters_per_deg_lon) < 60
                for p in points[::max(1, len(points) // 20)])
            if not near:
                continue
            diag["near"] += 1
            worst_grade = 0.0
            cap_at_worst = None
            graded = False
            for i in range(len(points) - 1):
                (a_lat, a_lon), (b_lat, b_lon) = points[i], points[i + 1]
                mid_d = math.hypot(
                    ((a_lat + b_lat) / 2 - spot_lat) * METERS_PER_DEG_LAT,
                    ((a_lon + b_lon) / 2 - spot_lon) * meters_per_deg_lon)
                if mid_d > 200:
                    continue
                seg = math.hypot((a_lat - b_lat) * METERS_PER_DEG_LAT,
                                 (a_lon - b_lon) * meters_per_deg_lon)
                if seg < 2:
                    continue
                diag["segments_in_range"] += 1
                va, vb = value_at(a_lat, a_lon), value_at(b_lat, b_lon)
                if va is None or vb is None:
                    continue
                diag["segments_valued"] += 1
                graded = True
                grade = abs(va - vb) / seg
                if isinstance(caps, (int, float)):
                    cap = float(caps)
                elif caps:
                    cap = caps[min(i, len(caps) - 1)]
                else:
                    cap = None
                if grade > worst_grade:
                    worst_grade = grade
                    cap_at_worst = cap
            if graded:
                diag["axes_graded"] += 1
            if cap_at_worst is not None:
                findings.append((worst_grade, cap_at_worst))
            elif graded:
                diag["axes_no_cap"] += 1
        return findings, diag

    def no_finding_reason(diag):
        """WHICH of the four states produced no finding — each named."""
        if diag["axes"] == 0:                       # refused above; belt+braces
            return "the sidecar carried no axes at all"
        if diag["near"] == 0:
            return (f"no axis within 60 m of the spot "
                    f"({diag['axes']} axis(es) in the sidecar)")
        if diag["segments_in_range"] == 0:
            return (f"{diag['near']} axis(es) within 60 m, but none has a "
                    f"segment >= 2 m long whose midpoint is within 200 m")
        if diag["segments_valued"] == 0:
            return (f"{diag['near']} axis(es) within 60 m and "
                    f"{diag['segments_in_range']} segment(s) in range, but no "
                    f"emitted node lies within {VALUE_SNAP_M:.2f} m of any "
                    f"segment endpoint — the axis-to-node join found nothing")
        return (f"{diag['axes_graded']} axis(es) graded near the spot, but "
                f"none carries a usable cap in sidecar key '{axes_key}'")

    for (lat, lon, d) in sorted(clusters.values(),
                                key=lambda t: -abs(t[2]))[:12]:
        findings, diag = audit_spot(lat, lon)
        if not findings:
            print(f"  ({lat:.6f},{lon:.6f}) flex={d:+.2f} m — no measurement: "
                  f"{no_finding_reason(diag)}")
            continue
        findings.sort(key=lambda t: (t[1] - t[0]))
        grade, cap = findings[0]
        slack = cap - grade
        # LEAST-SLACK, not "binding": "binding" is a law word this tool does
        # not own — it is computed here as the argmin of (cap - grade) over
        # the axes near the spot, and that is exactly what it is called.
        print(f"  ({lat:.6f},{lon:.6f}) flex={d:+.2f} m — least-slack taxi "
              f"axis (of {len(findings)} measured) max grade "
              f"{grade*100:.2f}% of cap {cap*100:.2f}% "
              f"(slack {slack*100:+.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
