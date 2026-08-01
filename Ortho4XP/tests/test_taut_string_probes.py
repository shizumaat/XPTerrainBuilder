"""Headless tests for the two taut-string measurement probes.

Spec: ``docs/specs/taut-string-probe-spec.md`` §3.2.

* **Probe A — the mover ledger.**  Gate ``O4_STRING_MOVER_LEDGER``.  The
  ledger is opened, carried across stage boundaries and stamped by four
  module-level helpers in ``route_profile.solve`` plus one write-only
  out-parameter (``feasibility_project(probe_out=...)``).  Those are the
  WHOLE mechanism — the solve-site block only calls them — so they are
  driven here on a synthetic corridor with the REAL projection, in the
  same order the solve uses.  Gate-off arm: the helpers are no-ops on
  ``None`` and the projection with ``probe_out=None`` is byte-identical
  to the call that passes nothing at all (which is what makes the row
  fields absent with the gate off).

* **Probe B — hook-entry attribution.**  No gate: ``hard_cat`` /
  ``have_initial`` are optional passengers of ``construct_taut_strings``
  that ride the ``O4_STRING_STATE_DUMP`` pickle.  Absent when not
  supplied, verbatim when supplied.

No network, no X-Plane install, no DEM: pure arithmetic + ``tmp_path``.
"""
from __future__ import annotations

import pickle

from shapely.geometry import Polygon

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile.solve import (
    MOVER_LABELS, _mover_ledger_new, _mover_publish, _mover_rebind,
    _mover_snapshot, _mover_stamp, _mover_stamp_probe,
    _mover_stamp_rebound, is_mover_label, mover_stage_boundary)
from auto_patch.elevation_per_surface.route_profile.taut_string import (
    construct_taut_strings, substrate_fingerprint)

#: The labels a CONFLICT row may carry — the ledger closes before the
#: tail boundaries run, so a row can never name one of those.
LEDGER_LABELS = ("unchanged_since_freeze", "svc_dem_follow",
                 "proj_shape.blend", "proj_shape.sweep",
                 "proj_u.blend", "proj_u.sweep")


# ══════════════════════════════════════════════════════════════════════
# probe A
# ══════════════════════════════════════════════════════════════════════
def _corridor():
    """A 5-node chain, node 0 hard high, the rest 10 m below it.

    ``shape_constraints`` and the ``u_edges`` entry are the two graphs the
    solve projects in sequence at the spine-yield site.
    """
    elev = [110.0, 100.0, 100.0, 100.0, 100.0]
    shape_constraints = [{"edges": [(0, 1, 0.15), (1, 2, 0.15),
                                    (2, 3, 0.15), (3, 4, 0.15)]}]
    u_edges = [(1, 2, 0.15), (2, 3, 0.15), (3, 4, 0.15)]
    return elev, shape_constraints, u_edges


def _drive_ledger(elev, shape_constraints, u_edges, hard, watch,
                  svc_moved=()):
    """Exactly the solve-site sequence: open, project, stamp ×4."""
    ledger = _mover_ledger_new(watch, elev, svc_moved=svc_moved)
    feasibility_project(elev, shape_constraints, hard, probe_out=ledger)
    _mover_stamp_probe(ledger, "proj_shape.blend")
    _mover_stamp(ledger, _mover_snapshot(ledger, elev), "proj_shape.sweep")
    feasibility_project(elev, [{"edges": u_edges}], hard, probe_out=ledger)
    _mover_stamp_probe(ledger, "proj_u.blend")
    _mover_stamp(ledger, _mover_snapshot(ledger, elev), "proj_u.sweep")
    return ledger


def test_mover_ledger_off_is_inert_and_projection_identical():
    """Gate off ⇒ ``None`` everywhere ⇒ no field, no behaviour change.

    The row fields are emitted under ``if _mover is not None``; with the
    gate off the projections receive ``probe_out=None``, which must be
    byte-identical to not passing the parameter at all.
    """
    assert _mover_stamp(None, {0: 1.0}, "proj_u.sweep") == 0
    assert _mover_stamp_probe(None, "proj_u.sweep") == 0

    elev_a, sc_a, ue_a = _corridor()
    feasibility_project(elev_a, sc_a, {0})
    feasibility_project(elev_a, [{"edges": ue_a}], {0})

    elev_b, sc_b, ue_b = _corridor()
    feasibility_project(elev_b, sc_b, {0}, probe_out=None)
    feasibility_project(elev_b, [{"edges": ue_b}], {0}, probe_out=None)

    assert elev_a == elev_b, (elev_a, elev_b)


