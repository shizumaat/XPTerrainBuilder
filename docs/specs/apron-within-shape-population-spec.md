# Apron within-shape population = movement surfaces (Fable spec, 2026-08-21;
# owner ruling RULINGS 2026-08-21b "an apron's cap is owed on its movement
# surfaces — never on a generic ring-vertex pair", answer (ii))

Basis (read 2026-08-21, scratchpad repop.py over seven patches): of HECA's
`within_shape apron|apron` airside rows, 1,442/1,584 (transect arm) and
1,055/1,089 (battery) are generic ring-vertex chords (p90 412-449 m, max
680 m) that merely cross a spine corridor cover; the ruled population —
frontage chords (building→spine) — is 441-545 rows (chord ≤ 200 m). Under
the ruled population HECA airside reads 839 (main) / 849 (transect) / 844
(RM+transect): the arms converge; the spread was the generic class. SPJC
189→155; CYXY unchanged. Stand entries have no engine object — a stand's
lead-in IS its frontage chord (`apron_terrace.corridor_cover` :681-687), so
the population is frontage chords.

## The law (ONE predicate, both readers — `grade_law.classify_pair`)

1. For a pair whose owning shape's role is APRON, `classify_pair`
   (grade_law.py:2635) SKIPS the pair unless it is a FRONTAGE CHORD:
   exactly one endpoint is a frontage vertex (a node the apron ring shares
   with a building ring, participating in a frontage EDGE — production's
   predicate, anchors.py:734-786 / `_frontage_box`; never proximity) and the
   other endpoint lies inside the spine corridor cover
   (`apron_terrace.corridor_cover`, its own radius) with chord ≤
   `BUILDING_REACH_CORRIDOR_M` (config.py:6324, the frontage band's own
   reach). P1 (both endpoints frontage vertices of one pad) is ring-adjacent
   and takes the existing ring-adjacent branch — keep that branch's
   behaviour; report its count.
   The corridor-cover radius used here (13.5 m = APRON_TERRACE_CORRIDOR_HALF
   _WIDTH_M + APRON_TERRACE_JOINT_CLEARANCE_M) is an EXISTING constant
   reused, flagged for owner ratification in the report — no new constant.
2. Every other apron pair is NOT LAW. It leaves `sc.edges`
   (grade_graph.py:2464) and therefore `G.edges`, the lockstep bake and the
   census's `iter_shape_grade_constraints` (check_grade.py:1527) in one
   move, because both readers call `classify_pair`. Twin: the census and
   the bake enumerate the same apron pair set on a synthetic apron with two
   pads and one corridor.
3. Runway, taxiway, JUNCTION and building within-shape laws are UNCHANGED
   (ruling clause 4). The lane REPORTS what rule 1 would do to
   junction|junction (HECA 93/96 generic, short chords) — numbers only.
4. The route-metric (RM) budget is NOT applied; the frontage chord's budget
   is today's: `BUILDING_FRONTAGE_MAX_GRADE` clamp (grade_law.py:2728) over
   the Euclidean chord, via `pair_grade_budget_m`. RM is to be re-evaluated
   on this population separately (ruling clause 3) — expected moot.

## The solve

