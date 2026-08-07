# Tunnel portal fidelity — spec (2026-08-07)

Author: lead session (Fable). Status: FROZEN for implementation.
Rulings: `docs/RULINGS.md` "2026-08-07 — Tunnel portal fidelity: four
rulings"; attribution context in memory `othh-tunnel-emitter-attribution`
and the session investigation (OTHH, tile +25+051).

## 1. Context (established, do not re-derive)

All six OTHH tunnel symptom sites are defects of the OSM-road tunnel
machinery in `src/auto_patch/bridges.py`. Every real tunnel is mapped in
OSM and already present in the cached corpus (tile `big_roads` + the
airport road feed). The object classifier is out of scope: the pack
carries zero `ATTR_hard`, so its tunnel signature is structurally
unsatisfiable there. `_emit_tunnel_portals` runs from `finalize.py`
(≈:559) AFTER the elevation solve — pavement shapes it touches are
already solved; `cut_pavement_over_footprint` (`bridges.py:5041`) is the
existing post-solve pavement-surgery helper (the R13 path in
`object_terrain_assembly.py:1663-1682` uses it at the same stage).

Line numbers below are from the pre-change tree; re-locate with the
cited symbols, do not trust offsets after editing.

## 2. Changes (all four are owner rulings; none is optional)

### C-1 Mapped-end preservation becomes unconditional (ruling 1)

Site: the mapped-end preservation block in
`_synthesize_implied_crossing_bores` (`bridges.py` ≈905-912, comment
≈891-904 names SPJC). Today a merged bore interval snaps to the mapped
way's ends only when the head/tail stretch is ≤ 100 m; OTHH's 62 m
mouth stretch passed under it, planting the portal 61 m inside the bore
and stripping `tunnel=yes` off the covered mouth stretch (≈956-960),
which the ramp then excavated.

Change: for `_had_tunnel` ways, snap the merged interval's ends to the
mapped way extent ALWAYS (portal at s=0 and s=L). Implied (un-tagged)
ways keep the existing behavior byte-identically. Consequence to
preserve, not fight: the portal nodes are node-shared with the untagged
surface continuation ways, so `_walk_surface` then builds the approach
ramp on the SURFACE side, descending to the mapped mouth — that is the
intended geometry (OTHH mouth D = 25.2789456, 51.5994543).

### C-2 No open-cut inside a mapped bore (ruling 2)

Site: the low-connector open-cut test in the interval-merge loop
(`bridges.py` ≈874): a gap < `TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M`
(100 m) between crossings is recorded for open excavation. The test
carries no `_had_tunnel` term, so 86.5 m and 39 m interior gaps of
OTHH's mapped 810 m bore were dug open (emitted ways -11724, -11728).

Change: record an open-cut gap ONLY when the way is not `_had_tunnel`.
Mapped-bore gaps still MERGE (they are covered roof, exactly like gaps
≥ 100 m today). The implied-bore path (KDFW class, comment ≈851-873)
is untouched — add a regression test proving it.

### C-3 Corridor cutback joins the 0.6 m clearance standard (ruling 3)

Site: `_emit_low_corridor_connectors` (`bridges.py` ≈3245-3247) cuts
the corridor back by `airside_gate_union.buffer(0.5)` — exactly
`SHARED_VERTEX_TOL_M`, so a corridor corner can land in a solved
pavement vertex's intern bucket and inherit its altitude (the
−5.16/+3.19 needle on way -11724). Every other tunnel emitter clears
0.6 m (`_TUNNEL_GRAZE_CLEARANCE_M`, ≈3350; `wall_gap_m` comment
≈3646-3653).

Change: use `_TUNNEL_GRAZE_CLEARANCE_M` (no new literal) for that
cutback. With C-2 landed this emitter no longer fires on mapped bores,
but it still serves implied corridors — fix it there.

### C-4 Tunnel ramp wins over pavement (ruling 4)

Site: the pavement-overlap clip loop (`bridges.py` ≈3474-3577): a
tunnel piece (`tunnel_cap` / `tunnel_wall` / `tunnel_ramp`, ≈3504)
whose intersection with `airside_gate_union` is ≥ 50 % of its area
drops whole (≈3517-3519); below 50 % it is graze-clipped (≈3520-3567).
This beheaded the mapped A-site portal (ramps dropped over the
`service_junction` grid; only the 1 m perimeter wall band survived)
and is the leading suspect for B1/B2/B3 emitting nothing.

Change:
* `tunnel_ramp` pieces are EXEMPT from both the ≥ 50 % drop and the
  graze clip against pavement. Emit them whole.
* After the cluster's ramp pieces are final, cut the pavement they
  surface through: `cut_pavement_over_footprint(layout,
  ramp_footprint_union, cut_roles=pavement_cut_roles(
  include_groundside=True))` — the R13 helper already in this module.
  Follow the R13 call pattern (`object_terrain_assembly.py:1663-1682`)
  for any reindex/union bookkeeping the helper expects.
