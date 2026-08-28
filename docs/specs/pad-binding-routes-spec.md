# Pad binding-route publication + offline trace (`pad_binding_routes`)

**Spec author:** Fable lead session, 2026-08-27.
**Origin:** owner request 2026-08-27 — answering "show me the calculated
route for building25's pad at HECA" required a full in-process rebuild,
because the reach band is live solver state and
`tools/trace_reach_route.py` deliberately reads the LIVE band (its
docstring records why an offline re-derivation became silently wrong).
**Disposition:** publication only. The engine publishes, at emit time,
the route evidence it already computed; the tool gains a mode that
renders the published record without building. No second engine, no
re-derivation, anywhere.

## 0. Doctrine this spec is bound by

* **Single-pass principle** — one capture, N consumers. The capture
  point is the existing one (`_frontage_band_records` /
  `build_building_seats`), extended, never duplicated.
* **Never a replay** — every number published is read from the band the
  seat consumed (`band.attachment_at`,
  `layout._band_anchor_provenance`, `G.spine_adj`/`G.pos` of the same
  pass). A re-derived lookup is a second engine and is forbidden.
* **Extend the near-fit, never fork** (owner ruling, RULINGS
  `7e90032`) — the route walk moves OUT of the tool INTO the engine and
  the tool imports it back; the sidecar renderer extends
  `trace_reach_route.py`, no new tool.
* **Evidence, never law input** — the census reports the key and
  adjudicates nothing from it.
* **Frame stamps** (RULINGS 2026-08-06 "Instrument truth is law") —
  the record carries its node-space token; absent facets are explicit,
  never omitted.

## 1. Engine: publish `pad_binding_routes` into the `.axes.json` sidecar

### 1.1 Walk relocation (prerequisite, same commit)

Move, verbatim in behavior, from `tools/trace_reach_route.py` into
`src/auto_patch/elevation_per_surface/building_feasibility.py`:

* `_walk_to_anchor(G, prov_side, node, anchor, limit=100000)` →
  public `walk_to_anchor(...)`, exported in `__all__`. Semantics
  unchanged: replays the RECORDED winning route (each hop must
  reconcile the recorded budget through the edge it crosses); a hop
  that does not reconcile stops the walk and reports incompleteness —
  never a search.
* `_edge_budget(G, a, b)` → public `spine_edge_budget(G, a, b)`,
  exported in `__all__`.

