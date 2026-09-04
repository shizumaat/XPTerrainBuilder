# auto-patch-v2 — M6b report: the DECK SIGNATURE by geometry, the abutment seat, the witness floor (RULINGS 2026-09-04k)

Lane `v2deck` (Fable, owner 2026-09-04 03h), branch `lane/v2deck` off main
`461617e2`. Every v2 file ≤ 1,000 lines (new `airport/deck_signature.py`
546; `emit/rebake.py` 420, `planar/structures.py` 951, `law/model.py` 869);
no environment read in v2; nothing under `auto_patch_v2` imports v1; every
number below is a `structures.toml [bridge]` / `[rebake]` key with its
ruling. Twins: `tests/auto_patch_v2/test_m6b_deck.py` (20), m6a / m4b / m4 /
law / model / planar twins and the v1 hook twins green (96 + 20). Commits
§8, on the branch, not merged.

## 0. Site first — OTHH, tile +25+051, `--engine v2`, `O4_DSF_OBJECT_REANCHOR=0`

Closing build `OTHH_tile_v2deck_measure` (ledger `tools/run_ledger.jsonl`,
tree `4de2d8ab…`-family, exit 1 at step 3 masks — the shared-repo guard's
known refusal; steps 1 vector 104.7 s, 2 mesh 38.1 s with the v2 re-seat
run on the new mesh, 0 objects written). The build's own result sidecar
(`Patches/+20+050/+25+051/o4_v2_rebake_result_OTHH.json`) carries the
seats of commit `20f3b569`; the plan-side fixes that followed (§4, and the
candidate-promotion deletion of §2) were replayed on the SAME mesh through `tools/v2_rebake_replay.py seat`
(`scratchpad/OTHH.rebake.final.json`) — identical bridge seats, so both
are quoted once:

