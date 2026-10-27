# The pad fill — the ground under a pad unit's off-pad plates and pier prints (issues #712, #1003)

Lane m13, 2026-10-19. Owner law: RULINGS 2026-10-19ap ("a paved slab above the
lot below is met by FILLING the ground to the slab with banks, not by draping
the slab", #712); owner Q33 2026-10-20 for #1003 ("flatten it all"); RULINGS
2026-10-03e ("whole viaduct at T3's level; grade the ground to the landings",
#290). Consumer census per RULINGS 2026-08-30l, written before any consumer was
edited. Analysis credit: lane m10 named the need (a noded region for the
plate's off-pad part held at the pad's level, a 1:3 bank the shelf/collar way)
and suggested the shelf; the ramp LANDING (`planar/landing`) is the nearer
existing member — a flat groundside pad face at a block's datum + an authored
y, inside a 1:3 collar, held one-way in stage 2 — so the fill is minted there.

## 1. What was measured (HECA capture `frames/m2/HECA.pkl`, patch `m2base.osm`)

* **#712, site 30.1096365, 31.3889978.** `Seasonal_Terminal/side_walk.obj`
  (`dsf:obj3368`) is ONE plate component, y 0.15, height 0.00, no feet, 15,761 m2
  outline: 7,155 m2 on the held block `building5` (96.27-96.63 m), 1,932 m2 over the
  lot `gap:3`, 6,670 m2 over ground no face grades. The base-slab witness refuses it
  (rule 1: no feet), so nothing grades under it. The site reads INSIDE `gap:3`, whose
  rim falls to 88.84 m. `Seasonal_Terminal/asphalt_3.obj` comp 1 (the first #712 plate,
  23,716 m2, 10,258 on `building5`) is the same shape.
* **#1003, site 30.112939, 31.397394.** The site is inside `gap:5/s0` (14,960 m2, ramps
  94.11-101.85 m). The T3 road viaduct `T23/T3_road.obj` belongs to block `building4`
  (`bridge_family.viaduct_units`, 113 voters); its ground prints off the block are the
  `T23/Plastic.obj` strips and pier bases (y -0.19 / -0.29, feet at the objects' zero),
  32 feet of them standing in `gap:5/s0`, running from `building7` (101.85) out to the
  kerb islands (`small_roads:-19747` 96.5-97.2, `-19777`, `gap:53`).

The two share one mechanism: a rigid structure seated on a held block puts parts
AT ITS ZERO off the block, and the ground there is not at the block's level.

## 2. The rule

THE PAD FILL. For every held platform block `B` (`Registries.held`, the blocks the
ramp landings already read):

1. **A PLATE RIDING THE BLOCK.** A partition component (a genuine part or a thin plate,
   `airport/slab_plates`) AT THE OBJECTS' ZERO (`|base_y| <= [placement]
   base_slab_base_y_max_m`), THIN (`height <= base_slab_max_height_m`), a PLATE and
   LEVEL by its own faces (side share `<= base_slab_max_side_share`, top relief `<=
   split_tol_m`, not an elevated deck: base-slab rules 5-7), never a deck member, whose
   outline lies on `B` by at least `base_slab_min_m2`. A component is never cut apart,
   so it is seated on `B` (§16f (4) plurality: the pad is the evidence); its OFF-BLOCK
   part is ground at `B`'s datum + its `base_y`.
2. **A VIADUCT'S GROUND PRINTS.** For a deck of block `B` (`viaduct_units`, 10-03e),
   every part of its voters (members sharing the deck's frame, centre inside its
   footprint) that has feet AT ITS ZERO (`|foot y| <= landing.BAND_M`) and stands off
   `B`. Prints closer than two bank widths (`2 x [building_pad] platform_collar_max_m`)
   are ONE fill (two fills at one level cannot bank down and up between them); its
   extent is the convex hull of the group — the ground the viaduct stands on — at `B`'s
   datum + the group's lowest foot y.

Each fill, less every pad, the airside and a bank's minimum width of it
(`[design] bank_min_width_m`) and what an earlier landing took, in pieces of at least
`max(grid^2, 1 m2)`, IS A RAMP LANDING (`<unit>/landing<k>`, registered in
`Registries.landings` with `kind` = `plate` / `piers`): the landing's own level rows
(`constraints/platform.landing_rows`, stage 2, one-way against the block's datum
column), its own 1:3 collar out to `platform_collar_max_m`
(`platform_collar_rows`), and its own lot cut (`landing_cut`). A late cell (gap piece,
road ribbon) is clipped by it at pass C as by any pad. No new row, no new law value.

## 3. Consumer census (every pass that reads the affected geometry)

| # | reader | reads | with a pad fill | ruling |
|---|---|---|---|---|
| 1 | `planar/landing.landing_regions` | blocks, vias, taken | mints the fills after the deck landings (deck refs unchanged), collars in its PASS 2 | the ONE derivation site |
| 2 | `planar/landing_runout.landing_runouts` | deck landing plats | fills are NOT handed in (a fill has no ramp foot) | deck only |
| 3 | `planar/landing.landing_cut` | `landings` + collars | cuts `parking_lot` base regions under a fill as under a landing | unchanged code |
| 4 | `planar/ribbons._ribbons_pass_c` (`clip_f`) | rigid faces | a gap piece / road ribbon over a fill is clipped by it (rigid role) | unchanged — the fill is a pad face |
| 5 | `planar/apron_shelf.shelf_regions` | `held` = base + pads + late | a shelf never takes a fill | unchanged |
| 6 | `constraints/platform.landing_vertices/landing_rows` | `landings[ref]["block"/"y"]` | holds the fill at block datum + y (hard, stage 2) | unchanged code |
| 7 | `constraints/platform.platform_collar_rows` | `#collar` faces | the 1:3 bank around the fill | unchanged code |
| 8 | `constraints/pads.pad_datum_withdrawn` | `landing_vertices` | a fill's vertices take no DEM datum | unchanged code |
| 9 | `classify/ramp_runout._landing_faces` | `/landing` faces | a fill is occupied ground for a ramp run-out | unchanged |
| 10 | late stage `gap_follow` / `terrace_cut` | standing rings | a fill is a PAD-class station; the lot beside it follows it within its cap | unchanged |
| 11 | `classify/gap_mint` slab pieces + `constraints/slab_weld` | base slab open parts | a base slab's piece over a fill is clipped at pass C; the rest welds as before | unchanged |
| 12 | `airport/placement_read` (object stage) | landing / collar faces | a body over a fill reads the fill (the block's level + y) | unchanged — what 19ap asks |
| 13 | `airport/slab_drape.drape_plan` | ground relief under a slab | the ground under a filled plate is level: no drape (19ap) | unchanged code |
| 14 | `pipeline/publication._landings` (sidecar) | `landings` | the fills appear, `deck` = `plate:<member>#<comp>` / `piers:<deck>` | unchanged code |
| 15 | `pipeline/capture_state` `landings` registry | carried | carried | unchanged |
| 16 | census `check_grade` | `building` faces, collars | a fill is a flat pad face; its collar a bank | unchanged |

Airside: no fill takes the airside or a bank's width of it (the landing's own
`base_hard`), so stage 1 cannot see a fill.

## 4. Not in this rule

* Feet of a unit that is NOT a viaduct of its block (e.g. a terminal's lamp posts in a
  lot) are not read: no planar-time witness says which block they ride.
* A plate on no held block (an OB- ground plate on raw ground) keeps the base-slab /
  drape path.