`tools/trace_reach_route.py` then imports both and deletes its private
copies. One implementation, two consumers. The tool's docstrings
describing the walk move with the code (they are the walk's contract).

### 1.2 Capture point

`route_profile/anchors.py :: build_building_seats` gains an optional
keyword parameter `unified_graph=None`. The one production call site
(`route_profile/solve.py:2808`) passes the `_G` it already received
from `reach_band_for` (solve.py:2717) — the SAME graph the band of
record was built on. Test callers that pass nothing get `None` and the
route capture is skipped (see §1.6).

Capture happens inside the existing per-pad loop, beside the
`_frontage_band_records` capture (the "ONE capture, TWO consumers"
block, anchors.py ~976-988), reading:

* `band(x, y)` and `band.attachment_at(x, y)` — already read there;
* `layout._band_anchor_provenance` — recorded by
  `_record_anchor_provenance` when THIS band was built ("write-only,
  last call wins" — and this capture runs synchronously with the same
  `band` object in hand, so the map in hand is the one this band
  wrote);
* `unified_graph.spine_adj` / `unified_graph.pos` via
  `walk_to_anchor` / `spine_edge_budget`.

**Pass-identity guard.** Before capturing, assert
`band is band_of_record(layout)`
(`building_feasibility.band_of_record`). On mismatch: do NOT publish
routes from a possibly-foreign node space — set the container's
`nodespace` to `null`, append no records, and `_report` one loud line
naming the mismatch. Never silent, never a crash (evidence must not
kill a build the law would accept).

### 1.3 Binding-node rule

Identical to the tool's `_binding_route` (trace_reach_route.py:290-296),
stated here so the two can never drift:

* the band takes the MIN ceiling over the route nodes seeding a cell,
  so the CEILING-binding attachment node is
  `argmin over attachment_nodes of (anchor_value[anchor] + budget)`
  from the `ceiling` provenance side (ties → lowest node id);
* symmetrically the FLOOR-binding node is
  `argmax of (anchor_value[anchor] − budget)` from the `floor` side
  (ties → lowest node id).

Per pad, the frontage point whose interval BINDS the pad's box is the
one published per side: the frontage record with the minimum ceiling
(ceiling side) / maximum floor (floor side) among that pad's
apron-shared edge centres — i.e. the edge of the intersection the seat
was actually clamped by. One route per side per pad; no
per-frontage-point fan-out (bounded size, and it is the binding route
the owner asks for).

### 1.4 Record schema

Sidecar key `pad_binding_routes`, written unconditionally by
`layout._write_axes_sidecar` from `layout._pad_binding_routes` (set by
the capture; `getattr` default used at write time as for every other
key). Shape:

```json
{"nodespace": "n=<len(G.pos)>",     // null = capture could not run
 "records": [
   {"pad": "<shape.ref>",
    "seat_m": <float>,               // the seat chosen at capture time
    "off_network": false,
    "sides": {
      "ceiling": {
        "anchor_node": <int>,
        "anchor_ll": [lat, lon],
        "anchor_value_m": <float>,   // provenance anchor_value[anchor]
        "route_budget_m": <float>,   // provenance budget at binding node
        "plan_len_m": <float>,       // sum of hop plan lengths
        "route_complete": <bool>,    // walk reached the anchor
        "route_ll": [[lat, lon], ...],  // anchor → binding attachment
                                        // node, 7 dp, every hop node
        "frontage_ll": [lat, lon],   // the binding frontage point
        "band_floor_m": <float>,     // band(x,y) at that point
        "band_ceiling_m": <float>
      },
      "floor": { same fields }
    }}
 ]}
```

* A pad whose frontage points all answer `band(x,y) is None`, or whose
  attachment carries no provenance-known node, publishes
  `{"pad": ..., "seat_m": ..., "off_network": true}` and no `sides` —
  an ANSWER (the within-shape law governs it), not a refusal; same
  doctrine as the tool.
* A side whose walk is incomplete still publishes, with
  `route_complete: false` and the partial chain — incompleteness is a
  finding, not a suppression.
* `route_ll` is the full recorded chain, 7-dp rounding
  (the `seam_pins` precedent). **No silent caps**: never truncate;
  these chains are route-node chains (hundreds of nodes worst case ×
  one per side per pad — small beside `mesh_edges`).
* Coordinates via `layout.m_to_ll` on `G.pos`; this is presentation
  precision, not an identity join (the canonical-identity law is not
  in play — nothing re-joins these).

### 1.5 Key registration

Add `pad_binding_routes` to `SIDECAR_EVIDENCE_KEYS` in
`tools/check_grade.py` with a comment naming this spec — EVIDENCE,
deliberately: the census reports it and adjudicates nothing.
`tests/test_harness.py`'s classification twin fails otherwise; that
twin is the enforcement, do not weaken it.

### 1.6 Degraded contexts

`unified_graph is None`, band without `attachment_at`, or empty
`_band_anchor_provenance` (hermetic tests, hand-made bands, synthetic
layouts): capture publishes `{"nodespace": null, "records": []}` —
a reader can tell "capture could not run" (`nodespace: null`) from
"ran, no pads" (`nodespace` set, `records: []`) from "patch predates
the key" (key absent).

## 2. Tool: `trace_reach_route.py --from-sidecar`

### 2.1 Interface

```
venv/bin/python tools/trace_reach_route.py --from-sidecar PATCH.osm \
      [--ref building25 ...] [--out /tmp/route.kml]
```

* `--from-sidecar` takes the patch path or the `.axes.json` path
  itself (accept both; resolve `X.osm` → `X.osm.axes.json`).
* Mutually exclusive with the build modes (`ICAO` positional, `--dem`,
  `--coord`, `--ref` as a build lookup, `--inverted-pairs`); `--ref`
  in this mode is a FILTER on `records[].pad` (repeatable; default all
  pads).
* NO build, NO engine solve, NO layout: the mode reads JSON and writes
  the render. It must not import the solver (keep the imports inside
  the build-mode functions, as today).
* Output format by `--out` extension: `.kml` → KML (default
  `/tmp/reach_route.kml`), `.osm` → OSM XML.
* Missing `pad_binding_routes` key → exit with a message naming the
  fact and the remedy ("this patch predates route publication —
  rebuild it, or use the live modes"). `nodespace: null` → print the
  capture-unavailable fact and render nothing. Empty `records` →
  say so. A `--ref` that matches nothing → name the refs that exist.

### 2.2 Rendering

* **KML**: factor the document skeleton + `line`/`pm` helpers out of
  `_kml` (trace_reach_route.py:900-967) so ONE skeleton serves both
  the live mode and the sidecar mode (extend, never duplicate). Per
  pad: a folder; per side: the route as a LineString styled as today
  (distinct color per side), placemarks for the anchor (name carries
  `anchor_node`, `anchor_value_m`, `route_budget_m`, `plan_len_m`,
  `route_complete`) and the frontage point (name carries
  `band_floor_m`/`band_ceiling_m`/`seat_m`). Off-network pads render a
  single placemark saying so.
* **OSM**: minimal well-formed `.osm` XML, negative ids, one way per
  side per pad with tags `pad_binding_route=ceiling|floor`,
  `pad=<ref>`, `anchor_node`, `route_budget_m`, `plan_len_m`,
  `route_complete`, `band_floor_m`, `band_ceiling_m`; nodes shared
  per way. It is a viewer artifact (JOSM), never a patch — no
  `.axes.json` beside it, and the writer must refuse an `--out` that
  ends in `.patch.osm` (the patch loader globs `*.patch.osm`; a
  render must never be loadable as scenery).

### 2.3 `tools/INDEX.md`

Update the `trace_reach_route.py` entry in the SAME commit: the new
mode, its no-build property, and the sidecar key it consumes. A tool
change without its index entry is a defect (tool-discipline ruling).

## 3. Twins (mandatory, same commit)

1. **Engine capture twin** — extend the near-fit fixture family
   (`tests/test_seat_band_and_coupler.py` /
   `tests/test_route_metric_seat_coupling.py` drive
   `build_building_seats` directly with hand-made bands): with a
   synthetic band exposing `attachment_at`, a synthetic
   `_band_anchor_provenance` and a synthetic `unified_graph`, assert
   (a) `layout._pad_binding_routes["records"]` names the pad, the
   expected binding anchor per side, `route_complete=True`, and a
   chain whose ends are the anchor and the binding attachment node;
   (b) `plan_len_m` equals the hand-computable chain length;
   (c) a hand-made band WITHOUT `attachment_at` yields
   `{"nodespace": null, "records": []}` and the build does not fail;
   (d) an off-band pad yields `off_network: true`.
2. **Sidecar write twin** — `_write_axes_sidecar` on a synthetic
   layout publishes the key unconditionally; absent-attr layout
   publishes the §1.6 degraded shape.
3. **Key-classification twin** — already exists
   (`tests/test_harness.py`); adding the key to
   `SIDECAR_EVIDENCE_KEYS` is what makes it pass. Do not touch the
   twin.
4. **Single-implementation twin** — assert
   `trace_reach_route` has no private walk:
   the module's `walk_to_anchor` / `spine_edge_budget` ARE
   `building_feasibility.walk_to_anchor` /
   `.spine_edge_budget` (object identity), and
   `inspect.getsource(tools.trace_reach_route)` contains no
   `def _walk_to_anchor` / `def _edge_budget`.
5. **Tool sidecar-mode twin** — hermetic (`tmp_path`, no build): a
   hand-written sidecar with one pad/two sides renders (a) a KML
   containing both route coordinate strings and the anchor placemark
   fields; (b) an OSM whose ways carry the §2.2 tags; (c) missing key
   → the named refusal; (d) `--ref` filter honored; (e) `.patch.osm`
   out-path refused.

## 4. Budget, guards, verification scope

* **Build-time impact statement** (hard law): the capture is, per pad,
  two recorded-provenance walks (dict lookups along an already-chosen
  chain; no Dijkstra, no band rebuild). Estimate ≪ 0.1 s on
  HECA-scale layouts — under the 1 % (0.6 s) threshold; no Fable-5
  optimization review required. The sidecar grows by the two chains
  per pad (7-dp floats); no reader loads it whole except the census,
  which already streams `mesh_edges`-scale keys.
* **Convergence guards**: materiality floor 0.01 m on any elevation
  assertion in the twins; attempt cap 2 per target then STOP-and-
  report; long steps stamp `.progress` in the scratch dir.
* **Pre-ship mode** (RULINGS): run ONCE the test files this change
  touches (`test_harness.py`, the extended seat-band test files, the
  new tool twin, `test_r17b_below_grade_anchor_scope.py` — it twins
  the tool being refactored). No battery, no full suite; each skipped
  verification gets its line in `docs/DEFERRED_VERIFICATION.md`.
* **Acceptance (ONE build, the owner's own question)**: from
  `Ortho4XP/`, `venv/bin/python tools/harness/build_airport.py HECA`
  (mount via `tools/harness/lane_worktree.sh` if the harness refuses
  the lane), then
  `venv/bin/python tools/trace_reach_route.py --from-sidecar
  <emitted HECA patch> --ref building25 --out /tmp/building25.kml`
  — the render must succeed with no build and name building25's
  binding anchors, budgets and band. Report the record verbatim.

## 5. Out of scope

* No change to band construction, seat choice, provenance recording,
  or any law family. Publication only.
* No consumer in the census beyond key classification.
* No decimation/simplification of published chains.
* The live modes of `trace_reach_route.py` keep their exact behavior
  (the walk relocation is a move, not an edit).
