# Round 12 — a bridge seats by its DECK TOP, and a bridge is ONE body

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r12bridge**. Pre-ship mode
(docs/RULINGS.md); deviations STOP-and-report. Parallel lanes own
`bridges.py` (r10tunnel) and `flat_site_mode.py`/`O4_Airport_Elevation_
Insets.py` (r11kmci) — this lane must touch NEITHER file. Its files:
`src/auto_patch/post_mesh.py`, `src/auto_patch/object_anchor.py`,
`src/auto_patch/object_terrain_assembly.py`,
`src/auto_patch/object_terrain_features.py` (finding only).

## Measured attribution (2026-08-11 read-only recon; replay against the
## current +25+051 mesh reproduces the pack deltas to the millimetre)

Owner: OTHH bridges at 25.2483641,51.6153252 / 25.2515518,51.6203517 /
25.2530024,51.6174763 seat "with the bottom edges at our 4 m ground …
we want the bridge deck (top) there; the lower parts are supports that
go down to the water." Mesh under all three anchors = 0.00 m (canal);
land Z0 = 3.96 m.

* CLASS A (`OTHH_Bridge_05`, `_04`; control `_01`): classifier
  TERRAIN_CARRIED, abutments certified, R6-3 `bridge_abutment_seat`
  FIRED with abutment grades 5.089 / 4.051 / 3.851 (medians of 10 mesh
  samples; the measurement REPRODUCES and is not the defect). The seat's
  delta (post_mesh.py:1435-1438) is `abutment_grade − anchor_ground` —
  it lands the authored **y = 0 plane** at abutment grade. Only a FLUSH
  deck has deck-at-y=0: Bridge_01 (deck_top_y −0.31) reads right;
  Bridge_04/05 (deck_top_y +1.067 / +1.187) land deck-proud with
  supports lifted to 2.28 / 3.27 m instead of descending to the water.
  post_mesh.py:1385-1386 already computes
  `expected_deck_top_m = abutment_grade + deck_top_y_m` — recorded,
  never used in the delta.