| family (one anchor spelling) | owner-accepted on disk | **v2 seat (closing mesh)** | Δ | how the seat was founded |
|---|---|---|---|---|
| Bridge_01 (all 12 placements — the two below-grade pier pieces M6a skipped and the two sheets included) | **+4.1589** | **+4.186** | +0.027 | deck top `y` 3.1685 (`LOD0_002`/`_003`, v1's crest 3.1927 on `CLUTTER_000`) at the abutment grades 3.47 / 3.96 |
| Bridge_02/03/06 interchange (all 32 placements) | **+0.9576** | **+0.9576** | 0.000 | coalition 4/12 deck members within 0.25 m — `Bridge_06_LOD0_000/001`, `_CLUTTER_000/006` (crests 3.003–3.016) at the 3.962 bank, 8 outliers (canal-floor samples) — v1 amendment 4's coalition, member for member |
| Bridge_04 (5) | **+2.5672** (the R12 in-sim pin was **+2.9831**) | **+2.994** | +0.427 vs disk, **+0.011 vs the R12 pin** | deck top 4.868 (the kerb strip `LOD0_001` joins the 4.65 plate under effective-height binning, as v1) at grades 3.73 / 3.96 |
| Bridge_05 (5) | **+1.6450** | **+1.731** | +0.086 | deck top 4.687 at grades 2.14 (west bank, graded down to the canal) / 3.71 |
| BusStation (12) | authored (v1: stays) | −0.102, **stays** (below the 1.0 m threshold) | 0 | feet, coalition 5/6 |

Bar: within 0.10 m per bridge — **met for Bridge_01, the interchange,
Bridge_05, BusStation; missed for Bridge_04 by 0.43 m against the DISK.**
The disk's +2.5672 is a later v1 re-bake on a mesh whose abutment stood
at 3.634 (delta = grade − crest − anchor ground); the state the owner saw
and accepted in the sim on 2026-08-11 (memory `othh-bridge-deck-datum-r12`)
was +2.9831 with the deck top at 4.0506, and v2 reproduces THAT to 0.011.
The law-invariant quantity — deck top AT the abutment grade — holds by
construction for all four (materiality 0.01). Families: ONE delta each
(§3). Every family's members: written together in the lane-local proof
(§5). Census 0/0, acceptance §6.

## 1. The signature rule (`airport/deck_signature.py`; `[bridge]` keys)

`ATTR_hard_deck` stays PRIMARY (`deck_kind = "flag"`). A family with no
flagged member is read for a plate:

1. FAMILY = one anchor spelling (frame mm + AGL) — the rigid body the seat
   uses (memory `shared-datum-pack-authoring`).
2. DECK PLANE = the largest-area bin (`deck_plane_bin_m` 0.5) of
   near-horizontal solid faces (`deck_plate_normal_y_min` 0.7, |n_y|:
   OTHH's decks are not consistently wound — signed normals move the
   interchange's plane from 3.0 to 1.0) standing `deck_min_elevation_m`
   (2.0) above the family's lowest feet, binned by EFFECTIVE height
   (y + AGL) as v1's `_dominant_height_plane` did; bins within
   `deck_plane_area_tie` (0.9) of the largest tie and the higher wins (a
   slab's underside equals its top); plane area ≥ `deck_min_area_m2`
   (200).
3. Per member: PLATE = union of its plane faces closed at `deck_close_m`
   (1.0); minimum rotated rectangle → axis, length, width, the two END
   LINES (abutments) when length ≥ `deck_min_span_m` (10); DECK TOP = the
   highest corner of its plane faces (v1's profile maximum); STATIONS =
   ≤ `deck_stations` (32) near-horizontal faces of the plate's own
   components spread along the axis; profile per `deck_profile_bin_m`.
4. SPANNING EVIDENCE (`deck_spanning_evidence`): a mapped bridge way
   (highway/railway, `bridge != no` — the one predicate
   `planar/structures.py` now imports) RUNNING ALONG a plate
   (`deck_way_cover_min` 0.5 of its length, projected on the axis) with
   the carried plates holding `deck_way_carried_area_min` (0.5) of the
   family's plane; or an emitted below-grade region under the plate
   (`deck_signature.promote`: the re-seat plan promotes a CANDIDATE of a
   foreign family over a basin ring). No evidence → CANDIDATE (recorded,
   feet law).

Evidence per OTHH bridge (recorded per object, `deck_evidence`; the
per-member crests reproduce v1's `deck_member_records` to the millimetre —
`Bridge_02_CLUTTER_000` 3.07059, `Bridge_03_LOD0_001` 2.30832,
`Bridge_06_LOD0_000` 3.01635, …):

| family | plane (eff.) | plates | carried by | plane area | way cover / carried share |
|---|---|---|---|---|---|
| Bridge_01 | 3.1685 − 3.5 | `LOD0_002` 1,940 m² (100.8 × 23 m), `LOD0_003` 772, `CLUTTER_000` 1 | trunk way −500 | 2,713 m² | 0.67 / 100 % |
| Bridge_02/03/06 | 2.406 | 17 plates: `Bridge_03_LOD0_000` 3,153 m² (191 × 94), `Bridge_06_LOD0_000/001` (243 m), … | trunk ways −490/−492 on `Bridge_03_LOD0_000` / `_CLUTTER_000` | 4,836 m² | 0.66–0.69 / 72 % |
| Bridge_04 | 4.653 − 3.801 | `LOD0_000` 1,380 m² (79 × 18.5), `LOD0_001` 142 (kerb), `LOD0_003` 80 | tertiary −8147 | 1,460 m² | 0.84 / 100 % |
| Bridge_05 | 4.618 − 3.5 | `LOD0_000` 1,425 m², `LOD0_001` 115, `LOD0_004` 78 | tertiary −8149 | 1,618 m² | 0.97 / 100 % |

Refused at OTHH (all 6,636 families read; 4 accepted, 114 candidates):
`Terminal_Parking` (38 members, 52,836 m² plane at 4.1) — way −985 runs
100 % along the 90 m `VCN_002` kerb road but carries **2 %** of the
family's plane (a mosque stands on the slabs: under the first draft it
seated the family −4.14 by deck, the clearance test fooled by the mosque's
faces 8.55 m up); `TerminalRoads/Terminal_Base` (466 members, one anchor)
— the way crosses the slab at 0.23 cover; every fuel farm, hangar, cargo
shed, control post, the BusStation: no bridge way. `Drainage`/
`Dewatering` families: candidates, then EXCLUDED as basin families (§4).

## 2. Object-bridge law in the planar map and constraints

A signature deck fills `PlacedObject.hard_deck` / `deck_top_z` exactly as
a flagged one, so `planar.basins.object_decks` → `planar/structures.py`
`_object_deck_intervals` → `Deck(datum="deck_top")` →
`constraints/structures.py`'s Offset rows (cut continues under the deck at
bore datum, deck top clears the ramp by `bridge.clearance_m` 5.1 /
`clearance_minimum_m` 4.2) run unchanged for it (M4's twinned law,
`test_m4b::_object_bridge_map`, now reachable without the flag). At OTHH
no accepted deck crosses a tunnel corridor (`object_decks 0`).

REFUTED AND DELETED (`3e868062`): the first draft also promoted a
CANDIDATE plate crossing a tunnel corridor to an object deck inside the
tunnel pass ("the crossing is its evidence"). At OTHH 22 terminal slab /
kerb-road plates cross the four terminal tunnels; promoting them pushed
every climb past the slabs, the tunnel pass emitted 4 tunnels where main
emits 8, and the portal acceptance read 7/8 (`site_reach` B3 at 1,725 m)
against the base-arm control's 8/8 at `461617e2` (worktree `v2deckctl`,
patch `OTHH_20260904T090856`). The tunnel under a building is the pad
law's, never a bridge's. The closing TILE build carried that draft (its
patch: tunnels 4); the patch-only rebuild after the deletion (§6) is the
acceptance proof — the bridge seats read the canal banks, 1.5 km from the
terminal tunnels, and are the same on both.

## 3. The seat (`emit/rebake.py`; `[rebake]` keys)

* SIGNATURE DECK: the abutment grade is sampled along each deck-end line
  every `abutment_sample_step_m` (5); a sample on a water triangle is
  discarded; with fewer than `abutment_min_land_samples` (4) on land the
  line walks LANDWARD (away from the other end) a step at a time to
  `abutment_walk_max_m` (60) — R12 amendments 1–2, the mesh's own water
  bits the authority (Bridge_02's far ends walked 20–30 m to the bank;
  `_CLUTTER_006` found no land in 60 m and contributes nothing). Member
  delta = grade − (anchor ground + AGL + deck top); the family takes the
  agreeing coalition within `agreement_window_m` (amendments 3/4; a
  tie or no ≥ 2 coalition REFUSES the deck seat and the feet law
  governs, with the finding). Records per member: walked metres, land /
  water / off-mesh samples, grade — the evidence trail.
* CLEARANCE CONFIRMATION (`deck_min_clearance_under_m` 1.0): after the
  seat the mesh under SOME station must lie 1.0 m under the seated face
  or be water (Bridge_01/04/05: stations over the canal; the interchange:
  the ramps' stations 2–5 m over the bank). A plate whose every station
  stands on the ground it covers spans nothing → refused, feet law (the
  canopy twin).
* ONE ANCHOR, ONE DELTA: deck members found; foot members follow rigidly
  (`deck founds the family: 7 foot member(s) follow rigidly`); a deck
  family's below-grade pier pieces (`Bridge_01_LOD0_002/003`, footings
  under the canal bed, skipped as "below-grade solids" in M6a and so left
  4 m below their deck) and its sheets (`LOD0_004`) join the family
  (`deck_family_seats_rigid`; R12-2 completeness — v1 wrote all 12).
* DECK SEATS ARE THRESHOLD-EXEMPT (`deck_seat_threshold_exempt`): the
  interchange's +0.9576 is under `min_delta_m` 1.0 and would otherwise
  "stay" — i.e. be REVERTED to authored by v1's reversion pass, a 0.96 m
  drop of a state the owner accepted; v1's `bridge_abutment_seat` wrote it
  under the same generic threshold. Feet seats keep the threshold.
* WITNESS FLOOR (`founding_min_witnesses` 8, `founding_min_share` 0.25 of
  the unit's LARGEST member's land witnesses — relative, so a sign on
  four feet still seats): TerminalRoads_03_004's 4 witnesses cannot found
  the 400-object family; `Qatar_DutyFree`'s 16-witness founder (+12.2 in
  M6a) demoted → +1.37; `GA_Hangar6` demoted. Members under the floor are
  named in a finding.
