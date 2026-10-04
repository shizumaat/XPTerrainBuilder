"""Adjacent-ground LATERAL grade-law VALIDATOR (slice 4).

``verification.check_adjacent_ground`` is the DEM-based reader in lockstep
with the ``adjacent_ground`` emitter (both consume the ONE law function
``grade_law.adjacent_ground_envelope``).  These synthetic-DEM cases pin
the corridor semantics the reader must honour:

  (a) terrain inside the corridor (within tolerance) → no findings;
  (b) a fill band OWED but not emitted (DEM below the finite zone-1/2
      floor, uncovered) → flagged ``should_fill``;
  (c) a zone-3 cliff beyond the graded band (floor = None) → NOT flagged
      (the boundary-bridge killer);
  (d) a column CLAMPED by the emitter's clip (abutting/covering shape) →
      NOT flagged (the validator never demands what the emitter cannot
      emit);
  (e) the gate-off contract: ``dem=None`` → empty, and ``verify_and_log``
      grows no ``adjacent_ground`` counter when the gate is off.

The harness mirrors the runway-end-skirt validator harness: a flat
code-3 runway rect at 100 m, a monkeypatched ``elevation._sample_dem``
keyed on the lateral distance from the runway centreline edge.
"""


# ── OSM-side tear sentinel (tools/check_grade) ──────────────────────────
def _make_graded_way(elevs):
    """A synthetic closed ``adjacent_ground`` way whose ring runs along the
    x axis at 5 m spacing (metres carried as lon), ``elevs`` per vertex."""
    import sys
    sys.path.insert(0, "tools")
    from check_grade import Way
    n = len(elevs)
    nids = [f"n{i}" for i in range(n)]
    nodes = {f"n{i}": (0.0, float(i) * 5.0) for i in range(n)}  # (lat, lon=x)
    return Way(wid="w", role="graded_strip", ref="adjacent_ground",
               aeroway="aerodrome", nids=nids, elevs=elevs, tags={}), nodes


def _ll_xy(lat, lon):
    return (lon, lat)   # lon carries x-metres, lat carries y-metres


def test_osm_tear_reader_flags_submetre_vertical_edge():
    """A sub-metre edge carrying a multi-metre jump (a clip/weld tear) is
    flagged; a gently graded band at 5 m spacing is not."""
    import sys
    sys.path.insert(0, "tools")
    import check_grade as CG
    # Clean band: 3 % over each 5 m step — no tear.
    clean, cnodes = _make_graded_way([100.0, 99.85, 99.70, 99.55, 100.0])
    assert CG._check_adjacent_ground_edges([clean], cnodes, _ll_xy) == []
    # Insert a tear: a vertex 0.5 m from its neighbour, 20 m lower.
    torn, tnodes = _make_graded_way([100.0, 99.85, 80.0, 99.55, 100.0])
    tnodes["n2"] = (0.0, 5.5)         # 0.5 m past n1 → sub-metre edge
    findings = CG._check_adjacent_ground_edges([torn], tnodes, _ll_xy)
    assert findings, "a sub-metre near-vertical edge must be flagged"
    assert findings[0].de_m > 1.0