def test_mover_ledger_on_labels_are_in_the_closed_set():
    """Gate on ⇒ every watched node carries a label from the closed set,
    and the projection result is unchanged by the instrument."""
    watch = {0, 1, 2, 3, 4}

    control, sc_c, ue_c = _corridor()
    feasibility_project(control, sc_c, {0})
    feasibility_project(control, [{"edges": ue_c}], {0})

    elev, sc, ue = _corridor()
    ledger = _drive_ledger(elev, sc, ue, {0}, watch)

    assert elev == control, "the ledger moved the surface"
    assert set(ledger["label"]) == watch
    for node, label in ledger["label"].items():
        assert label in LEDGER_LABELS, (node, label)
        assert label in MOVER_LABELS, (node, label)
    # Node 1 sits one 0.15 m budget under a 10 m-higher hard anchor: the
    # first projection MUST move it, so it cannot read as unmoved.
    assert ledger["label"][1] != "unchanged_since_freeze", ledger["label"]
    # The hard anchor never moves in either projection.
    assert ledger["label"][0] == "unchanged_since_freeze"


def test_mover_ledger_stage_g_is_stamped_without_a_diff():
    """``svc_dem_follow`` is seeded from the moved set stage G already
    returns, and a later boundary overwrites it only if the node moves."""
    elev, sc, ue = _corridor()
    ledger = _drive_ledger(elev, sc, ue, {0}, {0, 1, 4}, svc_moved={0, 4})
    # Node 0 is hard: no later boundary can move it, so it keeps the
    # stage-G label it was seeded with (which is the point — stage G ran
    # BEFORE the baseline snapshot and is unreachable by any diff).
    assert ledger["label"][0] == "svc_dem_follow"
    # Node 4 was also stage-G-moved but a projection moved it again, so
    # last-writer correctly overrides the seed.
    assert ledger["label"][4] in LEDGER_LABELS
    assert ledger["label"][4] != "svc_dem_follow"
    assert ledger["label"][1] != "svc_dem_follow"


def test_mover_stamp_is_last_writer_and_exact_float_equality():
    """The stamp is a rolling diff against the PREVIOUS boundary, so the
    label always names the stage that moved the node LAST."""
    elev = [0.0, 0.0]
    ledger = _mover_ledger_new({0, 1}, elev)
    elev[0] = 1.0
    _mover_stamp(ledger, _mover_snapshot(ledger, elev), "proj_shape.blend")
    assert ledger["label"] == {0: "proj_shape.blend",
                              1: "unchanged_since_freeze"}
    elev[0] = 0.0                      # moved BACK — still a move
    _mover_stamp(ledger, _mover_snapshot(ledger, elev), "proj_u.sweep")
    assert ledger["label"][0] == "proj_u.sweep"
    # A boundary that changes nothing never re-stamps.
    assert _mover_stamp(ledger, _mover_snapshot(ledger, elev), "fp8") == 0
    assert ledger["label"][0] == "proj_u.sweep"


def test_probe_out_snapshot_is_the_blend_not_the_sweep():
    """``feasibility_project`` leaves the watch slice AT the blend/sweep
    boundary; the caller's own snapshot is the post-sweep state."""
    elev, sc, _ue = _corridor()
    probe = {"watch": {0, 1, 2, 3, 4}}
    before = list(elev)
    feasibility_project(elev, sc, {0}, probe_out=probe)
    post_blend = probe["post_blend"]
    assert set(post_blend) == probe["watch"]
    # The blend copy is a state of this call, not the caller's baseline
    # nor (necessarily) the returned state; at minimum it is a real
    # snapshot of ``elev`` taken during the call.
    assert all(isinstance(z, float) for z in post_blend.values())
    assert post_blend[0] == before[0] == elev[0]   # hard node never moves
    # Consuming it means a call that never snapshots cannot be misread.
    _mover_stamp_probe({"watch": probe["watch"],
                        "label": {}, "prev": {},
                        "post_blend": {}}, "proj_shape.blend")
    assert "post_blend" in probe


