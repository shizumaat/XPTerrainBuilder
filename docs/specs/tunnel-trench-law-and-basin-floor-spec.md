# Tunnel-trench law entry + basin floor integrity (Fable spec,
# 2026-08-25; tunnels round, classes 1a/1b of the LEMD+OTHH
# attribution)

Evidence: the 2026-08-25 tunnel attribution. 90.7 % of LEMD's 12,253
census rows (95.7 % of OTHH's baseline 5,871) are rows involving
`tunnel_trench` — minted because the role has NO `ROLE_GRADE_LIMITS`
entry, so the by-law node-split trench wall (R2) prices as a step at
every contact under the fall-through default cap. Separately, LEMD's
basin floor is 51.5 m too deep: two 4-vertex DECAL quads authored at
y=-48.244 (AESlite VOR ground decals) pooled into one facility and set
`solid_minimum_y_m = -50.0`; the sidecar prints `body_depth_m 7.02`
beside `floor_m 545.52` — a 43 m disagreement between two numbers on
one line, unchecked.

## §1 Declared-step exemption for tunnel trenches (census side)

1. NOT `"tunnel_trench": None` — that blinds the census to a trench
   born 51 m too deep. Instead the `terrace_joints`/`crown_drops`
   idiom: the sidecar already publishes `basin_facilities` (`floor_m`,
   `rim_law_m`, `emitted_rim_min/max_m`) per facility; the census
   prices a trench↔pavement or trench↔rim step against the facility's
   OWN DECLARED floor→rim drop and reports only the EXCESS beyond it
   (materiality floor applies).
2. `tunnel_trench|tunnel_trench` within-shape pairs price at None
   (a flat-by-law terrain plate carries no taxiway cap) — the declared
   geometry, not the 1.5 % fall-through.
3. Lands in `LAW_FAMILIES` + `run_checks` + the sidecar reader
   together — `tests/test_harness.py` twins enforce the register; a
   family added without register parity fails there. The census, CLI
   and fixtures share the one code path (standing law).
4. Twin: a synthetic facility with declared drop D — a wall step of D
   prices zero rows; a step of D+1 prices the 1 m excess; a facility
   whose floor is 50 m below its declared rim (the LEMD class) still
   reports.

## §2 A decal is not a solid (facility floor integrity)

1. A pooled part contributes to `minimum_effective_height_m` (the
   "deepest solid" witness) ONLY if it has vertical extent: parts
   whose own authored bbox height (max_y − min_y) is below
   `MIN_SOLID_PART_THICKNESS_M = 0.3` are EXCLUDED from the
   floor-witness minimum (they remain in the pool for every other
   purpose). A 4-vertex flat quad at y=-48 is a ground decal, not a
   structure floor (the LSGG shared-datum class).
2. THE DISAGREEMENT GATE: where
   `|solid_minimum_y_m + body_depth_m| > BASIN_FLOOR_DISAGREEMENT_M
   (2.0)`
   the facility floor derives from `body_depth_m` (the deck-face
   median population) and the discarded witness is reported LOUDLY
   with its resource name and authored y — never a silent 43 m
   disagreement on one log line. Measured calibration: every OTHH
   basin agrees within 0.4 m; LEMD's pooled decal disagrees by 43 m.
3. Pooling itself (the 2.0 m chain-join that united a VOR decal, an
   FSX ground poly and an airport object) is NOT changed in this
   round — recorded for a future docket; §2.1+§2.2 make the pool's
   floor immune to its worst member.
4. Twins: (a) decal quad in a pool → floor from the real solids;
   (b) genuine deep solid (thickness > threshold) still sets the
   floor; (c) the gate fires on a synthetic 43 m disagreement, loud
   line names the resource; (d) OTHH-class agreement (≤0.4 m) →
   byte-identical behaviour.

## Acceptance

- LEMD build + census: the `tunnel_trench` families collapse to the
  EXCESS population (report honestly — expect the 61 m class to
  survive §1 until §2 fixes the floor, and to vanish under §1+§2:
  report both single-section arms if cheap, else the composed arm
  with the class table); basin_facilities sidecar shows floor_m ≈
  rim − body_depth (≈590, not 545.5).
- OTHH (baseline artifact re-censused under the new law, no rebuild
  needed for §1; ONE build only if §2 changes OTHH's floors — its
  basins agree within 0.4 m so expect byte-identical): the ~5,616
  lawful trench rows retire; the real 14.7 m worst-step facility
  (the pooled AuxBuilding/ControlPost/Dewatering case) is reported
  via the gate if it trips, else unchanged.
- No airside regression on HECA/SPJC/CYXY census (their patches carry
  no tunnel_trench; re-census existing artifacts, no rebuilds).
- Attempt cap 2, materiality 0.01 m, STOP on second miss. No
  shared-repo writes, no timing claims.

## Amendment 1 (Fable, 2026-08-25 — per-part wall allowance; the flat
## declared drop misprices walls on sloping ground)

Measured (lane/basinpad, LEMD_a4): the pan↔rim wall on sloping ground
emits per-part (rim 592.64-595.24) while `_basin_declared_drop` prices
the FLAT declared drop (593.03 − 586.01), so every part shipping more
than the flat drop by its terrain relief reports — +930 rows, worst
9.23 m, all lawful walls. OTHH never exposed it (flat DEM).

1. The §1 allowance at a wall contact is PER PART: that part's own
   published `emitted_rim` − the facility `floor_m` (the sidecar
   already carries both). Excess beyond the part's own drop still
   reports in full — a floor 50 m below its rim remains visible.
2. The declared-number join discipline stands (join on published
   sidecar values, never proximity).
3. Twin: sloping-ground facility → zero rows at lawful walls; a part
   emitted 1 m deeper than its published rim → 1 m excess row.
4. Acceptance: LEMD wall rows collapse (+930 → ≈0 lawful; report);
   OTHH/controls unchanged.
