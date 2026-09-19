# PACK READ ONCE, PACK READ FAST — spec + whole-pipeline optimisation review

Fable 2026-09-18, lane `packfast-spec`, base main `2cdfa31f`. Owner order RULINGS
2026-09-18m (1). This IS the Fable-5 whole-pipeline review `Ortho4XP/CLAUDE.md` §6 calls
for. Inputs: `docs/findings/pack-read-profile-20260918.md` (measured; not re-derived),
RULINGS 17k / 17o / 17w, spec §46 (1 mm quantum, byte identity) and §51 (frame entry —
lane `frameentry` is implementing it now; everything here sits ON TOP of it).

DESIGN ONLY. No `src/` edit is on this branch. Four throwaway measurements were taken
for design numbers (parse-only or pickled-input; nothing heavy; the `frameentry` TNCM
capture was running, so no replay was started). They live in
`/Users/noah/XPTerrainBuilder/.lanes/packfast-spec/` (`sig.py`, `attach.py`, `mst.py`,
`sig_{TNCM,TFFG,LEMD}.pkl`) and are labelled **[M-new]** below; everything labelled
**[F]** is the findings document's number.

---

## 0. THE REVIEW IN SIX SENTENCES

1. **The owner's observation is right and it has a name: the MANY-SMALL-COMPONENTS
   resource.** One placement of one `.obj` that contains tens of thousands of
   disconnected little solids. TNCM: 40 such files are 96,328 of 153,384 placed
   components (62.8 %) [M-new]. **TFFG is one file:
   `TFFG/Objects/Flora/Tree1Foliage.obj`, 139,451 components — tree LEAVES, median plan
   size 0.44 m — 88.6 % of the airport** [M-new]. LEMD has 4.5 % of its components in
   such files, which is why the large airport is fast and the small islands are not.
2. **Two thirds of TFFG's 1,127 s is one function, and it falls 600× with the output
   ORDERED-LIST-IDENTICAL.** `model/ground_fit.neighbour_pairs` on the real n = 86,592
   input: shipped 345.2 s [F] → 0.57 s [M-new], every edge, its order and its length
   equal, 52,846 tied lengths included (§B.1). No owner question, no movement.
3. **The 29.2 M `intersects` calls are ONE list comprehension** —
   `wall_geometry.py:102 _straight_runs`, 28,440,458 of them [M-new, from the saved
   profile]. And 51 s of `distance` is 6,868 calls at one site
   (`object_cut.py:258`). Three exact bulk rewrites, ~90 s of TNCM (§B.3).
4. **The partition cache has never hit for anyone**, and fixing its file name plus its
   invalidation walk is a day's work that makes every REBUILD of TNCM skip 255 s and
   every rebuild of TFFG skip 470 s (§B.4).
5. **After those, what is left cold is the contact partition over scatter** (TNCM
   231 s, TFFG 459 s). Making it *fast* is a rewrite; making it *not happen* is an
   ADMISSION law — but that is a change of BEHAVIOUR (what happens to a bush), two
   candidate discriminators were measured here and ONE WAS REFUTED, and the seat of a
   scatter object is the owner's to state (§D). It is sliced so the dry census lands
   first and the wiring waits for the answers.
6. **Native code is NOT WORTH IT now.** OBJ8 parse is 2.5 % [F]; GEOS is already C++;
   every measured hot spot is either an algorithm (O(n²) → O(n log n)), a scalar loop
   over a C library that has a bulk entry point, or work that should not be done at
   all. The measurement that would reopen it is stated in row N1.

---

## A. THE RANKED OPTIONS TABLE

Gains are wall seconds on the findings' un-profiled stage table where one exists
(TNCM 301.6 s / 7.08 GB, TFFG 1,126.7 s / 18.50 GB for load + read + partition +
groups [F]); gains inside `planar/build` are from the cProfile run ÷ 1.2 (the findings'
own overhead factor) and are marked ≈. "Ship" = freeze / signing / CI cost on the three
OSes. "§46" = risk to the byte-identity gate.