* `tunnel_wall` bands keep their current clip behavior against
  pavement EXCEPT where the pavement was just cut by their own
  cluster's ramps (walls follow their ramp). `tunnel_cap` behavior
  unchanged. The WALL-vs-RAMP clip (≈3580-3631) stays.
* SAFETY FLOOR (spec-level, flagged in RULINGS): a ramp NEVER cuts a
  runway-family shape (the runway roles as defined in `config.py` /
  role constants — resolve the exact set from `ROLE_*` and
  `pavement_cut_roles`' complement; at minimum runway, runway
  end-skirt, runway clearance). A ramp piece overlapping a
  runway-family shape ≥ 50 % is dropped with a `vprint(1)` naming the
  source way id and the shape. Do not silently clip.

Gating: all four changes are ungated default-ON law-alignment fixes to
already-default-ON machinery (no new config flags; no degradation
shields — owner 2026-08-04).

## 3. Out of scope / STOP conditions

* Object-classifier changes, OSM data refreshes, apt.dat edits: out.
* The B1-B3 kill mechanism is being confirmed by a `O4_TUNNEL_DEBUG=1`
  OTHH build. If its log shows the B-site portals died to something
  OTHER than the C-4 clip (e.g. the adjacent-road skip at ≈1507, or a
  walk failure), STOP and report — do not widen this spec.
* Any public-interface change, any deviation: STOP and report (the
  spec author rules on it).

## 4. Acceptance

1. **Unit tests, synthetic** (no airport builds inside pytest; follow
   the module's existing test conventions — locate via
   `venv/bin/python tools/blast.py src/auto_patch/bridges.py`):
   a. Mapped 2-node `tunnel=yes` bore, pavement crossing starting 62 m
      from one end → portal at the mapped end, no below-grade piece
      inside the mapped extent (C-1).
   b. Same geometry UNTAGGED (implied) → existing behavior unchanged
      (portal at the crossing edge) — regression guard.
   c. Mapped bore with an 86 m interior gap between two crossings →
      no low-connector shape; identical implied bore → connector still
      emitted (C-2 + KDFW guard).
   d. Corridor cutback clearance ≥ 0.6 m (C-3).
   e. Ramp overlapping ≥ 50 % service pavement → ramp emitted whole,
      pavement cut (assert shape count/area delta); ramp overlapping a
      runway shape → ramp dropped, loud log (C-4).
2. **Suite**: the blast.py-named tests plus the new file, through
   `tools/run_with_ledger.py`.
3. **OTHH acceptance — ONE patch-only harness build**
   (`venv/bin/python tools/harness/build_airport.py OTHH --patch-only
   --tag tunnel-fidelity`), then assert on the emitted patch:
   * a `tunnel_ramp` way with a vertex within 15 m of D
     (25.2789456, 51.5994543), its below-grade extent entirely OUTSIDE
     the mapped bore span (bore = OSM ways -917/-918 in the tile
     big_roads cache);
   * ZERO emitted vertices with `alt_abs < 0` lying over the covered
     span s ∈ [70, 740] of that bore;
   * `tunnel_ramp` geometry within 60 m of each of A
     (25.271935, 51.6022729), B1 (25.2758817, 51.6139664), B2
     (25.2558032, 51.6079424), B3 (25.2540818, 51.6036435);
   * no `ref='tunnel_low_connector'` on any mapped bore;
   * the −5.16/+3.19 needle gone (no way mixing altitudes ≥ 8 m apart
     within the C2 corridor footprint).
4. **Census, law-true**: `venv/bin/python tools/harness/census.py` on
   the OTHH patch BEFORE and AFTER (the pre-fix patch is the current
   `/Users/noah/XPTerrainBuilderData/Patches/+20+050/+25+051/
   OTHH_auto.patch.osm`; census it first, or reuse a lane copy — do
   not overwrite it). Requirement: no NEW adjudicated violations in
   families untouched by tunnels; new ramps hold the tunnel/groundside
   4 % cap (planned grade is 3.5 %).
5. **Build-time impact statement** in the report (ledger tripwire only,
   per the 2026-08-04 suspension; expected: negligible — the clip loop
   gains one union+cut per portal cluster).

## 5. Convergence guards (mandatory)

Materiality floor 0.01 m (elevation) / 0.01 pp (grades); attempt cap 2
per target then STOP-and-report; progress heartbeat START/step/EXIT
stamps in the scratch dir (`.progress` convention).

## 6. Honest budget

Implementation + unit tests: no builds. Verification: 1 × OTHH
patch-only build (~8-10 min wall) + census (~1 min) + pytest selection
(~1-7 min). Nothing timed; concurrent with other correctness work is
allowed (owner 2026-07-31).
