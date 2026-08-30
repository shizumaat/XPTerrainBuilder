# HECA round 6b — rework under the 2026-08-30b rulings
# (continuation of round 6; lane report + owner rulings of 2026-08-30)

Base: lane/hecar6 (carries the held item-4 fix `99e47d62`, the item-1
revert `d6bc40b2`, and the round-6 twins), rebased/merged onto main
with RULINGS 2026-08-30b (`96f939df`). Six work items; the four owner
rulings are LAW, not hypotheses. SITE-FIRST at the round-6 coordinates.

## Item 4 rework — up-build goes airside-frozen (ruling 1)

The `_chord_band` pinned-generator up-build is mechanism-confirmed but
HELD: it moved 2,053 solve-owned airside nodes (worst 3.92 m) and +249
census rows. Rework so groundside builds UP without touching
solve-owned airside values. Attribute the propagation channel first
(which weld/adoption path carried the up-build into airside — the
road-weld split in `airside_value_delta.py` is the instrument), then
constrain: pinned airside generators are read-only sources, never
receivers. Acceptance: `airside_value_delta.py` control→arm shows ZERO
solve-owned airside nodes moved >0.01 m; the junction 2675 contact
step stays closed (≤2 % over the 5.4 m, as achieved); quote the low
site 30.1055367,31.3994026 — the ring's far body (~104.1) capping the
near arm is expected to persist; if the site stays below the owner's
"couple of metres" ask with airside frozen, quote the residual and the
capping mechanism — that residual goes back to the owner, not into a
third iteration.

## Item 2 — band cuts groundside (ruling 2)

Implement: the taxiway adjacent-ground zones 1–2 band claims its
lawful width regardless of shape ownership; groundside shapes are CUT
BACK by the band (the band's graded surface replaces the groundside
sliver inside its width). Remove the `s.role != "groundside_pavement"`
static-block exclusions (`adjacent_ground.py:6307`, `:6928`) only as
far as the ruling requires — groundside becomes visible to the
corridor as ground to be graded FROM the pavement edge; the
DEM-inside-corridor "emit NOTHING" economy stays for lawful ground.
Site: 30.1125699,31.4053664 — junction 586 (104.28) ↔ groundside 2836:
the 7.51 m/1.01 m step at the shared edge becomes a zones-1–2-lawful
grade; cliffs remain lawful beyond the graded strip (zone 3).
Mind the blast radius: this touches every airport's adjacent-ground
emission — the synthetic twin must cover a taxiway abutting a
groundside shape at a large DEM offset, and the census guard is the
five-airport sweep AT MERGE-BATCH TIME, not per-lane.

## Item 3 — scoped road sever (ruling 3)

Sever ONLY where an OSM service road shares ≥1 vertex with the
groundside ring at 11-dp identity (HECA: way −13192 shares
30.114178800,31.404126000 with ring −12831). The severed corridor
(road width per the road family) becomes a service_road under the
merged free-road ramp law, welding to 30.1123727,31.4059687 per the
owner's round-6 ask. §H3 stays OFF and refuted — do not re-arm it; do
not sweep for evidence beyond the identity-vertex trigger. Site
acceptance at 30.1118886,31.4064793: the point classifies as road,
ramping smoothly (free-road law) instead of dropping 7 m from apron
585.

## Item 5 — width test beside the area test (round-6 spec law)

`groundside._separate_groundside_from_airside` drop test
(`groundside.py:6912`) gains a WIDTH criterion: a separated part
thinner than half a service-road width along its airside frontage
(the round-6 spec's law) is dropped — merged into the adjacent airside
grading — regardless of area. Demonstrate interventionally on a cut
fixture first (the 332 m² / 0.69 m mean width / 480.9 m frontage
ribbon at 30.1157630,31.4116825 is the fixture); shape 3151's 108
sliver pieces (1,424 m²) are the acceptance population.

## Item 6 — groundside gap-fill blocker (ruling 4)

Add groundside_pavement to the gap-fill blocker set
(`gap_fill.py:181` open question now RULED); spine graded_strips 3225/
3227 stop emitting over 2837/2838. Then the role question: run
`classify_report.py` on the closing build and quote the scorer's
verdict for 2837/2838 with own-side evidence (inside aerodrome −98,
2837 inside taxiway rings −128/−129, parking positions 31–35 m); if
the scorer still says groundside, report the evidence read that
misfires — re-roling beyond what the scorer supports is a STOP.
Also quote the 2836↔building79 38.8 m² overlap state after the round.

## Item 1 — building79 demonstration (round-6 spec law)

Demonstrate the merge mechanism: dump the cluster outline either side
of `terminals._close_building_outline` (BUILDING_OUTLINE_FILL_R=110 m)
for the building79 facade cluster. If the close is the minter, fix at
the mechanism level: the close must not permanently swallow
inter-building pavement — five buildings emerge as five pads with
pavement between them scored as pavement (round-6 Family B law). If
the dump refutes the close, report the refutation and the next
candidate — do not iterate blind (attempt cap applies).

## Acceptance

Round-6 coordinates quoted first, current configuration. Synthetic-
first; ONE closing HECA build; controls via ledger (the round-6
control at `5cbab135`/`3d8e477af793` is NOT valid for this base —
build the new base arm once, it is the round's control). Item 4
additionally gates on airside_value_delta solve-owned = 0 >0.01 m.
Census not worsened beyond attributed re-roling/sever effects; item-2
family deltas quoted separately (the band-cuts-groundside law will
re-role rows by design). Below-bar = STOP with residual quoted.