* CLASS B (the 255° shared-anchor family `OTHH_Bridge_02/_03/_06`, 30
  placements): classification REFUSED ("piered viaduct: no solid
  geometry reaches effective grade (≤0.5 m) within 35 m of the start
  deck end(s)") ⇒ generic Phase-2 y-bake, whose delta
  (object_anchor.py:3276) is `structure_ground −
  anchor_ground_by_resource` — the same y=0 datum assumption — applied
  PER STRUCTURE, tearing one bridge across seats 0.00 / 1.63 / 3.96 m.
  `OTHH_Bridge_04_LOD0_004.obj` is additionally absent from the R6-3
  candidate member set entirely: never baked, ~7.9 m under its siblings.
* Frame split (recorded, NOT fixed this round): post-mesh
  classification runs with `pavement_polygons_longitude_latitude=None`
  (object_terrain_assembly.py:1064) ⇒ height fallback
  (object_terrain_features.py:2588) says TERRAIN_CARRIED where
  pipeline-time coverage 0.0 says AMBIGUOUS (:2591). Two frames, two
  verdicts, one pack.

## The laws

### R12-1 THE SEAT DATUM IS THE DECK TOP

`bridge_abutment_seat`'s delta becomes: the authored DECK-TOP plane
lands at the abutment grade —
`delta = (abutment_grade − candidate.deck_top_y_m) −
anchor_ground_by_resource[...]` (the existing AGL/anchor frame handling
stays exactly as it is; only the datum term is added). The recorded
`expected_deck_top_m` is then the ACHIEVED deck top — assert their
equality in the record (materiality 0.01 m). Bridge_01 (deck_top_y
−0.31) MOVES +0.31 under this law — that is correct (its deck today
sits at 3.544, below its own 3.851 abutment grade) and the old
behaviour is NOT pinned.

### R12-2 ONE BRIDGE, ONE RIGID SEAT — INCLUDING REFUSED VIADUCTS

* A bridge FAMILY (the classifier's member set for one structure /
  shared placement anchor) seats as ONE rigid body: one delta for every
  member. Per-member or per-structure-median deltas that tear a family
  are forbidden.
* A REFUSED piered-viaduct family (class B) does not fall to the
  generic per-structure y-bake: it takes the SAME R6-3 rigid deck-top
  seat, using the family's member geometry for its deck ends/abutment
  lines (the classifier computes these even when the contract is
  refused — reuse its records; if a refused family genuinely has no
  measurable deck member, it keeps today's y-bake and mints a counted
  `bridge_seat_fallback` finding naming why).
* MEMBER-SET COMPLETENESS: every placement of the family's resources
  joins the seat (the `OTHH_Bridge_04_LOD0_004` gap — find the
  member-set predicate that dropped it, name it in the commit message,
  and close it so a family member can never be left behind at a
  different altitude). If the predicate turns out to be a deliberate
  exclusion with a reason this spec doesn't know, STOP and report.

### R12-3 THE FRAME SPLIT IS RECORDED (nothing else)

When post-mesh classification derives a verdict for a resource whose
pipeline-time cache carries a DIFFERENT verdict, mint one counted
finding (`bridge_verdict_frame_split`: resource, both verdicts, both
coverage inputs). Do NOT change which verdict is used — with R12-1 the
TERRAIN_CARRIED seat is correct for class A, and re-sourcing verdicts
is a separate design decision for the owner.

## Tests (tests/test_round12_bridge_deck_datum.py, new; plus the
## directly-covering files once: test_object_bridge_terrain,
## test_post_mesh, test_object_anchor, test_object_cluster_seating,
## test_supporter_fate)

1. Datum twin: flush deck (deck_top_y −0.31) seats within 0.31 m of the
   old law; raised deck (+1.19) seats deck-top AT abutment grade, and
   `expected_deck_top_m == achieved` within 0.01.
2. Rigid-family twin: three members with different per-structure
   grounds get ONE delta; the tear (0.00/1.63/3.96) is impossible by
   construction.
3. Refused-viaduct twin: a refused family with measurable deck members
   takes the rigid deck-top seat; one with none keeps the y-bake +
   `bridge_seat_fallback` finding.
4. Member-completeness twin: a family resource absent from the old
   candidate set is seated with its siblings.
5. Frame-split twin: differing pipeline/post-mesh verdicts mint the
   finding; agreeing verdicts mint nothing.
6. OFFLINE REPLAY (the recon's method, as a test fixture where
   possible): the class-A arithmetic pins — Bridge_05 deck top 5.089,
   Bridge_04 deck top 4.051, supports descending below deck by the
   authored 3.0 m extent.

## Acceptance

The seat runs only at the end of `build_mesh` (O4_Mesh_Utils.py:327) —
no harness patch build exercises it. Acceptance is therefore: (a) the
unit twins above; (b) an OFFLINE REPLAY against the current +25+051
mesh and pack bytes (the recon reproduced current deltas to the
millimetre — your replay must reproduce the NEW deltas:
Bridge_05 y0-delta 8.589→7.402, Bridge_04 7.851→6.784, Bridge_01
7.352→7.662, class-B family one shared delta) — write the replay in
your scratch dir, quote every number; (c) the owner's next in-app
+25+051 build is the in-sim acceptance (pre-ship law). Do NOT run a
tile build.

## Bookkeeping

Lead writes the DEFERRED_VERIFICATION line at merge (no tile build, no
in-sim arm, replay-only acceptance; the bridges.py:10080 crossing-floor
decline remains untouched and ledgered from R6-3). Version stamps are
the lead's at app build.

## AMENDMENT 2026-08-11 (lead ruling on the implementer's STOP:
## WATER NEVER AUTHORS A BRIDGE DATUM)

The class-B viaduct declines the R6-3 seat because its deck-end sample
lines lie over the canal (54/74 samples 0.00 m, median 0.00, drop 0.00
< the 1.00 reseat threshold). The datum law gains one clause: an
abutment stands on LAND —

* abutment samples falling inside the mapped water union (the SAME
  OSM water ∪ sea reader R6-1's pad clip uses — one authority, do not
  re-derive) are DISCARDED and never author the grade;
* when a deck end's line loses its samples to water, the line WALKS
  LANDWARD along the deck axis (away from the span) in the existing
  sample-step increments, up to 60 m, until ≥ 4 non-water samples
  exist; the abutment grade is their median;
* a family with no such samples within the cap at EITHER end keeps
  the y-bake + `bridge_seat_fallback` finding (the landed limb) —
  that limb's behaviour is unchanged.

For OTHH class B this walks off the canal onto the 3.96 m land: one
rigid family delta seating the deck top at the land grade — the
owner's stated intent verbatim ("deck (top) at our 4 m ground, the
lower parts go down to the water"). Twins: a canal-end family seats
deck-top at land grade with supports descending below the water line;
an all-water-within-cap family keeps the fallback + finding. Replay:
quote class B's one shared delta, the seated deck-top (expect ≈3.96),
and the per-member world y ranges showing supports below 0.5 m. This
is a NEW ruled target — the attempt cap resets.

## AMENDMENT 2 — 2026-08-11 (lead rulings on the implementer's two
## frame STOPs; supersedes the conflicting figures above)

**B1 (STOP-2 — THE CORRECTED DELTA IS ADOPTED).** `deck_top_y_m` is an
EFFECTIVE height (AGL + authored y, metres above the anchor terrain)
while `anchor_ground_by_resource` is world-frame (mesh(anchor) + AGL):
the frozen formula double-counted AGL and left the deck top where the
old law left the y=0 plane. The law's delta is
`grade − crest_effective − mesh_at_anchor`, one delta per family. The
spec's pinned figures 7.402/6.784/7.662 are SUPERSEDED by the
pack-byte-verified pins: Bridge_01 **4.1589**, Bridge_05 **3.9013**,
Bridge_04 **2.9831**; seated deck tops at their grades
(3.8515 / 5.0885 / 4.0506); Bridge_04 supports at **−2.59 m**, below
the 0.00 m water line. "Class A must not move" applied to the water
clause, not to this frame correction.

**B2 (STOP-1 — THE MESH'S OWN WATER BITS ARE THE AUTHORITY).** OTHH's
canal is mapped as coastline, not `natural=water`, so the OSM union
Amendment 1 prescribed cannot see it (the implementer's band sweep:
every reach ≤ 200 m reproduces class A, every reach ≥ 300 m breaks
Bridge_04 — the single-sided buffer under- or over-covers, never
fits). At POST-MESH time the frame-correct water authority is the
MESH the seat samples: a sample landing on a triangle carrying the
mesh's sea/water attribute bits is a WATER sample and is discarded
(this replaces the OSM-union test for the seat; Amendment 1's walk,
cap, ≥4-sample floor and fallback limb are unchanged). If the mesh
reader genuinely cannot expose per-triangle attributes at the sample
point, STOP and report — do not approximate water by elevation.
Expected class-B outcome: the 21 canal-floor samples discard, the
landward walk fires, grade ≈ 3.96 land, one rigid delta, supports
below the water line.

**B3 (ratified).** The obj8 (east, SOUTH) handedness fix and the
"band is the reach of the question" fix (longest abutment line + walk
cap, in place of R6-1's 2 km pad constant) are both APPROVED as
landed.