5. Removing generic pairs from the LAW does not remove smoothing: the warm-
   start carrier regularisation keeps the full pair graph ("it smooths a
   seed and claims nothing", RULINGS 2026-08-15 band-carrier). Do not add
   a replacement regulariser. Report `airside_value_delta` vs the battery
   patch so the surface change is visible; the in-sim item for the owner
   is "apron interiors between corridors now follow the seed, not a 1 %
   all-pairs law" — name the HECA aprons with the largest interior change.
6. The projection-law certificate's `over_cap`/both-hard counts will FALL
   (fewer law edges); report both arms.

## Lockstep artifact

7. `pair_caps` rows gain a family tag: export `edge_family`
   (grade_graph.py:3038) alongside each row (`[[ll],[ll],budget,family]`),
   so a frontage chord is addressable in the sidecar and the census can
   assert that every priced apron pair is a baked frontage chord
   (`priced N / baked N / foreign 0`). Register the key in
   `SIDECAR_LAW_KEYS` (test_harness twins enforce this).

## Acceptance (lane off main; composed censuses via the harness)

8. Twins: (a) generic apron pair skipped, frontage chord kept, P1 on the
   ring-adjacent branch, on a synthetic apron + 2 pads + 1 corridor;
   (b) census and bake enumerate identical apron pair sets (lockstep);
   (c) junction/runway/building pair sets byte-identical to today;
   (d) sidecar family tag round-trips; (e) zero-building apron yields zero
   within-shape law edges (and the build still runs — the carrier keeps
   the smoothing).
9. Builds: CYXY, SPJC, HECA (one arm each). Expectations from the
   subtraction read: CYXY 75a (unchanged), SPJC ≈155a, HECA ≈839a; these
   are EXPECTATIONS — the solve also changes, so report census_rows_diff vs
   the battery patch per family with GONE/NEW, and explain any NEW airside
   row (a within_shape row that is not a frontage chord is a defect; rows
   in other families are the surface moving under fewer constraints —
   attribute, do not fix). Per-airport ruling: airside must not exceed the
   2026-08-21 battery bars (75 / 189 / 1,487) — trivially — AND must not
   exceed the subtraction expectation by more than the NEW-row attribution
   can explain.
10. The kept HECA frontage rows with grade > 5 % (34-64 rows, max 43-57 %):
    list them (way, building, chord, grade) — they are seat/anchor defects
    for the next docket, not this lane's fix.
11. No timing claims; no shared-repo writes; kill switch
    `O4_APRON_WITHIN_SHAPE_FRONTAGE_ONLY` default ON, flag-off arm = today.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; a census/bake
pair-set mismatch is a STOP (fix the predicate, never the count); any
within_shape apron row that is not a frontage chord after the change is a
STOP.

## AMENDMENT A1 (Fable, 2026-08-21; owner ruling RULINGS 2026-08-21c) — interior = 5 %

Measured on lane/compose (apronpop + transect): SPJC 189→551 airside, HECA
1,167 / CYXY 67 pass. Mechanism: with the generic pairs REMOVED the apron
interior has no law; the transect rows move the rings by metres and the
frontage chords absorb it (201 of 233 new SPJC rows genuine chords). §1-2
are amended:

1a. `classify_pair` does NOT skip a generic apron pair. It returns the
    pair with cap = `fan_ramp_law_cap` (5 %; `config.fan_ramp_law_cap`,
    the 2026-08-05 constant) when neither rule-1 condition holds, and the
    strict apron cap when the pair is a frontage chord. The ring-adjacent
    branch keeps its behaviour at the strict cap (R19-5's catch; report
    its count). The pair's budget is `pair_grade_budget_m` at that cap
    over the Euclidean chord; the 60 m `APRON_BODY_CHORD_MAX_M` body gate
    and the other existing skip rules stay as they are (they predate and
    are orthogonal to this ruling — report how many interior pairs the 60 m
    gate removes, since a 680 m chord at 5 % is still 34 m).
2a. Both readers therefore still enumerate the same pair set as today's
    bake MINUS nothing; only the CAP changes on the interior class. The
    census's within_shape rows gain `cap_pct` so a row says which cap
    priced it; the sidecar family tag from §7 stays.
5a. §5's "no replacement regulariser" is superseded: the 5 % interior law
    IS the interior's constraint. The carrier regularisation is unchanged.
9a. Expectations: HECA ≈ 839 + (generic rows > 5 %: a few dozen from the
    2026-08-21 read, median generic grade 1.66 %); SPJC ≈ 155 + its
    generic rows > 5 % (its 34 were all class (a) — report their grades);
    CYXY unchanged. Composed with lane/transect (the arm that matters):
    per-airport airside ≤ the battery bars 75 / 189 / 1,487 on ALL three;
    SPJC is the gate.
Everything else stands (twins updated to the cap semantics: a generic pair
at 3 % passes, at 6 % fails; a frontage chord at 3 % fails).

## AMENDMENT A2 (Fable, 2026-08-21) — ring-adjacent apron edges are interior

Compose-v2 measured: no violation on any airport carries the 5 % cap; HECA
+112 vs bar is ~648 apron RING EDGES over the strict 1 % — the class A1 §1a
kept strict on R19-5 grounds (the lead's clause, not the owner's). Under
2026-08-21b a ring edge between two non-frontage vertices IS a generic
pair, and R19-5's catch (the 148 % ring edge) survives at 5 %. §1a is
corrected: the ring-adjacent branch takes the INTERIOR cap (5 %) unless the
edge is a frontage edge (P1, both endpoints frontage vertices — strict) or
lies within the spine corridor cover at both ends (a corridor-crossing
edge — strict; report the count). Twins: ring edge at 3 % passes, 6 %
fails, 148 % fails; frontage edge at 3 % fails. Re-run CYXY/SPJC/HECA
composed; acceptance unchanged (75 / 189 / 1,487). This is a correction of
the lead's own clause, not a third attempt at the mechanism.