def test_probe_out_absent_snapshot_is_never_attributed():
    """An early return (no edges at all) leaves no snapshot; the stamp
    must then attribute nothing rather than reuse a stale copy."""
    elev = [1.0, 2.0]
    ledger = _mover_ledger_new({0, 1}, elev)
    feasibility_project(elev, [{"edges": []}], {0}, probe_out=ledger)
    assert "post_blend" not in ledger
    assert _mover_stamp_probe(ledger, "proj_shape.blend") == 0
    assert set(ledger["label"].values()) == {"unchanged_since_freeze"}


def test_final_projection_tail_crosses_a_rebuilt_node_space():
    """Spec amendment: the tail must survive ``final_grade_projection``'s
    node-list rebuild, which it does by CANONICAL KEY.  A watched node the
    rebuild dropped (emit decimation) must fall out of the map rather than
    be attributed to the pass."""
    elev = [10.0, 20.0, 30.0]
    ledger = _mover_ledger_new({0, 1, 2}, elev)
    ledger["key_of"] = {0: ("a",), 1: ("b",), 2: ("gone",)}
    # The rebuilt pass renumbers everything and no longer has ("gone",).
    b2i = {("b",): 0, ("a",): 1}
    idx = _mover_rebind(ledger, b2i, n=2)
    assert idx == {0: 1, 1: 0}, idx
    fp_elev = [20.0, 11.0]                 # node 0 moved 10.0 -> 11.0
    moved = _mover_stamp_rebound(ledger, fp_elev, idx, "final_proj_1")
    assert moved == 1
    assert ledger["label"][0] == "final_proj_1"
    assert ledger["label"][1] == "unchanged_since_freeze"
    assert ledger["label"][2] == "unchanged_since_freeze"   # never seen
    for label in ledger["label"].values():
        assert label in MOVER_LABELS


def test_final_projection_labels_separate_entry_from_the_pass():
    """``.entry`` is what happened BEFORE the pass; the bare label is the
    pass itself.  Both are in the closed set, and the pass counter drives
    which pass a boundary belongs to."""
    for label in ("final_proj_1.entry", "final_proj_1",
                  "final_proj_2.entry", "final_proj_2"):
        assert label in MOVER_LABELS
    elev = [0.0]
    ledger = _mover_ledger_new({0}, elev)
    ledger["key_of"] = {0: ("k",)}
    idx = _mover_rebind(ledger, {("k",): 0}, n=1)
    _mover_stamp_rebound(ledger, [1.0], idx, "final_proj_1.entry")
    assert ledger["label"][0] == "final_proj_1.entry"
    _mover_stamp_rebound(ledger, [2.0], idx, "final_proj_1")
    assert ledger["label"][0] == "final_proj_1"
    _mover_stamp_rebound(ledger, [2.0], idx, "final_proj_2.entry")
    assert ledger["label"][0] == "final_proj_1"       # nothing moved
    _mover_stamp_rebound(ledger, [3.0], idx, "final_proj_2")
    assert ledger["label"][0] == "final_proj_2"


def test_mover_publish_records_the_emitted_value_and_is_inert_off(
        monkeypatch, tmp_path):
    """The last boundary must carry the number the .osm spells: the
    uncrowned z′ the pass ended on MINUS that node's crown drop."""
    # No witness dump ⇒ ``write_string_sidecar`` writes nothing, so the
    # stand-in layout is never dereferenced.
    monkeypatch.delenv("O4_STRING_WITNESS_DUMP", raising=False)
    _mover_publish(None, object())            # gate off ⇒ no ledger ⇒ no-op
    elev = [100.0]
    ledger = _mover_ledger_new({7}, [0.0] * 8)
    ledger["key_of"] = {7: ("k",)}
    summary: dict = {}
    ledger["summary"] = summary
    ledger["pin_rows"] = [{"vertex": 7, "pin_z": 100.0,
                           "z_at_emit_copy": 100.0,
                           "last_writer": "unchanged_since_freeze"}]
    idx = _mover_rebind(ledger, {("k",): 0}, n=1)
    _mover_stamp_rebound(ledger, elev, idx, "final_proj_2")
    _mover_publish(ledger, object(), elev=[100.2], idx_map=idx,
                   crown_of={0: 0.05}, pass_no=2)
    row = ledger["pin_rows"][0]
    assert row["z_final_proj_2"] == 100.2
    assert row["crown_drop_m"] == 0.05
    assert abs(row["z_emitted"] - 100.15) < 1e-9
    counts = summary["pin_drag_counts"]
    (label, stats), = counts.items()
    assert label in MOVER_LABELS
    assert stats["n"] == 1
    assert stats["median_abs_dz_m"] == 0.0          # the emit-copy delta
    assert abs(stats["median_abs_dz_emitted_m"] - 0.15) < 1e-9


