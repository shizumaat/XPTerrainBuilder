# LEMD bridge deck — implementation of RULINGS 2026-08-30c
# (the ratified ROAD BRIDGE DECK law, §1–§6; owner site
# 40.4836744,-3.5809643)

The law text is canon in docs/RULINGS.md 2026-08-30c — implement it
verbatim; any deviation is a STOP. The attribution underneath it is
already measured (lemd-bridge-pit-spec.md round report, lane/lemdbridge):

- Feed ways -2192 (`bridge=yes layer=1`, lanes=4 → 14.0 m, the owner's
  span, west abutment node -10817 = 40.4836088,-3.5808853) and -2195
  (parallel southern deck, 7.0 m) in
  `OSM_data/_airport_road_feed/LEMD_road_feed.cache`.
- Bridge ways are skipped at bridges.py:11247, :14877, :1323, :1061;
  osm_aeroway.py:326 records `is_bridge` unused.
- The corridor course filter (pipeline.py:3607–3621) drops -2192 on
  the touching-pavement test; admission there joins it to -2096's
  chain via the shared node -10817 (linemerge at pipeline.py:3676).
- The west abutment currently mints a free-end DEM tie at junction
  514's nodes (recorded target 609.953, emitted 600.82) — §3 removes
  that tie; the deck pin (§4/§5) replaces it.

## Work

1. §1 detection: bridge-tagged feed way × emitted below-grade
   structures (tunnel_ramp / tunnel_trench / open cut) intersection.
   No geometry inference; the tag is the only trigger.
2. §2 emission: admit the way to the corridor course set on bridge
   evidence; carriageway from stated width; ordinary road shape class.
3. §3 protections: second exception in `_TUNNEL_PROTECTED_TRANSIT
   _ROLES` / `_tunnel_ramp_cut_roles` scoped to the bridged span; no
   free-end tie at either abutment.
4. §4/§5 solve: deck pinned ≥ highest emitted surface beneath +
   `BRIDGE_ROAD_CLEARANCE_M`; approaches reach the pin at
   `SERVICE_ROAD_MAX_GRADE`; far side lands at the receiving surface
   value. The ramp beneath NEVER yields (airside-frozen: verify with
   airside_value_delta.py — zero solve-owned airside nodes moved).
5. §6 refusal: infeasible deck refuses loudly (named log line +
   sidecar evidence) and stands down to today's surface.

## Acceptance (site-first)

At 40.4836744,-3.5809643: road pavement continuous across the span
(the 11-station containment read shows zero OUTSIDE-EVERYTHING
stations); deck ≥ 603.55 (598.45 + 5.1) over the ramp; west approach
climbs from ~600.9–602.5 at ≤ road cap; east lands at groundside 557 /
junctions 184–185 values (601.8–603.4); tunnel ramp profile
byte-identical to the pre-law arm. Synthetic twin for §1/§3/§6 (a
bridge-tagged span over a fixture ramp: emits, is not cut, refuses
when infeasible). ONE closing LEMD build; control = the round's
closing arm (ledger `8a99a927adfb`, tree d11fd01c) — the code delta vs
main is the law only. Census not worsened; the -2195 southern deck is
in scope if it crosses an emitted structure, otherwise untouched by §1.
Below-bar = STOP with residual quoted.
