# HECA object-pad seating + excavation-rim pockets (Fable spec, 2026-08-12b)

Owner report (in-sim, 1.0.243, with JOSM evidence): object_pad:80
(shapeID 2646) emitted at 105.51 atop the DEM knoll at
(30.1136676,31.4086362), 13 m above the service road / apron at ~93.3;
"it should be level with the service road it's next to."
PRE-SHIP DEV MODE; deviations STOP-and-report to this spec's author.

## Evidence (measured on the owner's 1.50.1686 tile artifact —
## XPTerrainBuilderData/Patches/+30+030/+30+031/HECA_auto.patch.osm)

- object_pad:80 = way -12645, 14 nodes, flat 105.51 = its sidecar
  `emitted_target_metres` to the centibyte — NO pass ever moved it.
  Admission LAWFUL: real DSF placement Airport/Hangar_Tower/T3_34.obj
  (cluster, 55.48 m², object-pad channel, not the building-evidence
  gate).
- The emitted APRON RING (-10629) carries the pad's blend vertices at
  106.05/106.12 WELDED BETWEEN its own 93.67/93.45 body nodes — the
  weld the family needed, existing in the final geometry only.
- **0 of 139 object pads adopted a host level in this build** (131
  byte-identical to sidecar targets, 8 moved ≤0.73 m by later ring
  passes). Systemic: `_level_family_members` returns None (no seeds)
  because `weld_candidate_pairs(layout, tol=0.01,
  include_overlay_refs=True)` at BOTH relevel call sites predicts no
  pad↔host pair here, while the final epsilon-wedge weld later makes
  exactly that pair. Host body vertices are 10.4 m out — reachable only
  through the predicted-weld relation.
- Caps in play: DSF_OBJECT_PAD_MAX_RELIEF_M = 3.0 (adopt delta),
  PAD_HOST_LEVEL_LIFT_M = 6.0 (value-lip scope) — both smaller than the
  11.95 m this site needs.
- The knoll pocket: ~1,000 m² / ~35 m wide coverage hole at the rim of
  an apron excavated ~13 m below natural grade; bounded by apron E/S,
  groundside W, service road/junction + building pad N; OPEN to the SW.
  Dimensionally inside gap-fill floors (min 100 m², max width 175 m);
  blocked only by the enclosure test. R19-2 closed the ENCLOSED-hole
  case; this is the open-boundary case (part-30f class, STATUS:6669).

## Rulings

1. **The seeding defect is the target, and it is systemic.** The family
   relation must see, at relevel time, the SAME pad↔host identities the
   final weld will mint — including welds carried by a pad's BLEND ring
   into a host edge (the measured miss). Mechanism-before-fix applies:
   the lane FIRST builds a synthetic repro (pad + blend plate + host
   apron edge within weld reach, no shared vertices) reproducing
   seeds=None with `O4_PAD_FAMILY_DEBUG`, THEN attributes exactly which
   half fails (blend rings absent from the candidate enumeration? tol
   frame? overlay refs not mapped back to the pad group?), THEN fixes
   that half — one code path with the weld, as the #16 spec ruled. If
   the attribution lands somewhere this spec did not anticipate, STOP.
2. **Agreeing-host adoption is not relief-capped.** DSF_OBJECT_PAD_MAX_
   RELIEF_M (3.0) governs DEM-relief-derived moves; a coalition of ≥2
   agreeing HOST members (within _MEMBER_DELTA_AGREEMENT_WINDOW_M)
   adopts FULLY — the agreement + area weights are the safety (the
   swap class stays the named control). PAD_HOST_LEVEL_LIFT_M keeps its
   value-lip scoping role only. The blend plate re-ties from the new
   core level per the existing one-delta group move.
3. **Excavation-rim pockets join the graded domain.** A coverage hole
   whose boundary is ≥75% graded features (apron / roads / junctions /
   groundside pavement / pads) is ENCLOSED for gap-fill purposes even
   with an open segment — extend R19-2's subdivision to this case. The
   knoll then grades inside the fill toward its bounding features; the
   pad's blend ties into GRADED ground, not the raw 106 m knoll.
4. Order of application at the site: pocket fill grades the ground;
   pad seats to its host coalition (~93.5); blend re-ties. Acceptance
   reads the composed result.

## Implementation plan (ONE Opus lane)

1. blast.py per touched file; ledgered tests once; synthetic repro
   FIRST (ruling 1) — it is the fix-loop oracle per the owner's
   repro-cutter ruling; the HECA tile build is verification only.
2. Fix the seeding half named by the repro (conformance/anchors — keep
   ONE weld-predicate implementation; if the enumeration must run on a
   later geometry state, derive both weld and prediction from the same
   inputs rather than forking).
3. Ruling 2: adoption-cap rescope + twins (full adoption at 11.95 m
   with 2 agreeing hosts; a lone non-agreeing host still refuses; swap
   fixture stays green).
4. Ruling 3: pocket-enclosure extension in the gap-fill/adjacent-ground
   machinery + twin (open-boundary pocket fixture: ≥75% graded boundary
   → filled; a 50% one → untouched).
5. Acceptance: ONE HECA tile arm (4-step, foreground, lane-local build
   dir, never the X-Plane install), against the owner artifact
   baseline:
   - object_pad:80 core = host coalition level 93.5 ±0.3 (quote the
     coalition members); blend ramps into the graded pocket; the apron
     ring's welded vertices carry the SAME level as their neighbours
     (no 106-between-93s contamination).
   - Adoption census: N of 139 pads adopt (quote N, max |delta|, and
     the distribution); every adoption's coalition quoted host-agreeing;
     swap class 140/141, 146/151, 210/211 byte-stable.
   - Pocket: mesh/patch at (30.1136676,31.4086362) graded (quote
     before 106.285 → after), no residual wall/cliff at the pocket rim
     beyond lawful terraces.
   - Census before/after row-classed; positive deltas argued under the
     exposing-pre-existing ruling or STOPped.
   - OTHH control (--patch-only with its pads sidecar if present in the
     lane, else tile arm ONLY if the patch frame lacks pads): the
     seeding fix is systemic — quote OTHH adoption count and census
     delta; unexplained geometry churn is a STOP.
6. Build-time impact statement (the enumeration already costs 0.76 s
   flagged; quote any addition — profiling round adjudicates).

Convergence: materiality 0.01 m; attempt cap 2 per target; `.progress`
heartbeat; shared repo UNCHANGED; commit on lane branch; no merge.

## Out of scope

The knoll's DSM contamination upstream (elevation-source cleaning);
relief-round groundside items; #11 band remedy; building-pad admission
(R18-2 untouched).