# ══════════════════════════════════════════════════════════════════════
# ROUND 2 §2 — sub-boundaries inside the ``final_proj_N.entry`` window
# ══════════════════════════════════════════════════════════════════════
def _stage_layout(z, crown=None):
    """One apron ring with per-node altitudes — the smallest layout the
    real ``_build_node_list`` / ``_seed_elevations`` pair will read."""
    from auto_patch.canonical_points import CanonicalPointRegistry
    from auto_patch.layout import BuiltShape, PavementLayout
    layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
    layout.canonical_points = CanonicalPointRegistry()
    ring = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    layout.shapes.append(BuiltShape(polygon=ring, role="apron", ref="-1",
                                    node_altitudes=list(z)))
    if crown is not None:
        layout._crown_drop_key = dict(crown)
    return layout


def _stage_ledger(layout, z0):
    """A ledger watching the apron's first ring vertex, by canonical key."""
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list)
    _nodes, b2i = _build_node_list(layout)
    key = next(k for k, i in b2i.items() if i == 0)
    ledger = _mover_ledger_new({0}, [z0])
    ledger["key_of"] = {0: key}
    layout._string_mover_ledger = ledger
    return ledger


def test_stage_boundary_is_inert_without_a_ledger():
    """The ledger only exists on the layout under
    ``O4_STRING_MOVER_LEDGER=1``; without it the seam is one getattr."""
    assert mover_stage_boundary(_stage_layout([1.0] * 4), "03_tile_cut") == 0

    class _Bare:
        pass
    assert mover_stage_boundary(_Bare(), "03_tile_cut") == 0


def test_stage_boundary_names_the_stage_that_moved_the_node():
    """The whole point: a mover inside the entry window is attributed to
    the pipeline stage that ran, not to the undifferentiated window."""
    layout = _stage_layout([100.0, 100.0, 100.0, 100.0])
    ledger = _stage_ledger(layout, 100.0)
    assert mover_stage_boundary(layout, "00_post_solve") == 0
    assert ledger["label"][0] == "unchanged_since_freeze"
    layout.shapes[0].node_altitudes[0] = 101.0        # a stage moved it
    assert mover_stage_boundary(layout, "03_tile_cut") == 1
    assert ledger["label"][0] == "final_proj_1.entry.03_tile_cut"
    assert is_mover_label(ledger["label"][0])
    # and the boundary is a boundary: re-reading the same state moves
    # nothing, so a later stage is never credited with an earlier move
    assert mover_stage_boundary(layout, "05_feature_conformance") == 0
    assert ledger["label"][0] == "final_proj_1.entry.03_tile_cut"
    assert set(ledger["stage_moves"]) == {
        "final_proj_1.entry.00_post_solve",
        "final_proj_1.entry.03_tile_cut",
        "final_proj_1.entry.05_feature_conformance"}
    # MAGNITUDES ride beside the count: a stage that "moved everything" by
    # 1e-16 is a frame artefact, not a writer, and only the size says so.
    cut = ledger["stage_moves"]["final_proj_1.entry.03_tile_cut"]
    assert cut == {"n_moved": 1, "n_watched_here": 1, "n_unresolved": 0,
                   "median_abs_dz_m": 1.0, "max_abs_dz_m": 1.0,
                   "n_over_0p01_m": 1}
    quiet = ledger["stage_moves"]["final_proj_1.entry.05_feature_conformance"]
    assert quiet["n_moved"] == 0 and quiet["max_abs_dz_m"] is None


def test_stage_boundary_reads_the_uncrowned_frame():
    """One frame for the whole tail: the layout carries the CROWNED value
    and the ledger lives in z′, so the drop is added back — exactly what
    ``final_grade_projection`` does on entry."""
    layout = _stage_layout([100.0] * 4)
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list)
    _nodes, b2i = _build_node_list(layout)
    key = next(k for k, i in b2i.items() if i == 0)
    layout._crown_drop_key = {key: 0.25}
    ledger = _stage_ledger(layout, 100.25)            # z′ = 100.0 + 0.25
    assert mover_stage_boundary(layout, "00_post_solve") == 0
    layout._crown_drop_key = {key: 0.30}              # crown changed ⇒ z′ did
    assert mover_stage_boundary(layout, "09_planarize_airside") == 1
    assert ledger["prev"][0] == 100.30