* WATER NEVER FOUNDS (unchanged); a unit with no founding land witness
  is HELD (Bridge_05 is no longer held: its deck ends read land).

## 4. Plan-side rules (`airport/rebake_plan.py`)

* BASIN FAMILIES EXCLUDED WHOLE (`basin_family_excluded`; m6a Q3) — and
  the exclusion now FIRES: the basin records name members by resource
  PATH, the plan compared ids (`terrain_adapted 0` in every M6a count).
  At OTHH the eight Drainage / Dewatering units (M6a: Dewatering_01
  +15.1, in the closing build's own sidecar Dewatering_02 −13.6 "by deck"
  over its own pit) are gone: units 99 → 91.
* A member whose genuine solids reach `basin.admission_depth_m` (2.5)
  under the local ground never founds its family, floor plate or not:
  `TerminalRoads_03_005` (84 witnesses, 4.7 m under, a skirt with no
  plate) founded the 403-member family +5.96 once the witness floor had
  stopped the 4-witness piece; M6a's skip caught only floor-carrying
  objects. TerminalRoads now +1.89 (367 members, feet law) — a residual
  of the feet law, reported (§7).
* Candidate promotion over basin rings (`below_grade` kwarg from the
  pipeline: `(ring polygon, owner paths)`), owners never promoted by their
  own pit.

