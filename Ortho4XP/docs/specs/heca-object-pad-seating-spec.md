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

## AMENDMENT 1 (Fable lead, 2026-08-12b, after the lane's STOP)

The lane's measurement is accepted; ruling 1's premise is RETIRED. The
weld-prediction relation is VINDICATED (the cut-back pre-weld frame
seeds the owner's pad and adopts 105.51→93.45); the systemic 343/347
no-family is host-role scope and mostly LAWFUL (292/365 pads sit on
open terrain and rightly follow DEM). Ruling 2 stands as measured
(already satisfied; twins landed). The unexplained residue is why the
owner's 14:57 build did NOT adopt a pad that seeds when replayed — and
that cannot be answered while the pad's request is absent from every
current corpus.

Re-ruled plan, in order:

1. **Pin the live corpus (tile frame).** ONE HECA tile arm at lane HEAD
   (4-step, foreground, lane-local build dir, never the X-Plane
   install) with `O4_PAD_FAMILY_DEBUG=*` capturing the relevel debug.
   Outcomes: (a) the site's pad IS re-requested → capture its family
   debug in the SAME build and attribute why adoption differs from the
   replay; a fix then lands against that evidence (attempt cap 2 from
   here). (b) The pad is NOT re-requested → the 105.51 defect is
   corpus-history; record it, no pad-side fix lands, the finding goes
   to the owner report.
2. **Ruling 3 (pocket enclosure) proceeds regardless** — at HEAD the
   knoll STILL stands ~13 m proud inside the coverage hole even with no
   pad (the visible defect survives the pad's disappearance). The
   three-pass parity requirement the lane identified is accepted as the
   work; the tile arm from step 1 doubles as its acceptance frame:
   mesh/patch at (30.1136676,31.4086362) graded toward the bounding
   features (quote before ≈106.3 → after), lawful terraces only at the
   pocket rim, census delta row-classed.
3. **_PAD_HOST_ROLES widening is DEFERRED** (the counterfactual shows
   ~0 adoption movement; the 11 uncorroborated families need their own
   evidence). Goes to the owner report as a design option, not a lane
   act.
4. **Corpus hazard interim law (lead):** pad-seating acceptance runs
   TILE-FRAME ONLY until the request-sidecar's data-vs-product status
   is owner-ruled; the three-corpora finding (owner 851 / lane 842 /
   artifact-emitted 365 with 91 owner-only) is recorded in
   DEFERRED_VERIFICATION and the owner report. Patch-only pad numbers
   may not be quoted as acceptance.