def test_stage_boundary_follows_the_pass_counter():
    """Sub-boundaries belong to the window of the NEXT pass, so a seam
    after pass 1 is never mislabelled as pass 1's entry."""
    layout = _stage_layout([100.0] * 4)
    ledger = _stage_ledger(layout, 100.0)
    ledger["n_final_passes"] = 1
    layout.shapes[0].node_altitudes[0] = 101.0
    assert mover_stage_boundary(layout, "18_emit_decimate") == 1
    assert ledger["label"][0] == "final_proj_2.entry.18_emit_decimate"
    assert is_mover_label(ledger["label"][0])


def _unseeded_shape(layout, z=50.0):
    """A shape whose corners the canonical registry has NEVER seen —
    what every post-solve pipeline seam holds (tile cut, decimation and
    conformance all mint vertices after the solve interned its own)."""
    from auto_patch.layout import BuiltShape
    layout.shapes.append(BuiltShape(
        polygon=Polygon([(100.0, 100.0), (110.0, 100.0),
                         (110.0, 110.0), (100.0, 110.0)]),
        role="apron", ref="-2", node_altitudes=[z] * 4))
    return layout


def test_stage_boundary_interns_nothing_and_publishes_nothing():
    """PROBE PURITY (spec §1x) — the whole call is report-only.

    Round 6 proved the opposite interventionally: the stage-boundary
    probe's node-list rebuild called the MUTATING ``get_or_add``, and
    because the registry snaps within 0.5 m one extra insertion changed
    which later vertices welded — ``O4_STRING_MOVER_LEDGER=1`` moved
    SPJC's emitted surface (+1 node, 86 altitudes, |dz| <= 0.21 m).  Two
    properties lock it: the registry SIZE is unchanged across the call,
    and every layout attribute the readback pair publishes in its own
    node-index space is exactly as it was.
    """
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _PROBE_PUBLISHED_ATTRS)
    _MISSING = object()
    layout = _stage_layout([100.0] * 4)
    ledger = _stage_ledger(layout, 100.0)       # seeds the 4 apron corners
    _unseeded_shape(layout)
    size_before = layout.canonical_points.size
    pub_before = [(a, getattr(layout, a, _MISSING))
                  for a in _PROBE_PUBLISHED_ATTRS]

    assert mover_stage_boundary(layout, "03_tile_cut") == 0

    assert layout.canonical_points.size == size_before   # nothing interned
    assert [(a, getattr(layout, a, _MISSING))
            for a in _PROBE_PUBLISHED_ATTRS] == pub_before
    # and it still measured: the watched key resolved read-only
    row = ledger["stage_moves"]["final_proj_1.entry.03_tile_cut"]
    assert row["n_watched_here"] == 1 and row["n_unresolved"] == 0
    # the ledger keeps working after the pure readback
    layout.shapes[0].node_altitudes[0] = 101.0
    assert mover_stage_boundary(layout, "05_feature_conformance") == 1
    assert layout.canonical_points.size == size_before


def test_stage_boundary_reports_unresolved_keys_instead_of_interning():
    """A watched key the registry no longer holds is REPORTED, never
    inserted (§1x): ``n_unresolved`` names it and the surface is
    untouched."""
    layout = _stage_layout([100.0] * 4)
    ledger = _stage_ledger(layout, 100.0)
    ledger["key_of"] = {0: (999.0, 999.0)}      # nowhere near the registry
    size_before = layout.canonical_points.size

    assert mover_stage_boundary(layout, "18_emit_decimate") == 0

    assert layout.canonical_points.size == size_before
    row = ledger["stage_moves"]["final_proj_1.entry.18_emit_decimate"]
    assert row["n_watched_here"] == 0 and row["n_unresolved"] == 1
    assert row["max_abs_dz_m"] is None


def test_is_mover_label_admits_one_sub_level_of_entry_only():
    for label in MOVER_LABELS:
        assert is_mover_label(label)
    assert is_mover_label("final_proj_1.entry.00_post_solve")
    assert is_mover_label("final_proj_2.entry.18_emit_decimate")
    assert not is_mover_label("final_proj_1.entry.")     # empty stage
    assert not is_mover_label("final_proj_1.18_emit_decimate")
    assert not is_mover_label("proj_u.blend.something")
    assert not is_mover_label(None)