## 5. The lane-local write proof (`scratchpad/write_proof.py`)

A copy of the 2,077 files the plan's units touch (live `.obj` +
`.anchor_bak` + provenance) under the scratch dir, the final plan
re-rooted onto it, seated against the closing build's mesh, then v1's
writer through the hook's `_decision_from_seats` → `object_rebake.apply`:

| | |
|---|---|
| run 1 | 502 resources written (11 units: the four bridge families by deck, seven by feet), 7 earlier v1 bakes reverted (units v2 leaves authored), backups 1,021 → 1,021 (never overwritten) |
| run 2 | 502 written, 0 reverted, **byte-identical to run 1**, backups 1,021 |
| bridges on the copy | live − authored `y`: Bridge_05 +1.7313, Bridge_04 +2.9939, interchange +0.9576, Bridge_01 +4.1858 — every member of each family one value |
| `object_rebake.restore` | 1,021 files put back, every live == its backup, provenance removed |
| the REAL pack | untouched: 1,229 backups, 63 live ≠ backup, no file newer than the session; 109 bridge-file hashes recorded |

`modify_custom_airports` was on in the copy run; the closing tile build
ran under `O4_DSF_OBJECT_REANCHOR=0` (env snapshot in the ledger line) and
wrote nothing. The owner's Custom Scenery was never a write target.

## 6. Census and acceptance