| # | option | TNCM | TFFG | GB | impl. cost | ship | §46 risk | verdict |
|---|---|---|---|---|---|---|---|---|
| **1** | **MST: Delaunay-candidate heap Prim reproducing the shipped tie rule** (§B.1) | 39.6 → **0.8 s** [M-new] | 646.5 → **2.0 s** [M-new] | ~0 | 1 new module ~90 lines + 2 call sites | none (`scipy.spatial.Delaunay` is already imported by `geom/triangulate.py`, `cKDTree` at module level in `planar/shapes.py` — frozen today) | **NONE — ordered edge list identical on both real maxima**; the theorem in §B.1 says why | **DO NOW** |
| **2** | **Partition cache: name by airport, memoise the pristine walk, atomic write** (§B.4) | warm rebuild −255 s (read 23.5 + partition 231.2) | warm −470 s | — | ~40 lines | none | none (a hit returns the pickled product of the same code) | **DO NOW** |
| **3** | **Bulk GEOS at the three attributed scalar sites**: `_straight_runs` (28.4 M `intersects`, 48.5 s cum), `object_cut.py:258` (6,868 `distance`, 51.4 s cum), `skirt.py:202` (2.02 M `distance`, 13.6 s cum) (§B.3) | ≈ −90 s of `planar/build` | unmeasured (its build was not profiled) | small-object churn ↓ | ~60 lines | none | `_straight_runs`: none (same predicate, same order). The two `distance ≤ tol` → `dwithin`: a pair exactly AT the tolerance may flip; declared, twin-pinned | **DO NOW** |
| **4** | **Process model**: `max_tasks_per_child=1`, DEM handed to workers as a memory-mapped `.npy` instead of pickled `initargs` (§B.5) | 0 s | 0 s | **−12.8 GB idle** [F] per finished worker; −485 MB × (workers − 1) DEM copies [F] | ~50 lines in `auto_patch/driver.py` | none (stdlib, py ≥ 3.11; the freeze is cp313) | none | **DO NOW** |
| **5** | **ADMISSION — the SCATTER class**: a many-small-components resource never reaches the ε-contact narrow pass, `plan_hull`, groups / `ground_fit` / foot rows / cluster pads, or any structure reader; it seats by plan-box PIECES (§B.2) | partition 231 → est. **45–60 s** (parts 101,922 → ≈ 20 k; pairs_tested 2.26 M → est. < 0.3 M); `planar/build` readers ≈ −60 s | partition 459 → est. **15–25 s** (parts 76,930 → ≈ 3 k); groups → ~0 even without row 1 | TFFG est. **18.5 → < 6 GB** (NEEDS MEASUREMENT — the findings do not attribute RSS by stage) | 1 new module + 6 edit sites; consumer census §B.6 | none | **DECLARED MOVEMENT**: LP rows that scatter bodies state today vanish; cluster-pad outlines lose the bushes chained to them; seat bodies of scatter change. Bounded in §B.2 (6) | **DO NOW in two steps**: 5a the dry CENSUS (no behaviour) now; 5b the wiring after owner Q1/Q2 (§D) |
| **6** | **Per-pack, frame-independent on-disk cache** of object-space products (§B.7) | warm, with row 2 already hitting: ≈ 0 extra. COLD second AIRPORT of a pack: −(parse + components + rings + intra-member contacts) of the SHARED resources only = 12.3 MB of 2.05 GB [F] → **≈ 0 s at TNCM↔TFFG** | same | mmap lets two children share pages: est. −0.5…−1 GB at OTHH | large: a new store, a format, invalidation, the `contact.partition` split into an object-space and a frame pass | none | the split reorders union-find skips → the cross-member contact SPANNING SUBSET changes (connectivity-equivalent, not identical); rings move ≤ 0.71 mm (§51 class) | **DO NEXT** — its real customer is OTHH (1,247 resources × 14,218 placements, 17w) and any pack whose airports share heavy resources; TNCM/TFFG gain almost nothing from it because their heavy files are placed ONCE |
| **7** | `plan_hull` memoised per `(resource, component)` in object space, in-process only (the part of row 6 that needs no disk) | ≈ 0 (every heavy TNCM file is placed once) | ≈ 0 | — | ~40 lines + `frame_entry.enter` per placement | none | rings move ≤ 0.71 mm (rotation after simplification instead of before); lands in §51's re-baseline window | **DO NEXT**, with row 6 (OTHH is the measurement) |
| **8** | **Coarser proxy for the footprint ring**: convex hull for a component under a size floor instead of `union_all` + `_outward` (3 GEOS constructive calls per blob) | ≈ −40 s cold (`plan_hull` 57.1 s cum [F]) IF row 5 is refused; ≈ −8 s after row 5 | similar | — | ~15 lines | none | outward-only by construction (the hull contains the outline — 14j's law holds); units can only MERGE more, never split; declared | **NOT WORTH IT after row 5**; reopen only if Q1 refuses the scatter class |
| **9** | Vectorise `_narrow_pass` row assembly (CSR-stacked, 4.47 M `_narrow_rows` + `_inside` calls = 91.4 s cum [F]) | ≈ −60 s IF row 5 is refused; ≈ −10 s after | ≈ −100 s / ≈ −5 s | buffers bounded by `contact_batch_rows` | high — the batch-then-union order is the spanning-subset law (I-20, 10i (1)); a rewrite must reproduce the skip decisions | none | high if the flush order moves | **DO NEXT, only if** the post-row-5 profile still shows `_narrow_pass` > 20 s anywhere |
| **10** | Per-resource parallelism across cores for the cold object-space work (rings, intra-member contacts) | bounded by the largest single file (HillBush = 40 % of parts) unless chunked by component range | same | + one parse per worker | medium; needs row 6's object-space split first | none | none if results are merged in resource / component order | **DO NEXT, after row 6** |
| **11** | One pack reader in the PARENT, children receive / mmap the read | duplicated downstream work is 2,867 placements [F] ≈ 2–3 % of either airport | same | — | large (`ResourceCache` is not picklable cheaply; 985 MB parse at OTHH, 14v) | none | none | **NOT WORTH IT** as stated; row 6's mmap store is the lawful form of the same idea |
| **N1** | Native OBJ8 parser + component labeller (C++/Rust `Utils/{mac,win,lin}` binary, subprocess) | parse 9.4 + components 7.3 = **16.7 s ceiling** [F] (5.5 % of 301 s) | 11.3 s ceiling | — | new tool, 3 toolchains, a wire format | mac: a new signed hardened-runtime Mach-O (the `sign_app.sh` inner-first discovery covers `Utils/`, so it signs, but it is a new CI build job ×3 like `build-osmium.yml`) | the welding (`np.round(v, 3)`, `np.unique`) must be reproduced bit-for-bit | **NOT WORTH IT.** Reopen when parse + components exceed 25 % of a pack stage AFTER rows 1–5 (at TNCM that would need the stage under 67 s with parse unchanged — plausible; re-measure then, and first try `np.loadtxt`-free slab parsing, which is Python-level) |
| **N2** | Python extension wheel (pybind11 / Cython) for the narrow pass or the MST | MST: row 1 already takes it to 0.8 s. Narrow pass: see row 9 | | | build matrix ×3, vendoring | **mac notarisation**: a `.so` inside the bundle signs fine; a vendored `.whl` does NOT (submission `0e71fbdf`, [F] §6 d) — it would have to be built in CI per OS and collected, never vendored | new compiled float code = new §46 surface (FMA contraction differs arm64 / x86 unless `-ffp-contract=off`) | **NOT WORTH IT** |
| **N3** | numba | jit of the Prim loop ≈ 100×, but row 1 is 600× in pure scipy | | | adds numba + llvmlite (~150 MB) to three freezes | llvmlite's JIT needs `com.apple.security.cs.allow-jit` / unsigned-executable-memory entitlements under the hardened runtime — a notarisation-policy change for the whole app | JIT float semantics per CPU | **NOT WORTH IT** |
| **N4** | A native MST | — | — | | | | | **NOT WORTH IT** (row 1) |
| **12** | Placement-radius prefilter | **REFUTED [F §5.1]**: −86.5 % placements, parts +13 | | | | | | **DELETED** — not to be retried |
| **13** | "Attached to a structure" discriminator by 3-D box proximity for the scatter class | **REFUTED [M-new]**: `HillBush.obj` reads 100.0 % attached, `Tree1Foliage.obj` 93.9 %, LEMD's T4 struts only 24.7 % — large flat neighbours' boxes cover everything; it separates nothing | | | | | | **DELETED** — §B.2 (3) makes false positives harmless instead of trying to eliminate them |
| **14** | `partition_cache._pristine_entries` walks the 8.8 GB pack per fingerprint | folded into row 2 (memoise per process + per `(root, dir mtimes)`) | | | | | | DO NOW (row 2) |
| **15** | `dsf.read_dump` re-parsed per child (2.07 MB, ~1 s [F]) | −1 s | −1 s | | | | | **NOT WORTH IT** |
| **16** | `skirt._plan_union` — 722 unions, 38.5 s cum [M-new]; frame-independent, ALREADY carried in the partition cache's `derived_state` | warm: row 2 delivers it. Cold: row 5 removes the scatter resources' share | | | | | | covered by rows 2 + 5 |
| **17** | `obj8_clip` unions (`_union_rings` 48,380 / `_clip_component` 57,410 / `_clip_both` 40,247 calls, ≈ 20 s cum each, nested) | cold: row 5 removes scatter components from every clip reader | | | | | | covered by row 5; re-profile after |

**Expected walls (pack read + partition + groups; cold unless stated).** Est. = computed
from [F]'s stage table, not measured; each implementing slice measures its own.

| after | TNCM | TFFG | OTHH (structures stage 1,386 s / 29.18 GB, 17w) | LEMD (378 s / 4.77 GB) |
|---|---|---|---|---|
| today | 301.6 s / 7.08 GB | 1,126.7 s / 18.50 GB | 1,386 s / 29.2 GB | 378 s / 4.8 GB |
| row 1 | 263 s | **482 s** | −(its `neighbour_pairs` share; max n 7,956-class → a few s) | same |
| + row 3 | 263 s (+ `planar/build` ≈ −90 s) | 482 s | NEEDS MEASUREMENT (its `_straight_runs` share is unknown) | same |
| + row 5b | est. **75–95 s** | est. **35–50 s** | unchanged (its driver is heavy INTERIOR meshes — §48's customer, not this class) | est. −5 % |
| + row 2, REBUILD | est. **25–40 s** | est. **10–20 s** | the cache exists there already and hits for a one-airport tile | same |
| memory target | ≤ 5 GB | **≤ 6 GB** (the owner's production line is 25 GB, 17j; the bar set here is "no airport's pack stage above 2 × LEMD's 4.77 GB except OTHH, which §48 owns") | §48's bar (≈ 9.5 GB) stands | — |

Neither island reaches the 60 s per-airport budget on a COLD first build by rows 1–5
alone (`planar/build`'s structure readers are another ≈ 150–250 s at TNCM [F §1.1]);
they are moved from "cannot complete / 19 minutes" to "minutes", and rebuilds to under
the budget. The budgets are adjudicated in the final profiling round (CLAUDE.md §6,
suspended in part); this table is the input to it.

---

## B. THE DESIGN — DO-NOW SET

### B.1 THE NEIGHBOUR GRAPH (row 1)

**The law is unchanged**: `neighbour_pairs(pts)` returns the edges of the feet's
Euclidean MST *as the shipped Prim emits them* — start at index 0; the next vertex is
the unseen one with the smallest `best`, LOWEST INDEX on a tie; `link[v]` is the
EARLIEST-ADDED tree vertex achieving `best[v]` (strict `<` update); edges are emitted in
pick order as `(link[u], u, best[u])` with `best` = `math.hypot`. Ties are not a corner
case: a rectangle's four feet tie by construction, and the TFFG input carries 52,846
repeated lengths in 86,591 edges [M-new]. `ground_fit` reads the ORDER (its `worst`
is the first edge reaching the maximum residual), so the list, not the set, is the
contract.

**Why a candidate graph reproduces it exactly.** (i) Any edge `ab` of any MST has an
empty open lune; a point `c` on the closed diametral disk of `ab` satisfies
`|ac|, |bc| < |ab|` strictly, so it lies in the lune — hence the closed diametral disk
of an MST edge is empty, the edge is strictly Gabriel, and it belongs to EVERY Delaunay
triangulation of the points, cocircular degeneracies included. (ii) At every Prim step
the minimum crossing weight `m` is achieved only by edges that are each in some MST
(cut property), so every `(u, v)` with `d(u, v) = m` across the cut is a Delaunay edge.
Therefore the set of minimum candidates, the lowest-index winner, and the
earliest-added `link` are the same on the Delaunay graph as on the complete graph, at
every step. A different VALID triangulation (Qhull on arm64 vs x86) cannot change the
output: platform-stable by construction, not by luck.

**Frozen interface.**

```
# NEW  src/auto_patch_v2/geom/feet_graph.py        (numpy + scipy allowed in geom/)
def neighbour_pairs_fast(pts: Sequence[tuple[float, float]]) -> list[tuple[int, int, float]]
# EDIT src/auto_patch_v2/model/ground_fit.py
def ground_fit(feet, y_zero, dem_at, bank_slope, *, pairs=neighbour_pairs) -> GroundFit | None
```

`model/` keeps importing neither numpy nor scipy (M0 §1): the pure Prim STAYS as the
reference and the default; the two callers (`planar/group.py:419`,
`constraints/foot_rows.py:317`) pass `pairs=feet_graph.neighbour_pairs_fast`. ONE
derivation site for "which feet are neighbours": `feet_graph` DELEGATES to the
reference for `n < 64` (no Qhull set-up cost, and the small case is the twin's anchor).

**The algorithm, normative.** (a) exact-duplicate points are grouped
(`np.unique(axis=0)`); Delaunay runs on the UNIQUE points, **translated by their mean**
— un-centred, Qhull's precision merging discards 85,538 of 86,592 TFFG points as
"coplanar" (measured; the coordinates are ~10⁶ m with 0.4 m spacing). The translation
feeds Qhull ONLY; every length is `math.hypot` on the ORIGINAL `pts`, which is what
makes `d` bit-equal to today's. (b) adjacency = Delaunay neighbours expanded over
duplicate classes, plus zero-length edges inside each class. (c) heap Prim keyed
`(d, v)`, strict-`<` relaxation, lazy deletion. (d) **GUARDS → fall back to the
reference, counted in the group report** (`mst_fallback`): `QhullError`; a non-empty
`tri.coplanar`; fewer than `n − 1` edges out; `len(unique) < 3`; any non-finite input.
A fallback on n > 20,000 additionally logs one line (it is the 345 s case).

**Measured [M-new]** (`mst.py`, the two real maxima the findings pickled):

| input | n | dup pts | tied lengths | shipped [F] | numpy Prim | **this** | ordered list identical | max \|Δd\| vs numpy |
|---|---|---|---|---|---|---|---|---|
| TNCM | 27,376 | 2,824 | 4,106 | 32.4 s | 2.54 s | **0.16 s** | **yes** | 2.2e-16 (= `np.hypot` vs `math.hypot`; this form uses `math.hypot`, i.e. equals SHIPPED) |
| TFFG | 86,592 | 18 | 52,846 | 345.2 s | 25.6 s | **0.57 s** | **yes** | 5.6e-17 |

Whole airport, scaled by feet: TNCM 0.8 s, TFFG 2.0 s. The numpy Prim is NOT the
design: it is still O(n²) (TFFG 48 s) and its `np.hypot` is libm's — platform-varying
in the last ulp, which `math.hypot` (CPython's own algorithm) is not.

### B.2 ADMISSION — THE SCATTER CLASS (row 5)

**(1) What each downstream law consumes — and what a bush can give it.**

| consumer | reads | can a < 10 m disconnected solid, one of ≥ 64 in its file, ever be admitted? |
|---|---|---|
| `door_wells`, `tunnel_objects`, `sunken_roads`, `wall_corridors` / `wall_geometry`, `object_cut.read_shells`, `basins` (witness, cover), `thin_plates`, `deck_signature`, `skirt` | below-grade floors, walls with a run, plates, covers | **no law key admits one** — the smallest admitted structure element on the corpus is a sill plate 18–22 m wide (17k); the dry pair in slice 5a PROVES it per airport (structures.json byte-identical with the class excluded) rather than this table asserting it |
| `contact.partition` ε-contact + weld + abutments | every part × every part | binds a bush to whatever it overlaps — the 7,000-part / 27,376-foot body [F] |
| `planar/group.derive` → `ground_fit` | a body's feet | today a scatter body is an ELIGIBLE group of one |
| `constraints/foot_rows` | feasible on-sheet bare-ground groups | **today a bush states LP target rows** priced at `pad_flat` — the terrain is pulled to the bush's authored relief (owner Q1) |
| `planar/cluster` → `classify/evidence._pads` (14x) | bodies whose footprints touch | a bush within 0.5 m of a hotel extends the hotel's PAD outline |
| `footprint_unit` (§16g), `placement_*`, `rebake_plan`, `dsf_write` | parts, feet, rings (box where no ring) | **NEEDED** — a bush is re-seated on the terrain the patch produced; §16g keeps whatever covers a building's footprint WITH the building |
| `verify` | emitted placements | unchanged |
| v1 `dsf_reader._compute_dsf_object_buildings` (`o4_object_footprints_<tile>.cache`, row C of [F §2]) | its own v1 parse; building footprints for the inset pass | **untouched** — it never reads v2's parts; its own population is building-sized footprints |

So the answer to "what is skipped vs still needed": a scatter object needs **a box, one
foot per ground piece, and membership in its unit** — and nothing else. A fence needs
its line (10bb, unchanged). A bush needs no ring, no ε-contact, no group, no row, no
pad, no structure read.

**(2) THE PREDICATE — mechanical, per RESOURCE, frame-independent, ONE site.** New
module `airport/scatter.py`, `is_scatter(cache, resolved, law) -> ScatterReading`
(verdict + the numbers it was read from, for the report). A resource is SCATTER when
ALL of:

 * it has at least `[scatter] components_min` (**64** — `placement_atom.
   RIGID_REACH_COMPONENTS_MAX`'s own number and its own sentence: "a member with
   thousands of them is CLUTTER whose pieces are meant to stand apart") genuine
   components;
 * EVERY genuine component's authored plan-box diagonal is ≤ `[scatter]
   component_diag_max_m` (**10.0**) — or the component is LINE-SHAPED (10bb's reading,
   imported from `line_object`, never restated), so a fence file of posts + wire runs
   is one class with its posts;
 * no triangle is `HARD` / `HARD_DECK`, and the placement is not deck-family,
   plate-seated, structure-seated or a basin member (the same exemptions 14.1 rule 4
   gives the line class — applied where they are applied today, `_build_member` and
   `PackPartition.filtered`);
 * it is not already a LINE OBJECT (that class keeps its drape).

 The earliest point this is knowable is `solid_components` — i.e. after the parse,
 which is 2.5 % of the cost [F]; nothing before it (resource path, library class,
 byte size) is mechanical. It is a pure function of the file, so it lives in the
 per-resource `derived_state` today and in row 6's store later.

 **Measured coverage [M-new]** (`attach.py`, N = 64, D = 10 m):

 | airport | components | scatter components | resources | what they are |
 |---|---|---|---|---|
 | TNCM | 153,384 | **96,328 (62.8 %)** | 40 / 238 | HillBush 41,220, AG2_palms 24,089, ParkingBushes 7,614, BaggageCarts 4,020, palms, people, ferns, catering trucks, road signs |
 | TFFG | 177,110 | **154,040 (87.0 %)** | 13 / 116 | Tree1Foliage 139,451, Tree2Branch 8,074, ApronTrees 3,492, bushes, cars |
 | LEMD | 495,439 | 22,207 (4.5 %) | 24 / 394 | **FALSE POSITIVES NAMED**: `Terminal4_yellow-LEMD11` 11,537 (the T4 struts, every one 8.69–8.70 m), `Terminal4_green-LEMD23` 1,720, `Terminal4_48` 1,200 (and at TNCM `Airport/TerminalGlass.obj`, 214 glass panes of 4.3–4.5 m) |

 (Counts here are per placed component of the census, not the partition's `parts`; the
 findings' 118,485 / 101,922 are the same population after the multi-anchor drop.)

**(3) FALSE POSITIVES ARE MADE HARMLESS, NOT ELIMINATED.** The box-attachment
discriminator was measured and REFUTED (row 13). So the class's consequences are chosen
such that a T4 strut classed as scatter renders exactly where it renders today:

 * **§16g is untouched and still sees every scatter part** (its box — `rings == ()`
   already means "read the part by its box", `contact.py:96`). A strut or a glass pane
   stands inside its terminal's footprint, so it is in the terminal's UNIT and takes the
   unit's seat — "we always want to keep objects covering the same footprint together"
   (13bo) is the law that protects it, and it is not this spec's to change. A bush
   against a hotel wall moves with the hotel; a bush on a hill seats alone.
 * a scatter part is NEVER dropped from the plan, never skipped from `dsf_write` — the
   §48 sentence: *never read [by a structure law], never dropped*.

**(4) WHAT CHANGES, at ONE derivation site each.**

 * `pack_partition._build_member` reads the verdict beside the line verdict and
   returns it; `Member` gains `scatter: bool = False` and `Part` / `PlacedPart` gain
   `scatter: bool = False` (BY NAME — the positional-tail defect is recorded twice in
   that function's own comment).
 * `contact.placed_parts`: a scatter member's parts get `rings = ()`, `k_max = 1`
   foot, and are built in ONE vectorised pass per member (bulk `_place` of the
   resource's vertices, `np.minimum.reduceat` / `np.add.reduceat` over the
   component-sorted triangle order that `solid_components` already produces) instead
   of 41,220 Python iterations.
 * `contact.partition`: scatter parts are EXCLUDED from `_weld_pairs`, `_broad_pairs`
   / `_narrow_pass` and `_abutment_pairs`. Their contact edges are the PIECE edges:
   inside one member, two scatter parts whose PLAN boxes come within
   `[placement] footprint_touch_m` (0.5 — §16g's number, not a new one) are one piece
   (one `shapely.STRtree.query(boxes, predicate="dwithin")`-class bulk call + union-
   find), emitted as a spanning chain `(pid_i, pid_next)` in pid order. They are
   intra-placement edges, so `bodies_of_plan` reads a piece as a BODY with no change.
   A palm's trunk and fronds, a person's forty sub-meshes, a cart and its wheels
   overlap in plan → one body, as today. No cross-placement edge is ever stated for a
   scatter part (10bb's sentence for the line class: it never forms a rigid body with
   what it touches).
 * `planar/group._eligible`: a member all of whose parts are scatter is INELIGIBLE —
   one line beside the line-class test (`group.py:342`). No group → no `ground_fit`,
   no foot rows, no `pad_relief`. `planar/cluster`: a scatter body never joins or
   founds a cluster (so never extends a pad).
 * `basin_witness.read_objects` — THE gate every structure reader goes through (17o's
   finding) — carries `PlacedObject.scatter` and the readers' common iterator skips it.
   §48 lands the same flag-through-the-gate for interiors; whichever lane lands second
   REUSES the first's plumbing (one carried "not a structure witness" predicate with a
   reason, not two parallel flags).
 * `partition_cache._CODE_MODULES` gains `auto_patch_v2.airport.scatter`;
   `CACHE_VERSION` bumps (the frozen engine's digest is its version — §51 (4) row 17's
   argument).

**(5) WHAT IS NOT DECIDED HERE** — the two owner questions in §D. The design is cheap
under either answer to Q1 (rows from one foot per piece are still available); under
Q2 = "leave scatter where it was authored" the piece edges and feet are simply not
built and scatter members are `skipped` with a reason like the stock / multi-anchor
classes.

**(6) EMITTABILITY + BYTE IDENTITY.** Nothing here creates a shape, a role or a
region; the heightfield question does not arise. What feeds the emitted patch BODY:
(i) foot rows of scatter bodies — REMOVED (count reported per airport by 5a before any
wiring: bodies × feasible × on-sheet); (ii) cluster-pad outlines — scatter bodies
leave them (5a reports the area delta per pad). Every other body-feeding product is
unchanged by construction, and 5a's dry pairs are the proof. Expected on the five
sweep airports: HECA / CYXY near-zero (no scatter population measured there — 5a
states the number), LEMD the 24 resources above. The DSF rows of scatter placements
move (piece bodies ≠ ε-contact bodies); that is the placement stage's output, not the
patch body.

### B.3 BULK GEOS AT THE ATTRIBUTED SITES (row 3)

Call-site attribution [M-new], from `cap/TNCM.prof` (`print_callers`):

| scalar call | total | the site | cum s |
|---|---|---|---|
| `intersects` | 29,199,009 | **`wall_geometry.py:102 _straight_runs` — 28,440,458 (97.4 %)**; `door_wells.read_door_wells` 737,066 | 48.5 / 1.3 |
| `distance` | 2,034,231 | `skirt.py:202` 2,021,179 (13.6 s); **`object_cut.py:258` 6,868 calls, 51.35 s = 7.5 ms each** | |
| `unary_union` | — | `skirt._plan_union` 722 / 38.5 s; `obj8_clip` 48 k–57 k / ≈ 20 s; `memo_union` 1,559 / 17.8 s; `object_cut.shell_reading` 14 / 12.1 s | |

 * **`_straight_runs`**: `members = [k for k in idx if segs[k][0].intersects(part)]`
   inside `for part in get_parts(merged)` is |idx| × |parts| scalar predicates.
   Replace with ONE `shapely.STRtree(parts).query(seg_array, predicate="intersects")`
   per bearing cluster; rebuild `runs` by grouping the returned `(seg, part)` pairs by
   part in ascending part index, members in ascending `k`. Same predicate on the same
   geometries → the same booleans; same order → the same `runs`. EXACT.
 * **`object_cut.py:258`**: `wall.distance(point) <= probe_m` per interpolated station
   against a very large `wall`. Replace with `shapely.prepare(wall)` once +
   `shapely.dwithin(wall, points_array, probe_m)` (GEOS ≥ 3.10; the freeze is 3.13.1).
   `dwithin` is defined as `distance ≤ d`; the prepared path uses an indexed facet
   distance, so a station EXACTLY at `probe_m` may read differently — declared, and
   pinned by a twin that compares the two readings over a registered capture's shells
   (expected: 0 flips). Platform stability is GEOS's on identical doubles (§46 (3)).
 * **`skirt.py:202`**: `any(e.distance(g) <= tol for e in exteriors)` per `g` →
   `shapely.dwithin(exterior_multiline, below_array, tol)`; same note.
 * G-rule (review gate, from §51 (6)): a per-geometry Python loop over a shapely
   predicate / measurement where the operands are already in a list FAILS REVIEW; the
   array form is required in any code this spec's slices touch.

### B.4 THE PARTITION CACHE (rows 2, 14)

 * **Key of record stays per (pack, tile dump, AIRPORT)** — the payload is placed
   geometry in the airport's frame plus that airport's window; it cannot be per pack.
   `cache_path()` → `o4_v2_partition_<tile>_<ICAO>.cache`. (Two airports, two files;
   the collision [F §2 row P] is gone.) The old un-suffixed file is never read and is
   left alone (never delete user-side cache files from a build).
 * **`_pristine_entries` is computed once per process per pack root** (module-level
   memo keyed `pack_root`), and ONCE PER TILE BUILD across children: the parent
   (`auto_patch/driver.py`, before the pool) computes it for each distinct pack root
   among the tile's airports and passes the digest in the task dict; a child that
   receives one does not walk. Standalone (`build_airport.py`) computes it itself.
 * **Atomic write** (`tmp + os.replace`) so a reader never sees a torn file; still NO
   lock (two airports never share a path now; two BUILDS of one airport racing write
   identical payloads).
 * **§12a discipline**: size + mtime is the fast path; on an mtime-only mismatch with
   equal size the content hash of that one `.obj` decides (a pack restored from backup
   must not invalidate 543 files' worth of reading). The hash is stored per entry in
   the payload header.
 * **It SURVIVES row 6**: row 6 is the per-PACK object-space layer (no frame, no
   ICAO); this file is the per-AIRPORT frame layer on top of it and shrinks when row 6
   lands (it stops carrying what row 6 holds).
 * **Shared-repo law**: unchanged class — a derived self-invalidating mod-cache file
   (the module doc's own argument, 14q); lane-local under `O4_AIRPORT_MOD_CACHE_DIR`;
   never a `--refresh-data` act; the app writes it to the shared mod cache as it does
   the footprints cache. NOTE for lanes (17w's disclosed write): overlays must be REAL
   COPIES for the packs a lane rebuilds, or the write follows the symlink.
 * The log line `[partition] cache HIT|MISS|WROTE <path>` is REQUIRED on every build
   (its absence is how this went unnoticed).

### B.5 THE PROCESS MODEL (row 4)

 * `ProcessPoolExecutor(..., max_tasks_per_child=1)` at `auto_patch/driver.py:987`
   (spawn context — the only one it is lawful with): a worker exits when its airport
   returns, and its 12.8 GB goes back to the OS instead of sitting in `sem_wait` for
   20 minutes [F §1.4]. Cost: one interpreter start + imports per airport (~1–2 s),
   against airports that take minutes; a tile of many SMALL airports pays it N times —
   so it is armed only when the tile has > `max_workers` airports OR any airport's pack
   is over 1 GB of `.obj` (both known before the pool starts). `_teardown_pool`'s
   deadline logic is untouched.
 * The tile DEM leaves `initargs`: the parent saves it once to
   `<tile tmp>/auto_patch_dem_<pid>.npy` (lane / tile-local `tmp`, never the shared
   repo) and `_init_worker` opens it with `np.load(mmap_mode="r")`; removed in the
   pool's `finally`. One physical copy, shared pages, no 485 MB pickle per worker —
   which is what makes `max_tasks_per_child=1` free. If `dem` is not a plain ndarray
   wrapper the implementer STOPS and reports its shape (deviation → Fable).
 * Peak memory per airport is rows 1 / 5's business, not the pool's.

### B.6 CONSUMER CENSUS (RULINGS 2026-08-30l) — every reader of what this spec touches

Grep census 2026-09-18 (`.contacts`, `.abutments`, `.feet`, `.rings`, `PackPartition`,
`read_objects`, `cache.components|genuine|geometry`), ruled once:

| # | consumer | reads | row 1 (MST) | row 5 (scatter) | rows 2 / 4 |
|---|---|---|---|---|---|
| 1 | `planar/group.derive` | bodies, feet, abutments | `pairs=` injected; output identical | scatter member INELIGIBLE (one line) | — |
| 2 | `constraints/foot_rows` | `g.feet`, `ground_fit` | `pairs=` injected | no scatter group exists → no rows (Q1) | — |
| 3 | `constraints/pad_relief` | group feet | — | no scatter group | — |
| 4 | `planar/cluster`, `classify/evidence._pads` / `_cluster_pads`, `constraints/cluster_pad` | bodies, rings | — | scatter bodies never cluster; pad outline loses them (declared) | cached clusters ride the partition cache — version bump |
| 5 | `airport/footprint_unit` (§16g) | parts, feet, rings → box | — | **UNCHANGED, still sees scatter parts by box** — the safety of (3) | — |
| 6 | `placement_plan`, `placement_body`, `placement_family`, `placement_atom`, `placement_carrier`, `placement_cut`, `placement_deck`, `placement_record` | contacts, feet, parts | — | bodies of scatter = pieces; `placement_atom`'s reach already skips members over 64 components; **scale of the plan stage with N piece-bodies is NEEDS MEASUREMENT (slice 5b bar)** | — |
| 7 | `rebake_plan.plan` / `PackPartition.filtered` | units, contacts, abutments, screen | — | re-states the scatter verdict for the screened set exactly as it re-states the line verdict | — |
| 8 | `pack_partition.extend_partition` / `contact.extend` | new members vs base boxes | — | a scatter member extends with the same piece rule; scatter base parts are never neighbours | — |
| 9 | `basin_witness.read_objects` → `planar/basins`, `planar/build` (door wells, tunnels, shells, wall corridors, sunken roads, plates), `planar/structures`, `planar/channel_witness` | placed objects, witnesses | — | the gate skips `scatter` (5a proves byte-identity of `structures.json`) | restored from the cache on a hit, as today |
| 10 | `skirt`, `deck_signature`, `thin_plates`, `below_zero`, `line_object`, `object_cut`, `wall_corridor_probe` | `cache.components / genuine` per resource | — | never asked about a scatter resource (the gate, and `_build_member` orders the scatter test BEFORE `is_skirt` / `elevated_deck`) | — |
| 11 | `pipeline/xplat.py` stage digests | partition counts | identical | digests MOVE once (declared; re-baselined with §51's) | — |
| 12 | `solve/rows.py`, `model/airport.py` | the partition as carried | — | carried flag only | — |
| 13 | `partition_cache` | everything pickled | — | version bump + module list | path, walk, atomic write |
| 14 | v1 `dsf_reader._compute_dsf_object_buildings` / `o4_object_footprints` / `o4_dsf_object_positions` | v1's own parse | — | **untouched** | — |
| 15 | `verify/*` | emitted placements / surface | — | reads what was written | — |
| 16 | §51 `frame_entry` | every placement affine on a POLYGON | — | scatter parts carry no polygon (no ring, no witness) → fewer `enter` calls, none added | — |

### B.7 THE PER-PACK STORE (row 6) — design fixed enough to slice later, NOT in the DO-NOW set

Recorded so the DO-NEXT lane does not start from zero and so rows 2 / 5 do not paint it
into a corner.

 * **What is cacheable before the placement transform**: `ObjGeometry` arrays;
   `solid_components` (labels, per-component y range / centroid / deck flag / authored
   plan box); the scatter / line / skirt / elevated-deck / y-range / bounds readings;
   the FEET SELECTION (indices — `_feet` chooses over authored `(x, z)` and `y` [F §3]);
   component areas and object-space centroids; the LOCAL footprint rings (§51 (2)'s
   SURVIVES clause: they become frame geometry only through `frame_entry.enter`);
   intra-member weld + ε-contact edges (object space; rigid motion preserves them up to
   rounding at exactly ε — declared).
 * **Key**: pack-relative path + size + mtime of the PRISTINE source (`.anchor_bak`
   where one exists — the 08-13 ruling), content sha256 on mismatch (§12a), + a
   per-product code digest (module source bytes; the engine version when frozen) + the
   law keys the product reads (`thickness`, `contact_epsilon_m`, `contact_weld_m`,
   `[scatter]`, `[rebake] line_*`).
 * **Format**: one uncompressed `.npy`-per-array directory per resource
   (`<mod cache>/<pack>/o4_v2_res/<sha1(relpath)>/…` + a small JSON manifest), opened
   `mmap_mode="r"` — two pool children map the same pages. Not `npz` (zip members are
   not mmap-able), not pickle (no sharing, and a code-execution surface on a user-side
   cache dir), not arrow (a new frozen dependency for no gain).
 * **Size**: TNCM's 1.72 GB of windowed `.obj` text is 17.3 M `VT` rows and 5.71 M
   solid triangles [F] → vertices 17.3 M × 3 × 8 B = 415 MB (float64 — float32 would
   change the welding's `np.round(v, 3)` inputs and is REFUSED), triangles 5.71 M × 3 ×
   4 B = 69 MB, labels + per-component tables < 20 MB: **≈ 0.5 GB for TNCM's window,
   ≈ 1.1 GB for the whole 3.74 GB pack**. Owner-visible disk; the mod cache already
   holds the dumps and footprints. A size bar (14v precedent) is the owner's.
 * **Where**: the mod-cache root, i.e. lane-local under the overlay, shared for the
   app — the SAME class as the partition cache; never inside the pack (07-15), never a
   build side effect under the harness beyond what that class already is.
 * **Invalidation with §12a adoption**: adoption changes which file is pristine → the
   key's source path changes → a new entry; the old one ages out by an LRU size cap.

---

## C. SLICING FOR OPUS IMPLEMENTERS

All slices: RULINGS are law (`Ortho4XP/docs/RULINGS.md`; append to that file only, by
absolute path; re-grep the tail for the next free key right before commit). Convergence
guards in every brief: materiality floor (0.01 m / 0.01 pp; for WALL times 5 % — single
runs swing ±25 %, never A/B one run per side), attempt cap 2 per pre-registered target
then STOP-and-report, `.progress` heartbeat. Deviation from this spec → stop, report,
Fable rules. No five-airport sweep; suites: only the files named. Every slice merges
main (it will contain `frameentry` / §51) before its closing test.

**MEANWHILE-CAPTURE NOTE.** TNCM has NO capture until §51 merges (the capture dies at
`wall_corridors.py:289` [F §1.5]); lane `frameentry` was re-capturing it as this was
written. Until it is registered (`frames.py list TNCM`), the closing instruments are:
the findings' `instr_groups.py` arm (load → read → partition → groups; it completes on
both airports and needs no planar stage) run from the slice's own worktree, the pickled
MST inputs (`.lanes/packreadprofile/{npairs,TFFGnpairs}.pkl`), and LEMD / HECA dry
`python -m auto_patch_v2.planar --stage structures` pairs with COPIED dumps (17w).
`instr_groups.py` is on its SECOND use → slice S2 promotes it to
`tools/pack_stage_profile.py` with an `INDEX.md` row and a twin (tool discipline).

| slice | content | files | parallel? | blast hazards (run 2026-09-18) |
|---|---|---|---|---|
| **S1 `packmst`** | row 1 | NEW `geom/feet_graph.py`, `tests/auto_patch_v2/test_v2packmst.py`; EDIT `model/ground_fit.py` (kw-only `pairs`), `planar/group.py:419`, `constraints/foot_rows.py:317` | independent | `ground_fit.py`: 2 src importers, direct test `test_v2canopy6.py` (run it); no role / env / wire hazards |
| **S2 `packcache`** | rows 2, 14 + promote the instrument | EDIT `airport/partition_cache.py`, `pipeline/build.py` (the drive site `:392-424`, log line), `auto_patch/driver.py` (parent-side pristine digest into the task dict); NEW `tools/pack_stage_profile.py` + INDEX row + twin | **coupled with S4 through `driver.py`** — ONE implementer does S2 then S4, or S4 waits | `partition_cache.py`: tests `test_airport_load.py`, `test_v2cost2.py`. `build.py`: 17 importers, 12 direct tests — run `test_v2cost2`, `test_airport_load`, `test_v2othh3` only. `driver.py`: 13 importers; WRITES `Patches/<tile>/<ICAO>_auto.patch.osm`; env `O4_AUTO_PATCH_REBUILD` read here — do not touch either |
| **S3 `packbulk`** | row 3 | EDIT `airport/wall_geometry.py`, `airport/object_cut.py`, `airport/skirt.py`; NEW `tests/auto_patch_v2/test_v2packbulk.py` | independent — but all three files are §51 edit sites: start AFTER `frameentry` merges | `wall_geometry.py` has NO direct test importer (§51 (6)) — the new twin is its cover; `skirt.py` is in `_CODE_MODULES` (cache invalidates itself) |
| **S4 `packpool`** | row 4 | EDIT `auto_patch/driver.py` (`:733 _init_worker`, `:987` pool) ; tests `test_auto_patch_engine_dispatch.py`, `test_silent_tile_death.py` extended | after S2 (same file) | as S2's `driver.py` row; `_teardown_pool` semantics are load-bearing (2026-09-03 wedge) |
| **S5a `packscatter-census`** | row 5 predicate + DRY census, **no behaviour change** | NEW `airport/scatter.py`, `law` TOML `[scatter]` + schema, `tests/auto_patch_v2/test_v2packscatter.py`; EXTEND `tools/pack_stage_profile.py --scatter-census` | independent of S1–S4; needs S2's tool if landed, else carries it | new module; schema files co-change with `law/rebake_schema.py` precedent |
| **S5b `packscatter`** | row 5 wiring | EDIT `model/rebake.py`, `airport/pack_partition.py`, `airport/contact.py`, `planar/group.py`, `planar/cluster.py`, `airport/obj8.py` (`PlacedObject.scatter`), `airport/basin_witness.py`, `airport/partition_cache.py` (module list + version) | **ONE implementer, after 5a's census is reviewed by Fable AND Q1/Q2 are answered; after §48 `v2interiors` if that lane is live** (both thread a flag through `basin_witness`) | `obj8.py`: **55 importers / 22 test files** — run `test_m4b`, `test_v2cost2`, `test_v2canopy2`, `test_v2canopy5`, `test_v2leafframe`, `test_v2partextend`, `test_v2objsplit`, `test_v2settle` (the `Member` positional-tail twin), `test_v2doorwellperf`. `pack_partition.py`: 11 importers incl. 3 tools. `contact.py`: co-changes with `rebake.py` 78 % — check `model/rebake.Part` field order |

**Test plans.**

 * **S1** T1 reference-equality (ordered list, `==` on the float) on: the two real
   pickles; 200 seeded random sets n ∈ [2, 3000]; integer LATTICES (maximal ties);
   all-duplicate; collinear (Qhull error → fallback counted); n = 63 / 64 / 65; points
   offset by 6.7e6 m (the centring regression). T2 the guards: a monkeypatched
   `Delaunay` returning `coplanar` non-empty → fallback + count. T3 `model/` imports
   neither numpy nor scipy (AST twin). CLOSING: `pack_stage_profile.py TFFG` — groups
   stage wall named, `groups` / `infeasible` / `relief` counts EQUAL to [F]'s
   (1,134 / 956 / —). BUILD-TIME STATEMENT: removes 39.6 s (TNCM) / 646.5 s (TFFG);
   adds < 0.1 s to an airport whose largest body has < 64 feet.
 * **S2** T1 two airports, one pack, one tile → two paths, both HIT on the second
   build (tmp_path pack fixture of `test_v2cost2`). T2 a child given the parent's
   digest never calls `os.walk` (spy). T3 mtime-only touch of one `.obj` → still HIT;
   one changed byte → MISS. T4 a torn `.tmp` is ignored. T5 tool twin. CLOSING:
   `pack_stage_profile.py TNCM` twice in one lane overlay — second run prints
   `cache HIT`, read + partition wall < 5 s. BUILD-TIME: cold +0 (the walk moves to
   the parent, once); warm −255 / −470 s.
 * **S3** T1 `_straight_runs` old-vs-new on synthetic U-kerbs and on every vertical
   component of a registered capture's objects → identical `runs`. T2 `dwithin`
   vs `distance <=` over a registered capture's shells / skirts → 0 flips (a flip is
   reported, not fixed: attempt cap). CLOSING: LEMD + HECA dry `--stage structures`
   pair vs main → every array byte-identical (17w's instrument). BUILD-TIME: ≈ −90 s
   TNCM `planar/build`; LEMD / HECA stated from the pair's `wall_s`.
 * **S4** T1 a two-task pool with `max_tasks_per_child=1`: distinct worker pids, first
   worker gone before the second result. T2 the DEM reaches the worker memory-mapped
   (`isinstance(np.memmap)` on the base) and the temp file is removed on success,
   failure and teardown-by-deadline. T3 the small-tile arm (≤ `max_workers` small
   airports) keeps reuse. CLOSING: none beyond the twins (the orchestrator's app build
   reads RSS). BUILD-TIME: +1–2 s per airport only in the armed case.
 * **S5a** T1 predicate twins: a bush field (scatter), a fence of posts + wire
   (scatter via the line clause), 64 identical struts (scatter — the false positive
   is EXPECTED and named), a terminal with one 12 m component (not), a hard-deck file
   (not). T2 the census tool prints, per airport, per resource: verdict, n, d-max,
   placements; and the three numbers 5b is gated on — (i) scatter bodies that state
   foot rows today (count, rows), (ii) cluster pads whose outline a scatter body
   touches (count, m²), (iii) `structures.json` dry pair with the gate skipping
   scatter vs not, on LEMD / HECA (+ TNCM / TFFG once captured). DELIVERABLE: that
   table, back to Fable. No src consumer is edited. BUILD-TIME: 0.
 * **S5b** T1 piece rule (trunk + fronds one body; two bushes 0.6 m apart two bodies;
   chain order deterministic). T2 a scatter part inside a building footprint joins the
   building's §16g unit (the false-positive safety). T3 no scatter pid in any
   `_narrow_pass` pair, no ring, one foot. T4 `_eligible` false; no `Linear` with a
   scatter source. T5 `filtered()` re-states the verdict; `extend` twin. T6 cache:
   version bump refuses the old payload. CLOSING: `pack_stage_profile.py` TNCM + TFFG
   (walls, parts, pairs_tested, **max RSS per stage** — the memory attribution the
   findings lack) and ONE `build_airport.py TFFG` (the airport carrying the owner's
   site for this order; CYXY stays the cheap control and is not rebuilt). Bars: TFFG
   pack stage ≤ 60 s and ≤ 6 GB; TNCM ≤ 100 s and ≤ 5 GB; **plan / placement stage
   wall with N piece-bodies named** — above 60 s is a STOP-and-report (the fallback,
   pieces aggregated per `line_segment_m` grid cell, is a Fable ruling, not an
   implementer's improvisation). BUILD-TIME: the table in §A.

**Order.** S1, S3\*, S5a in parallel now (\*after `frameentry` merges). S2 → S4 one
implementer. S5b last. Row 6 / 7 / 10 lane (`packstore`) is specced from §B.7 after
S5b's profile says what is left; OTHH is its measurement airport.

---

## D. OWNER QUESTIONS

Checked before asking: the placement stage DOES consume scatter today — every scatter
body is a plan body, seated by its own feet, and an eligible bare-ground one states
foot rows; so admission must not simply drop it, and the two questions below are
genuinely intent, not mechanism.

**Q1.** Today a bush, a palm, a parked baggage cart or a standing person that sits on
bare ground inside the patch is treated like a small building: if its authored feet fit
the terrain, it states target rows in the solve and **the terrain is pulled to it**
(the 11q law, written for canopies and buildings). Should scatter ever shape the
terrain? *Recommended: NO — scatter goes to the terrain, the terrain never goes to
scatter. (A bush that overlaps a building's footprint still moves with that building,
13bo unchanged.)*

**Q2.** When a pack ships ONE object containing thousands of separate bushes / trees /
people spread over a hillside (TNCM `HillBush.obj`: 41,220 bushes over 945 m; TFFG
`Tree1Foliage.obj`: 139,451 leaf clumps), what should happen to the pieces when our
terrain differs from the terrain the author modelled them on? (a) **each piece (a tree
with its fronds, a person, a cart) is set down on our ground on its own** —
recommended; (b) the whole object stays exactly as authored (cheapest; pieces may
float or sink where the two terrains disagree); (c) something coarser — pieces grouped
per ~100 m cell, each cell set down as one.

No other question. The memory bar in §A (≤ 6 GB for TFFG-class packs; OTHH under §48's
bar) is PROPOSED in the 17w form and is the owner's number to change.

---

## E. NOT DONE

 * No replay, capture, build or tile run (a TNCM capture by `frameentry` held
   6.7 GB while this was written). Every "est." above is computed, not measured.
 * TFFG's `planar/build` was never profiled by anyone; row 3's TFFG gain is unknown.
 * Peak RSS is not attributed by stage anywhere yet (S5b's closing test does it).
 * The scatter predicate was run on TNCM / TFFG / LEMD only — HECA, OTHH, VHHH are
   S5a's. The (N, D) = (64, 10 m) pair is a measured starting point, not a fitted one.
 * The `dwithin` flip count (row 3) is asserted 0 by expectation; S3's twin measures it.
 * OTHH's share of each row is unmeasured here; §48 remains its primary lever.

---

## F. ADDENDUM 2026-09-18 — LEVEL OF DETAIL — the ground footprint is what the laws consume

Owner follow-up (verbatim): *"are you looking for ways we can filter and reduce the
number of objects we have to process, or the level of detail? Seems like we are
primarily concerned with footprints on the ground, and so for a given freestanding
building (with some space all around it), it could have thousands of components,
interiors, people, chairs, you name it, that don't matter other than they need to stay
in their same relative position to their surrounding building if we reseat it."*
RULED since §D was written (RULINGS 2026-09-18q): Q1 scatter NEVER shapes the terrain;
Q2 each piece of a many-piece scatter object is set down on our ground on its own.
Owner, on jetways (verbatim): *"Jetways have to stay connected to their terminal and
should move with it, building pad should include them to keep everything at the same
level."*

Measurements [M-lod]: parse-only, `ps` checked first (nothing heavy running),
`.lanes/packfast-spec/lod3.py` / `lod4.py`, logs `lod3_*.log`, `lod4_*.log`,
`lod3_anyy_OTHH.log`. Instrument: a 1 m label raster of HOST outlines over the ±0.05°
window; a component is CONTAINED when its four placed plan-box corners and its centre
all stand on host pixels. It is a census (1 m, box corners), not the production test.
CORRECTION to §B.2 (2)'s LEMD row: `attach.py` globbed all 21 rewritten dumps in LEMD's
mod-cache folder, so its LEMD component TOTAL (495,439) is inflated by repeated
placements; the scatter SHARE (4.5 %) and the named resources stand. [M-lod] reads the
pristine `*.anchor_bak.*` dump only: LEMD 79,572 placed components / 1,656 placements.

### F.1 LAW BY LAW — what is consumed of an object, and at what precision

| consumer | what it consumes | precision | per component? |
|---|---|---|---|
| §16g `footprint_unit` (13bo) | the body's PLAN OUTLINE (rings; box where none) — "do these two cover the same ground" | `footprint_touch_m` = 0.5 m; rings ≤ 16 vertices, simplified OUTWARD by 0.05 m | **no** — only the UNION outline of a unit matters; a ring inside another ring of the same unit adds nothing |
| `planar/cluster` → cluster pad (14x) | the union outline of touching bodies whose GROUND FLOORS agree within `floor_split_m` 0.5 | the arrangement snaps at 0.5 m (17k M4) | **no** — union again; but it reads each ground-contact body's `base_y` for the floor split |
| placement seat (`placement_*`, `rebake_plan`) | FEET: ≤ 4 lowest vertices per ground part, the median of `surface − y` over them; carriers for footless bodies | metres in plan, centimetres in y | per ground PART today; the unit's seat needs the unit's ground feet, not every chair's |
| `planar/group` / `foot_rows` / `pad_relief` | feet of an ELIGIBLE bare-ground body | per foot | a body standing on a pad or pavement states NO rows already ("pavement is senior", 09af-1) |
| ε-contact partition | every part's triangles vs every neighbour's, 3-D, 0.25 m | millimetre welds | **yes — and its only products are (i) bodies and (ii) structures/abutments; inside one unit both are moot** |
| basins (witness + COVER), door wells (sill, `above`), tunnels, wall corridors, sunken roads, shells, thin plates, skirt | BELOW-grade floors and walls; AT-grade plates (sills, hard / draped); and the above-grade footprint as **roof COVER**, read as a UNION intersected with a ring or window | clip at a DEM plane; union at GEOS precision | below / at grade: **yes**; above grade: **union only** |
| deck signature / elevated deck / line object | a plate on piers; a long thin thing | per resource | per resource |
| v1 inset pass (`dsf_reader._compute_dsf_object_buildings`) | building footprints from its own parse | metres | untouched by everything here |

**CONCLUSION — what is NEVER consumed.** For a component that is
 * **(a) contained in plan inside a host's closed outline**: its ring (the host's covers
   it — the unit outline and the cluster-pad outline are the SAME polygon with or
   without it), its ε-contacts (unit membership follows from containment), its group,
   and its feet as an INDEPENDENT seat. If it is also wholly above the contact band and
   carries no hard / draped triangle, its structure reads too: it can only ever add
   cover under a roof that already covers it. **STILL CONSUMED**: a contained component
   AT or BELOW grade (a sill plate inside a hangar, a pit, a basement wall, a hard
   surface) — the door-well / basin / tunnel laws read exactly those, so they stay
   witnesses. They skip rings / contact / groups like the rest.
 * **(b) wholly above grade and NOT contained** (roof plant, a sign on a façade, a canopy
   edge): no feet today already (`elevated_base_m`); still consumed as COVER (union) and
   as footprint (a canopy extends its unit's outline — 11i). Its ε-contacts are consumed
   only to decide WHICH body carries it. So (b) alone is not an admission class; it is a
   precision class (F.3, row 19).
 * **(c) same resource vs separate placement**: inside one `.obj` the contents ride
   rigidly for free PROVIDED the file is not split between host and contents — which
   is what contact-body decomposition + §9's split can do today and what F.2 forbids.
   A separate placement inside the host must be given the host unit's motion — §16g
   does that today whenever its footprint is in the plan at all.

### F.2 THE RIGID-UNIT RULE — CONTENTS

**The rule.** A freestanding structure is ONE unit. Its OUTER ground outline and its
at-/below-grade parts are derived once. Every other component whose plan extent lies
inside that outline is CONTENTS: it takes the unit's motion rigidly, is never cut from
it, never decomposed into bodies, never states rows, never enters the contact graph,
the groups or the clusters, and founds no seat.

**The host outline — and why containment is NOT the refuted discriminator, measured.**
Box proximity (row 13) failed because flat or sheet-like neighbours' BOXES cover
everything. Plain plan containment fails THE SAME WAY, and worse: with any at-grade
solid ≥ 10 m as a host, `HillBush.obj` reads **83.9 % contained** and
`Tree1Foliage.obj` **100.0 % contained** [M-lod] — because these packs ship their
TERRAIN as objects: the hosts are `Objects/Flora/hill.obj` (34,565 bushes on it),
`TFFG/Objects/Ground/fixed_platform.obj` (106,827 leaf clumps) and
`TFFG/Objects/Ground/Cliff.obj`. A bush standing on a hill object is not the contents
of a building. The discriminator that works is on the HOST, not on the relation: a
host is a **closed volume** — the sum of its triangles' plan areas is at least
`[contents] host_closure_min` (**1.6**) × the area of its plan projection (a box
projects its roof AND its floor: ≈ 2; a terrain sheet, a slab, a platform: ≈ 1) — at
least `host_diag_min_m` 10 m across, `host_height_min_m` 2.5 m tall, and not
line-shaped. With that test [M-lod]: HillBush **0.0 %**, Tree1Foliage **0.0 %**,
ParkingBushes 0.0 %, BaggageCarts 0.0 %, the people 0.0 % — and what reads contained at
TNCM is palms in the OceanPoint hotel's courtyard wing, the Sonesta bar, the terminal
glass. 133 `Autogen1.obj` sheets, the docks pattern and the causeway bridge deck are
refused as hosts.

**At-grade hosts only vs roof-inclusive hosts, measured.** The owner's words are "the
footprint on the ground". At COMPONENT level that finds almost nothing at LEMD, because
a terminal is an assembly — no single at-grade component is the building:

| hosts | TNCM contained | TFFG | LEMD | OTHH |
|---|---|---|---|---|
| closed volumes AT GRADE only | 7.8 % comps / 6.5 % tris | 2.5 % / 6.6 % | **0.5 % / 0.2 %** | not run |
| closed volumes at ANY height (the building's plan outline incl. what its roofs cover) | 10.5 % / 8.7 % | 3.4 % / 7.1 % | **50.0 % / 44.4 %** | **23.1 % / 21.4 %** (of ≈ 772 k placed components) |
| — of NON-scatter components (what is left after row 5) | **27.0 %** of 57,056 | **26.5 %** of 23,070 | 40.3 % of 53,337 | — |
| — whole PLACEMENTS contained (decidable before `solid_components`) | 31 placements / 0.2 % | 2 / 0.0 % | **282 placements / 21.0 % of comps** | — |
| wholly above grade, NOT contained (class (b)) | 65.6 % (polluted: 72 % of HillBush reads "above grade" because it is authored ON the hill object) | 4.1 % | 20.3 % | 55.0 % |

So the production host outline is the any-height one: **the plan outline of the
structure = the union of its closed-volume components' projections**, holes kept.

**Relation to what exists.**
 * **§16g / 13bo — UNCHANGED, and it is the motion law.** Contents are in the host's
   unit because their footprint overlaps it; that is 13bo verbatim. What this rule adds
   is only that the work BEFORE §16g is not done for them. Deterministic host for
   motion: none needs choosing — §16g chains transitively, so a component overlapping
   two hosts makes all three one unit today and still does. For NAMING (the report and
   the DSF record): the host placement whose outline covers the component's centre;
   ties → the larger outline area, then the lower placement id.
 * **§48 interiors — SUBSUMED in its predicate, NOT in its safeguards.** §48's U5 is
   "roofed ≥ 95 % by the union of OTHER placements". Containment in the closed-volume
   outline IS that cover test, read in plan (the measured LEMD prize agrees: U5 34.7 %
   of triangles per placement-level; this rule 44.4 % at component level, 21.0 % of
   components at whole-placement level). This rule is WIDER in two ways the owner's
   sentence asks for: it works per COMPONENT (the chairs inside the same `.obj` as the
   terminal — TNCM 9.5 % of components are same-placement contents, which U5's
   same-resource exclusion can never reach), and it removes rings / contact / groups,
   not only structure reads. What §48 still UNIQUELY supplies, and this rule ADOPTS
   unchanged rather than re-deriving: no hard / hard-deck / draped triangle; `y_min >
   −2.5` (below-grade facilities are never contents); the fixpoint that stops two
   mutually-roofing shells from both vanishing (restore in descending footprint,
   named); the false-positive register (coincident duplicate placements, hangar door
   leaves, material-sliced shells, vehicles under a roof, a tower cab under its decal);
   the MSL carry twin. **ONE predicate module, one carried flag**: `v2interiors`
   (checkpointed, unmerged) is RESUMED as the lane that lands this (S6), not run beside
   it — two "never read" classes threaded through `basin_witness` would be the
   census-wrapper defect in geometry.
 * **Row 8 (convex-hull proxy rings) stays NOT WORTH IT** — contents get NO ring at
   all, which is cheaper than a hull and exact (the union is unchanged), and hosts keep
   the true outline 14j ruled.
 * **Row 5 scatter** is decided FIRST (it is a per-resource, frame-independent fact);
   contents is decided second, per placed component, against the hosts. A scatter piece
   inside a host is contents (it rides with the building — 13bo); one outside is set
   down on its own (18q Q2).

### F.3 THE PRIZE, and how early it is knowable

 * **How early.** Host test and containment need components (closure is a per-component
   reading), so `solid_components` still runs — and that is fine: parse + components is
   16.7 s of TNCM's 301.6 s [F]; **the cost is everything AFTER decomposition**
   (`placed_parts` rings 57 s, narrow pass 169 s, clips, groups). The one thing
   decidable BEFORE decomposition is the whole-placement case — a placement whose solid
   vertex bbox lies inside the host union skips `solid_components` too: LEMD 282
   placements / 21.0 % of components, TNCM / TFFG ≈ 0. Order in `partition_pack`:
   (1) per-resource readings (scatter, closure per component — frame-independent,
   cached); (2) place HOST components only and union their projections per placement
   (hosts are 0.2–1.1 % of components but 8.7–11.5 % of triangles; ONE
   `coverage`-style union per placement through `frame_entry.union`); (3) bulk
   containment of every other component's placed plan box (`STRtree.query(...,
   predicate="within")`, one call); (4) only the survivors become full `PlacedPart`s.
   Contents become box-only parts: `rings=()`, `feet` empty, `contents=True`, excluded
   from weld / broad / narrow / abutment passes.
 * **Estimated gain ON TOP of rows 1–5** (computed from the measured shares; partition
   cost taken ∝ full parts): TNCM parts ≈ 20 k → ≈ 14.6 k, partition est. 45–60 →
   **35–45 s**; TFFG ≈ 3 k → ≈ 2.2 k, **≈ −3 s**; **LEMD −40 % of its full parts →
   the object-layer share of its 378 s structures stage est. −25…−35 %** (NEEDS
   MEASUREMENT: that stage's split is not in hand); **OTHH −23 % of parts on top of
   §48's own triangle removal**; RSS: proportional to parts dropped — LEMD est.
   −1 GB, OTHH unmeasured. **This is LEMD's and OTHH's lever, not the islands'** —
   their cost is scatter (row 5) standing on terrain objects.

### F.4 RISKS, ruled one by one

| risk | ruling |
|---|---|
| contents that include a genuine GROUND STRUCTURE under the outline (a pit, a baggage tunnel mouth, a basement) | at-/below-grade, hard and draped components are never structure-skipped (F.1 (a)); `y_min ≤ −2.5` is never contents at all (§48) |
| **a hangar with open doors whose interior floor IS graded apron — door wells** | the sill plate and floor witnesses are at-grade / hard → still read; the closed-volume outline of a hangar covers its interior, so equipment parked inside rides with the hangar — correct. §48's door-LEAF false positive (236 of 506 OTHH admits) is an at-grade witness inside the cover: it stays a witness, and as contents it rides with its hangar — also correct |
| apron equipment inside the building's BBOX but outside its ring | the test is against the outline polygon, never the box; the census' 5-point box test is replaced in production by `within` on the placed plan box, so a cart half under a canopy edge is NOT contents |
| courtyards / holes | holes are kept in the host outline; a palm in a courtyard is free-standing scatter and is set down on its own |
| multi-host overlap | predicate = union of hosts; motion = §16g's transitive unit (unchanged) |
| a jetway foot inside / at the terminal outline | F.5 |
| host and contents are SEPARATE placements — same motion? | §16g already gives one seat per unit; contents add no feet to the unit's median, so **the unit's seat is its HOSTS' and its free ground members' feet only**. DECLARED MOVEMENT: units whose median included interior feet move by the difference; bounded by the pad's own flatness under the building; S6 reports the per-unit delta distribution on LEMD before wiring |
| multi-anchor resources that are contents (the same chair file at 40 anchors) | today DROPPED from the plan at load (I-4: one file cannot carry per-placement offsets) → they do not ride. Contents need no per-vertex bake — they need the unit's motion on their DSF ROW (§16g (5) `msl_seat_rows` precedent). Folded into F.5's row mechanism; until then they behave as today |
| byte identity of the PATCH BODY | expected IDENTICAL: unit and cluster-pad outlines are unions unchanged by removing contained rings; contained bodies stand on the host's pad and state no foot rows today (09af-1); cover unions are unchanged under a roof. PROVEN, not asserted: S6's dry pairs on LEMD / HECA / VHHH (`structures.json` + cluster-pad outlines + foot-row sources byte-identical). DSF rows move (declared above) |
| terrain objects (hill, platform, cliff) | never hosts (closure test). What the pipeline should DO with a pack's terrain object is outside this spec — owner Q4 |

### F.5 JETWAYS RIDE WITH THEIR TERMINAL (owner ruling above) — read with F.9, which generalises it

**What happens today, measured on the corpus dumps [M-lod]:**

| pack | jetways as placed | in the rebake plan today? |
|---|---|---|
| OTHH | 14 pack OBJ types, EVERY one placed > 1× (`Jetway_Type10` ×30, `Type7` ×27, `Type5` ×22 …) | **NO — multi-anchor drop** (`pack_partition` `drop_now`, I-4): X-Plane drapes each at its own anchor, on the apron; the terminal moves, the jetway does not |
| LEMD | 121 `.agp` placements (`LEBL_jetway.agp` ×81, `LEMD_Jetway_alt.agp` ×40), SAM | **NO — an `.agp` has no OBJ8 geometry**; never a member of anything |
| HECA | 48 `.agp` jetways + 3 `EGCC_Jetway_metal_03.obj` | `.agp`: no. The three OBJ ones: yes (and 17q found them misread as a channel witness) |
| TNCM | `Jetway1.obj`, `Jetway2.obj` ×1 each, `AutoJetWay.obj` ×4 | single-anchor ones: yes, as ordinary bodies; §16g units them with the terminal IF their ring comes within 0.5 m of it |
| library autogates (`lib/airport/Ramp_Equipment/…`) | none on these four dumps | **NO — stock resources are skipped** ("shared, never baked") |

So the ruling is met today only for a single-placement OBJ jetway whose outline touches
its terminal; on the three big airports it is NOT met for any jetway.

**The rule.**
 1. **Membership without geometry.** ANY placement — OBJ, `.agp`, `lib/…`, multi-anchor
    — whose DSF ANCHOR lies within `footprint_touch_m` (0.5 m) of a unit's host outline,
    or inside it, is a RIDER of that unit. This is 13bo stated on the anchor for
    placements whose geometry the plan never holds. It is mechanical and name-free: a
    SAM / autogate jetway's anchor is its rotunda at the terminal wall; a wall-mounted
    docking display rides too (correct); an apron marshaller 40 m out does not.
    Deterministic host: the unit whose outline is nearest the anchor; ties → larger
    outline area, then lower placement id.
 2. *(WITHDRAWN — owner simplification, F.9: no object-type recognition of any kind. A
    parsed body joins by R1's footprint intersection like everything else.)*
 3. **Motion by ROW, not by bake.** A rider takes its unit's vertical motion on its own
    DSF row (the §16g (5) `msl_seat_rows` mechanism), so multi-anchor, `.agp` and
    `lib/` placements can all ride without touching a shared file. NEEDS CHECK by S7
    before anything else: that X-Plane 12 honours an MSL / AGL row for an `.agp` and
    that SAM's animation anchors follow it.
 4. **The pad.** The cluster pad's outline is extended by the rider's GROUND footprint
    (bogie, rotunda column — for an unparsed rider: a disc of `footprint_touch_m` at
    the anchor), never by its elevated tunnel. **But §16g (10) (5) / 14ah / 14ax stand:
    a derived pad never takes AIRSIDE ground** — the extension is clipped by the apron
    faces like every pad. Where the feet stand on apron (the normal case), "the same
    level" therefore cannot be bought by bending the apron to the pad (airside is
    king). The pad already MEETS the apron at the terminal's airside edge (§20: the pad
    follows its apron; F.9 R4) — what is left open is only the strip of apron under the
    jetways themselves, which is owner Q3.

### F.9 THE GENERAL RULE (owner simplification, verbatim)

*"Do we need to recognize a jetway? Anything that intersects the building (and doesn't
extend of hundreds of meters like a railway) is just treated as part of that building
and moves with it. We only cut apart objects that have clear measurable space all the
way around them. Aprons and terminals must always meeting smoothly, and the flat
terminal area should include the jetways."*

**Every clause of this is already law — §16g (13bo) — and the code that costs the
minutes is the machinery §16g made redundant.** Rule by rule:

| | the owner's clause | what exists | value | what changes |
|---|---|---|---|---|
| **R1** | anything that intersects the building is part of it and moves with it; transitive | §16g (1) `footprint_unit.plan_units`: two bodies whose PLAN footprints overlap or come within `[placement] footprint_touch_m` are one unit, chained transitively; one seat per unit | **0.5 m**, plan | nothing in the law. TWO GAPS in its population: (i) a placement the plan never holds — multi-anchor, `.agp`, `lib/` — cannot intersect anything (F.5: every jetway at OTHH, LEMD and HECA's `.agp` ones) → F.5's anchor rider; (ii) `planar/group.derive` is a SECOND, narrower derivation of "what belongs together", from ε-abutments: at TNCM it reports `abutment_pairs 33,909`, **`refused_building 28,013`** (a pair of non-deck bodies across placements is refused a GROUP — 10i "buildings never group with buildings"), `cross_groups 19` (deck juniors joined to a senior), `long_span 0`. Those refusals are about who shares a PAD TARGET, not who moves together, so they do not contradict R1 — but under R1 + R4 the group's membership should be READ from the unit / cluster, not re-derived (the module's own "ONE DERIVATION, MANY READERS"). Consolidation = row 21 |
| **R2** | …unless it extends hundreds of metres like a railway | §16g (3) + (6) "THE ONLY CUT": a body whose footprint span reaches `connector_span_m` AND whose ends' ground differs by `[cockpit] visual_m` AND which topologically LINKS (two components of its unit, or one end to open ground) is a CONNECTOR — cut at line stations, never holding its unit rigid. Anything else is a member however long (13cn, the SPJC viaduct). Beside it: `[placement] group_span_max_m` 150 (group release, 11i), `UNIT_CLUSTER_SPAN_MAX_M` 300 (a rigid cluster is building-sized), the 10bb line class (fences, kerbs) | **200 m** | **keep 200 m; no new number.** Against real data: LEMD's kerbside canopies span 30–90 m (11i), a jetway with its fixed bridge ≈ 60–120 m, LEMD's T2 block is whole at 300 m and is a BUILDING (it is never asked this question — R2 is asked of one BODY, not of a unit), HECA's elevated rail and LEMD's 5,157 m perimeter fence run kilometres. 200 m sits above every attachment and below every railway; and the span test alone never cuts — the body must also be the link, which is what keeps a 250 m pier finger a member |
| **R3** | we only cut apart objects that have clear measurable space all the way round | the unit partition IS that: two things are separate units iff nothing chains them within 0.5 m in plan | **0.5 m = `footprint_touch_m`** — NOT the ε-contact 0.25 m (3-D surface-to-surface) and not the abutment test | **the consequence is this spec's subject.** The ε-contact graph (`contact.partition`: TNCM 231 s, TFFG 459 s, OTHH the plan stage) exists to find what is rigidly ONE in 3-D. Since 13bo the only lawful cut is R2's, so inside a unit nothing consumes a 3-D contact edge except (a) splitting ONE FILE that holds several free-standing structures into bodies (LEMD authors hundreds per file), (b) choosing a footless body's carrier (11ai–11am), (c) the cluster floor split (`floor_split_m`). (a) is a PLAN question — clear space all the way round — and is answered by footprint blobs, not by 2.26 M vertex-to-triangle tests |
| **R4** | the flat terminal area includes the jetways; aprons and terminals always meet smoothly | §16g (10) "THE PAD IS THE CLUSTER" (14x): one pad per cluster = the union outline of touching WALLED bodies (`chain_min_height_m` 2.5) whose ground floors agree within `floor_split_m` 0.5 — a parsed jetway touching its terminal is in the cluster and its outline is in the pad TODAY. §20: the pad FOLLOWS its apron (`frontage_level`: the senior fronting pavement's edge mean is the pad's level; the pad may tilt ≤ `pad_slope_max` 1 %); apron-to-pad joints at LEMD `building4` measure **0.00 m since 11af**. 14ah / 14ax: the pad is CLIPPED out of every airside face | 1 % tilt; 0.5 m floors | "meet smoothly" is MET by standing law — no owner question. "Include the jetways" is met for the part of a jetway over non-airside ground and is CLIPPED where its wheels stand on apron: that one conflict is owner Q3, with numbers. Unparsed riders (F.5) add a `footprint_touch_m` disc at the anchor to the cluster outline before the clip |

**Scatter stays consistent (18q):** a bush whose footprint intersects a building is R1 —
it rides (13bo); a free-standing piece has clear space all round — R3 — and is set down
on its own; and it never shapes the terrain (Q1), so it is never in a cluster (R4).

**R1–R4 AND THE LEVEL OF DETAIL — the end state.** Once units are formed by footprint
intersection, the only per-object products any law consumes are: **(1) the unit's outer
PLAN outline** (membership, R1 / R3), **(2) its GROUND outline and ground floors** (the
pad, R4), **(3) its ground feet** (one seat per unit), **(4) its at-/below-grade parts**
(basins, door wells, tunnels, wall corridors, sills, hard surfaces), **(5) its
above-grade cover UNION** (one polygon per unit). Nothing else — no ring per component,
no 3-D contact edge, no group per body.

 * **How early.** (1), (2) and (5) are unions of projected TRIANGLES and need no
   components at all: per RESOURCE, in OBJECT space, once per pack (row 6's store), the
   connected BLOBS of the solid plan projection are "the free-standing structures in
   this file" — R3 read literally. Per placement they are rotated through
   `frame_entry.enter` (§51) and chained across placements by ONE bulk
   `STRtree` `dwithin` 0.5 m query. `solid_components` then runs only for what (3) and
   (4) need: the at-/below-grade band of each blob.
 * **The measured prize under this rule [M-lod]** — the population the unit law works
   on, against the population the contact partition works on today:

   | | placed solid components (today's parts population) | at-grade footprint blobs (1 m raster, 8-connected, whole window) | ratio |
   |---|---|---|---|
   | TNCM | 153,888 | 6,014–6,706 | **4 %** |
   | TFFG | 182,584 | 3,493–4,027 | **2 %** |
   | LEMD | 79,572 | 9,244 | 12 % |

   and inside the blobs, F.2's contents shares (LEMD 50.0 %, OTHH 23.1 %, non-scatter
   TNCM 27.0 %) are what never needs a second look. Wall: the partition's cost is
   super-linear in parts (pairs), so a 10–25× smaller population takes the object
   layer to seconds; stated as an EXPECTATION — it is a redesign of `contact.partition`
   and its consumers (`placement_plan`, `placement_family`, `rebake_plan`, the carrier
   law 11ai–11am, `planar/cluster`'s floor split, `planar/group`), and is NOT sliceable
   from a census. Row 21.

### F.6 VERDICT ROWS (extend §A's table)

| # | option | TNCM | TFFG | LEMD / OTHH | cost | §46 | verdict |
|---|---|---|---|---|---|---|---|
| **18** | **CONTENTS — the rigid-unit rule** (F.2): components contained in a closed-volume host outline become box-only riders; above-band non-hard ones leave the structure reads | partition est. −10…−15 s after row 5 | ≈ −3 s | **LEMD 50.0 % of components / 44.4 % of triangles; OTHH 23.1 % / 21.4 %; LEMD whole placements 21.0 % skip decomposition too** | 1 module (shared with §48) + the `placed_parts` reorder; consumer census = §B.6's rows 1, 4–10 with "contents" read as "scatter" | patch body expected byte-identical (dry-pair proof); DSF rows move (declared) | **DO NEXT — S6 `packcontents`**, which RESUMES and absorbs `v2interiors` (§48) |
| **19** | coarser precision for class (b) (above-grade, not contained): hull ring + no intra-unit narrow pass | large at TNCM / OTHH on paper (65.6 % / 55.0 %) | — | — | the carrier choice (11ai / 16a) reads exactly these contacts | high — carriers decide where roofs sit (the floating-roof defect class, 11ah–11am) | **NEEDS MEASUREMENT, not now**: the "above grade" reading is polluted by terrain-object authoring; re-measure after rows 5 + 18 land |
| **20** | RIDERS WITHOUT GEOMETRY (F.5 / F.9 R1): anchor-based unit membership + row motion for unparsed (`.agp`), multi-anchor and stock placements — jetways are its first customer, no type is recognised | — | — | correctness, not time | new placement-law section in `object-placement-spec.md`; `dsf_write`, `footprint_unit` | none on the patch body unless Q3 extends pads | **DO NEXT — S7 `unitriders`** (Q3 decides only the pad strip, not the membership); its first step is the X-Plane `.agp`-row check |
| **21** | **UNITS BY FOOTPRINT, not by 3-D contact** (F.9 end state): object-space plan blobs per resource → placed outlines → one bulk touch query; ε-contact only where a carrier or a floor split needs it; `planar/group` reads units instead of re-deriving from abutments | population 153,888 → ≈ 6,400 (4 %) | 182,584 → ≈ 3,800 (2 %) | LEMD 12 % | a redesign of `contact.partition` + six consumers; needs its own consumer census and spec | every DSF row can move; patch body via cluster pads (outlines should be equal — to prove) | **DO NEXT, AS ITS OWN SPEC** after S5b + S6 land and are profiled: they are the same idea applied to two classes, and their measured residue says how much of the contact graph is still paid for |

**Slices.** S6 `packcontents` — ONE implementer, AFTER S5b (same edit sites:
`contact.placed_parts`, `pack_partition._build_member`, `basin_witness`), resuming the
`v2interiors` checkpoint. Files: NEW `airport/contents.py` (host closure reading, host
outline per placement, bulk containment; §48's safeguards live here), `[contents]` law
keys + schema; EDIT as S5b's list + `airport/footprint_unit.py` (seat reads hosts' and
free members' feet) + `partition_cache.py` (module list, version). Step 0 = a DRY
census like S5a (`pack_stage_profile.py --contents-census`: per airport the contained
share by the PRODUCTION test, the named false positives from §48's register, the
per-unit seat delta distribution) reviewed by Fable before wiring. Twins: closure test
(box ≈ 2, sheet ≈ 1, a hill object refused); containment vs courtyard hole, vs bbox-
only overlap, vs half-under-canopy; an at-grade sill inside a hangar stays a door-well
witness; a contained scatter piece rides, a free one seats alone; mutually-roofing
shells (§48 fixpoint); duplicate coincident placements; cache version refusal. Closing:
LEMD / HECA / VHHH dry pairs byte-identical on the patch-feeding products, then ONE
`build_airport.py LEMD` (the airport that carries this row's prize). Bars: LEMD full
parts −40 % ± 5 pp, structures-stage wall and RSS named; attempt cap 2; heartbeat.
S7 `unitriders` — separate lane, placement law (F.9).

### F.7 OWNER QUESTIONS

**Q3.** Two of your sentences meet at the jetway wheels. Today's law (14ah, "airside is
king") says a building pad NEVER takes apron ground, and the pad already FOLLOWS the
apron where they meet (§20: apron-to-pad joints measure 0.00 m at LEMD since 11af) — so
"aprons and terminals meet smoothly" holds. But the jetway's wheels stand 30–60 m OUT
on the apron, and "the flat terminal area should include the jetways" would make that
strip of apron flat at the terminal's level. Where the apron falls away from or along
the terminal the two disagree: at LEMD T4 a member of the terminal's unit stands up to
**1.73 m** off the graded apron under its own feet today (17x; 0.43 m with the shelved
fix B), and HECA's T3 apron falls **5.4 m** across the district. Which wins under the
jetways? (a) the apron keeps its own grade (airside is king); the jetway rides rigidly
with the terminal and its wheels may stand off the apron by the apron's fall over the
jetway's length — reported per gate; (b) the apron strip under the jetways is asked to
be LEVEL with the terminal as an AIRSIDE law of its own (a real stand is near-level) —
the apron is still solved airside-first, nothing groundside pulls it. *Recommended:
(a) now, with the per-gate number reported so you can judge (b) from a sim read.*

**Q4.** TNCM and TFFG ship parts of their TERRAIN as objects — `Flora/hill.obj`,
`TFFG/Ground/fixed_platform.obj` (the airport platform itself), `Ground/Cliff.obj` —
and their trees and bushes are authored standing on those objects, not on the mesh. We
now set each bush down on OUR ground (18q). What should happen to the terrain objects
themselves: leave them exactly as authored (they may poke through or float over our
mesh), or treat them as ground evidence? *No recommendation — this is new, and it
decides whether a bush set down on our ground ends up buried inside the pack's hill.*

### F.8 NOT DONE (addendum)

 * The census is a 1 m raster with a 5-point box test; the production predicate is
   exact `within` — S6 step 0 re-measures. OTHH was run with any-height hosts only.
 * No wall or RSS was measured for rows 18–20; every gain is computed from shares.
 * `.agp` / SAM behaviour under a rewritten row is unverified (S7 step 0).
 * No pad-vs-apron joint was re-measured here; R4's "0.00 since 11af" and Q3's 1.73 / 0.43 / 5.4 m
   are the standing record (11af, 17x), not new captures.
 * Row 21 has no consumer census yet; it is named as an end state, not designed.