def test_pipeline_seam_wires_both_probes_and_is_inert_off():
    """The seam list is the pipeline's OWN (``_rod_ckpt``); round 2 hangs
    the sub-boundary on it rather than inventing seams."""
    from auto_patch import pipeline as _P
    layout = _stage_layout([100.0] * 4)
    _P._rod_ckpt(layout, "03_tile_cut")               # no ledger ⇒ no-op
    assert not hasattr(layout, "stage_moves")
    ledger = _stage_ledger(layout, 100.0)
    layout.shapes[0].node_altitudes[0] = 102.0
    _P._rod_ckpt(layout, "03_tile_cut")
    assert ledger["label"][0] == "final_proj_1.entry.03_tile_cut"


# ══════════════════════════════════════════════════════════════════════
# probe B
# ══════════════════════════════════════════════════════════════════════
class _Pts:
    def __init__(self):
        self.d = {}

    def get_or_add(self, x, y):
        return self.d.setdefault((round(x, 6), round(y, 6)), len(self.d))


class _Layout:
    def __init__(self, apt):
        self.canonical_points = _Pts()
        self.shapes = []
        self.runway_union = Polygon()
        apt = list(apt)
        self.string_substrate_src = {
            "apt": apt, "osm": [],
            "fingerprint": substrate_fingerprint(apt, [])}


class _G:
    def __init__(self, pos):
        self.pos = pos
        self.service_spine_pairs = set()


def _construct(dump_path, monkeypatch, **kwargs):
    n = 12
    pos = {i: (10.0 * i, 0.0) for i in range(n)}
    apt = [([pos[i] for i in range(0, 6)], False),
           ([pos[i] for i in range(5, n)], False)]
    layout = _Layout(apt)
    elev = [100.0] * n
    elev[0], elev[n - 1] = 100.0, 101.65
    band = [(-500.0, 500.0)] * n
    band[0] = (100.0, 100.0)
    band[n - 1] = (101.65, 101.65)
    monkeypatch.setenv("O4_STRING_STATE_DUMP", str(dump_path))
    out = construct_taut_strings(
        layout, _G(pos), elev=elev,
        bucket_to_idx={f"k{i}": i for i in range(n)}, n=n,
        node_band=band, hard={0, n - 1}, corridor_pieces=[],
        junction_adj={i: [(j, 0.15) for j in (i - 1, i + 1)
                          if 0 <= j < n] for i in range(n)},
        cap_of_segment=lambda a, b: 0.015, **kwargs)
    assert out, "the fixture must produce a string, or the dump is empty"
    with open(dump_path, "rb") as fh:
        return pickle.load(fh)


def test_state_dump_without_probe_b_carries_neither_field(tmp_path,
                                                          monkeypatch):
    """Nothing supplied ⇒ the keys are ABSENT (not present-and-empty), so
    an offline reader can tell "not carried" from "carried and empty"."""
    payload = _construct(tmp_path / "off.pkl", monkeypatch)
    assert "hard_cat" not in payload
    assert "have_initial" not in payload
    assert "elev" in payload and "bucket_to_idx" in payload


def test_state_dump_with_probe_b_carries_both_fields(tmp_path, monkeypatch):
    """Supplied ⇒ both ride the pickle verbatim, and nothing else in the
    payload changes."""
    hard_cat = {0: "seed_rwy_seam", 11: "rwy_join", 4: "seat_on_spine"}
    have_initial = [i % 2 == 0 for i in range(12)]
    base = _construct(tmp_path / "off.pkl", monkeypatch)
    payload = _construct(tmp_path / "on.pkl", monkeypatch,
                         hard_cat=hard_cat, have_initial=have_initial)
    assert payload["hard_cat"] == hard_cat
    assert payload["have_initial"] == have_initial
    for key, value in base.items():
        assert payload[key] == value, key


def test_probe_b_payload_is_a_copy_not_an_alias(tmp_path, monkeypatch):
    """The dump must not alias the caller's objects (the probe may never
    hand the solver's own containers to a consumer)."""
    hard_cat = {0: "seed_rwy_seam"}
    have_initial = [True, False]
    payload = _construct(tmp_path / "copy.pkl", monkeypatch,
                         hard_cat=hard_cat, have_initial=have_initial)
    assert payload["hard_cat"] == hard_cat
    assert payload["have_initial"] == have_initial
    hard_cat[99] = "mutated"
    have_initial.append(True)
    assert 99 not in payload["hard_cat"]
    assert len(payload["have_initial"]) == 2