| | |
|---|---|
| OTHH oracle census (`census.py`) on the closing tile patch, on `OTHH_v2deck_patch` (artifact `5e44ba24eec6`, body `e867bef9c51d`, 75.5 s) and on `OTHH_v2deck_patch2` after `3e868062` (artifact `9ad5b9c3db45`, body `c8efbd3f506f`, 71.4 s, v2 verify 0 rows, tunnels 8 of 18 mouths as on main) | **LAW-TRUE 0, ADJUDICATED 0 / airside 0 — PASS**, all 27 families 0 |
| `tunnel_portal_acceptance.py --profile OTHH` | base-arm control at main `461617e2`: **8 PASS / 0 FAIL / 12 SKIP**; the closing tile patch and `OTHH_v2deck_patch` (with the candidate promotion): 7 / 1 / 12 (`site_reach` B3 1,725 m); **`OTHH_v2deck_patch2` after `3e868062`: 8 PASS / 0 FAIL / 12 SKIP — unchanged** |

## 7. Open questions (≤ 3)

1. **Bridge_04's datum: disk (+2.567, grade 3.634 on a v1 mesh) or the
   in-sim R12 pin (+2.983, deck top 4.0506)?** v2 gives +2.994 against the
   3.73 / 3.96 banks of its own mesh — the law "deck top at the abutment"
   is exact; the bar's number belongs to a mesh that no longer exists.
   Owner: is the 0.43 m a defect (then the bank grade near Bridge_04 is
   the question, not the seat) or is the bar re-based to the mesh?
2. **The interchange's accepted +0.9576 buries the Bridge_06 ramp feet
   (y −1.99) 3 m under the 3.96 bank and leaves Bridge_03's deck 0.4 m
   under the ground** — v2 reproduces v1's coalition exactly, but the
   feet law says +3.4…+5.6 (piers on the bank). The physical reading
   (ramp feet at the bank ⇒ ≈ +3.96, decks 2.6 / 9.5 m over land) is a
   different bridge; only the owner's sim eye decides.
3. **TerminalRoads (367 members, one anchor) +1.89 by feet** after the
   witness floor and the deep-skirt rule (M6a +6.35): the family mixes
   elevated kerb roads (feet 12.75 m up), ground slabs and underpass
   pieces — the anchor family is not one rigid body. v1's welded-structure
   unit or a "feet on the same plane" split is the owner's call (m6a Q2).

## 8. Commits, ledger keys, not done

Branch `lane/v2deck`: `20f3b569` (signature, plan, seat, law, 15 twins),
`eb177e62` (deep skirt never founds), `095c356e` (log line), `cb90d665`
(carried-area rule, threshold exemption, path-matching exclusion),
`f260b8de` (sheet members join), `3e868062` (tunnel-pass candidate
promotion deleted), `6578107b` (the plan's family flag read a stale
variable: the six bridge sheets were skipped in the full pack), plus this
report. Run ledger:
`tools/run_ledger.jsonl` — tile `OTHH_tile_v2deck_measure` (exit 1 at
masks, env `O4_DSF_OBJECT_REANCHOR=0`), patches `OTHH_v2deck_patch` (artifact
`5e44ba24eec6`) and `OTHH_v2deck_patch2` (`9ad5b9c3db45`), the base-arm
control at `461617e2` (worktree `v2deckctl`, patch `OTHH_20260904T090856`,
left in place for the spawner).

The closing build's after-audit reported 12 shared-repo writes under
`Elevation_data/-20-080/S13W078_bathymetry_band` and `Masks/-20-080/-13-078`
— tile −13−078 (SPLP), another lane's concurrent build, cross-attributed
to this run's window (the memory's "app builds cross-attribute" class);
this build touched +25+051 only and its masks step refused before writing.

NOT done: the five-airport sweep (orchestrator); the Fable-5 optimisation
review of the plan stage (M6a: 16.7 s — unchanged here, the signature adds
one face pass per resource inside the same 20–40 s OBJ8 read; the parse
cache stays owed); a v2 tile build with the write enabled against the real
pack (the owner's in-app rebuild is the in-sim acceptance); a tunnel-ramp
crossing by a real object deck (twinned only, as in M4); resolving §7.
