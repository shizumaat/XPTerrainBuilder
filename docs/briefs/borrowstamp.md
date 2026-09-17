# Brief pack — lane `borrowstamp`

Base: main `2fb0799f` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

the freshness gate watches the §44 borrowed Global apt.dat

## The brief

## The brief — lane borrowstamp (follow-up chip of RULINGS 2026-09-17a)

RESIDUAL (stated in `Ortho4XP/src/auto_patch/engine_v2.py` `_stamp_header`
docstring, "NOT WATCHED HERE"): under a §44 borrow v2 reads a SECOND
apt.dat (Global Airports). `Ortho4XP/src/auto_patch_v2/pipeline/build.py`
~:937-941 writes `o4_apt_dat_borrowed` into the patch header, but the
freshness gate (`layout.read_patch_source` :4400 →
`driver._auto_patch_is_current` :230) does not watch it — a Global
Airports update in place leaves a borrowed patch reading current.

DO
1. `pipeline/build.py`: write `o4_apt_dat_borrowed_mtime` (same
   `f"{os.path.getmtime(p):.6f}"` rendering as `o4_apt_dat_mtime`) beside
   `o4_apt_dat_borrowed`, only when the borrowed path is non-empty and
   stat()s; an OSError omits the key (as `_stamp_header` does).
2. `layout.read_patch_source`: return both (`apt_dat_borrowed: str` —
   "" when absent/empty — and `apt_dat_borrowed_mtime: float | None`).
   NB `_PATCH_SOURCE_APT_RE` is `o4_apt_dat='…'` and must keep NOT
   matching `o4_apt_dat_borrowed='…'`; check how v2's emitter escapes the
   header value (raw vs percent-encoded — `header_extra` percent-encodes
   only `o4_apt_dat`) and read it back in the encoding it is written in.
3. `driver._auto_patch_is_current`: when the patch carries a non-empty
   `o4_apt_dat_borrowed`, stat THAT file: missing file, missing mtime
   key, or mtime differing (exact match, the `1e-6` rule of input 1) ⇒
   not current. STAT ONLY — do NOT re-decide the borrow in the gate (no
   Global-block parse, no coverage union; the gate is stat()s by
   construction). Log the rebuild reason the way the inputs 2-7 branch does.
4. NO MASS INVALIDATION: a patch without `o4_apt_dat_borrowed_mtime`
   stays current UNLESS it carries a non-empty `o4_apt_dat_borrowed`
   (those rebuild once and acquire the key). Do not add the new keys to
   `provenance.FRESHNESS_KEYS` / bump `FRESHNESS_SCHEMA_VERSION` — that
   is the all-or-nothing block and would rebuild every patch.
5. Update the `_stamp_header` "NOT WATCHED HERE" docstring and the gate
   docstring's input list to say what is now watched (the borrowed file's
   mtime) and what still is not (the borrow DECISION: a Global update that
   flips borrow ↔ no-borrow for a patch that did not borrow).
6. Twin in `Ortho4XP/tests/test_auto_patch_freshness.py`: a borrowed patch
   goes stale when the fake Global Airports apt.dat is touched; a
   non-borrowed patch does not; a borrowed patch WITHOUT the mtime key is
   not current; a legacy patch with neither key stays current. Red on
   base, green after — show it.

PROCESS
- Merge main first. Own tree: `tools/harness/lane_worktree.sh up borrowstamp <base>`
  from `Ortho4XP/` (fresh branch name — never the session's branch).
- `Ortho4XP/venv/bin/python tools/blast.py <file>` on EACH touched file
  before editing; run the tests it names.
- Run the named tests, then the standing suite ONCE; report the pass
  count and every `FAILED` line VERBATIM (never `tail -1`).
- NO airport build, NO sweep, no `--refresh-data`.
- Do NOT touch RULINGS.md — the spawner appends the entry and owns the merge.
- Commit on the lane branch; report the sha, the diff stat, red/green twin
  evidence, the suite line + FAILED lines, and anything the brief got wrong.

## Bars

- Twin red on base, green after: borrowed patch stale on a touched Global apt.dat; non-borrowed patch unaffected.
- A patch with neither new key and no borrow reads current exactly as before (no mass invalidation); `FRESHNESS_KEYS` and `FRESHNESS_SCHEMA_VERSION` unchanged.
- The gate adds stat()s only — no apt.dat parse, no borrow re-decision.
- Standing suite: 0 FAILED (or every FAILED line shown to be red on base too).

## Files

Yours: `Ortho4XP/src/auto_patch_v2/pipeline/build.py`, `Ortho4XP/src/auto_patch/layout.py`, `Ortho4XP/src/auto_patch/driver.py`, `Ortho4XP/src/auto_patch/engine_v2.py`, `Ortho4XP/tests/test_auto_patch_freshness.py`

## Spec (design-surface) §44

## §44 A PACK WITHOUT PAVEMENT BORROWS THE GLOBAL AIRPORT'S (owner 2026-09-15; RULINGS 2026-09-15m; Fable 2026-09-15) — lane `v2pavborrow`

**THE DEFECT (LGAV, the owner's tile build 2026-09-14 23:14, engine 1.50.1785).**
The FlyTampa LGAV pack authored NO taxiway or apron pavement: its apt.dat block
carries two row-110 polygons, both runway-length strips (369,545 m²), and the
airport's pavement is IMAGERY — 41 draped `Overlays_orthos/Ground_*.obj` pages
declared `ATTR_layer_group_draped markings -2`, which §42's gate rightly refuses
(`report.load.object_pavements.refused["layer group markings"] = 21`). The
engine's pack precedence (`airport/apt_dat.find_apt_dat`, v1's rule) is "a
Custom Scenery pack carrying the airport WITH row-110 pavement wins", and two
polygons are row-110 pavement — so LGAV was graded with `faces_by_role =
{runway 4, graded_strip 4, junction 15, tunnel_ramp 2, retaining_wall 6,
door_ramp 1, tunnel_trench 5}`: ZERO taxiways, ZERO aprons, every apron object
on raw 30 m DEM. The Global Airports block for LGAV carries 63 pavement polygons
(2,409,902 m² as a union) and one row-130 boundary; the custom block's pavement
covers 1.3 % of it.

**THE LAW.**

(1) **THE PACK IS STILL THE PACK.** The selected pack is the first Custom
Scenery pack (sorted, `Global Airports` excluded) whose apt.dat carries the
ICAO — that is what X-Plane renders: its runways, lights, lines, startups,
metadata, and its DSF objects (the object stage, the pads, the seats). The old
tail of the precedence rule — "a pack without pavement is the fallback of last
resort", under which a pavement-less custom pack LOST the selection to Global
Airports and its objects were never read — is DELETED; §44 (2) does that work.
Among several custom packs the precedence stays as today (the first with row-110
pavement, else the first).

(2) **THE BORROW TRIGGER — COVERAGE (owner 15m: "Coverage < 25 %").** With the
selected custom block parsed, the Global Airports block for the same ICAO is
parsed too (XP12 `Global Scenery/Global Airports`, then XP11 `Custom
Scenery/Global Airports`, then the stock default; the first that carries the
ICAO). `coverage = area(custom_pavement_union ∩ global_pavement_union) /
area(global_pavement_union)`, in the airport frame. When `coverage <
[load] pavement_borrow_coverage_max` (0.25) the pack BORROWS. A custom block
with no row-110 rows has coverage 0 and borrows; no Global block → nothing
borrowed and the custom stands; the key at 0 never borrows, at 1 always does
when a Global block exists. The number is law (`law/structures.toml [load]`,
`LoadLaw.pavement_borrow_coverage_max`, validated 0 ≤ x ≤ 1).

(3) **WHAT IS BORROWED (owner 15m: "Pavement + boundary").** The Global block's
row-110 pavement polygons, parsed by the same parser, APPENDED to the custom
block's own (borrowing adds, never removes — LGAV's two runway strips are real
pavement and §40 classifies them as the runway's; overlaps between polygons are
the planar partition's business, as they already are among Global's own 63);
and the Global block's row-130 boundary ONLY when the custom block has none.
NOT borrowed: runways, lines (row 120), the taxi network (1201/1202 — the
pack's own, authored on its imagery, stays: 226 nodes / 290 edges at LGAV),
startups, metadata, the DSF. Every borrowed record says so (`Pavement.source
= "global_airports"` or the model's equivalent — the lane names it).

(4) **IDENTITY.** `SceneryPack` gains `borrowed_apt_dat_path: str` and
`borrowed_block_sha256: str` (both "" when nothing was borrowed); the signature
carries them; every cache keyed on the apt.dat path — the partition cache's key
list (`airport/partition_cache.py` ~:178) — includes the borrowed sha, so a
Global Airports update invalidates it; the patch header gains
`o4_apt_dat_borrowed`. `report.load.pavement_source = {"pack": …,
"borrowed_from": … | null, "coverage": 0.013, "custom_pavements": 2,
"borrowed_pavements": 63, "borrowed_boundary": true}` and ONE log line:
`[load] LGAV: the pack's apt.dat carries 2 pavement(s) covering 1.3 % of Global
Airports' 63 (< 25 %): pavement + boundary BORROWED from <path> (§44)`.

(5) **ONE DERIVATION SITE.** The borrow is decided in `airport/pack.py`
(`select_pack` → `PackSelection` gains the borrowed path / reason) and composed
in `airport/load.py` at the one place the block is parsed (:198–:211). No
consumer re-derives it.

### §44.1 CONSUMER CENSUS (owner RULINGS 2026-08-30l) — every reader of the affected geometry, ruled before any edit

| # | Consumer | Reads | Ruling |
|---|---|---|---|
| C1 | `airport/apt_dat.find_apt_dat` | pack precedence | EDIT: the "last resort" tail deleted (§44 (1)); returns the custom candidate first as today. |
| C2 | `airport/pack.select_pack` / `PackSelection` | the selection | EDIT: the single derivation site of the borrow (§44 (2), (5)); `PackSelection` gains `borrowed_apt_dat_path`, `borrow_reason`. |
| C3 | `airport/load.load_with_report` :198–:211, :241–:253 | parses the block; builds `pavements`, `boundaries` | EDIT: parse the borrowed block, append (§44 (3)); report + log (§44 (4)). |
| C4 | `model/airport.SceneryPack`; `airport/pack.signature` | the signature | EDIT: two fields (§44 (4)). |
| C5 | `airport/partition_cache` key list ~:178 | apt path in the key | EDIT: borrowed sha in the key. |
| C6 | `airport/pack_partition` :473 (`pack_root` from the apt path) | the pack root for object resolution | UNAFFECTED: the root is the CUSTOM pack's (objects resolve there) — that is §44 (1)'s point. |
| C7 | `pipeline/build.py` :875 patch header | `o4_apt_dat`, `o4_pack` | EDIT: `o4_apt_dat_borrowed` beside them. |
| C8 | `airport/load.LoadReport` | the load report | EDIT: `pavement_source`. |
| C9 | flat-site region (`FlatVerdict.region` = pavement ∪ boundary ⊕ margin), `_own_extent`, the DSF pavement admission gate (1 km of own pavement), §42 object pavements | pavement / boundary sets | UNAFFECTED in code; CHANGED BY DATA as intended — the region, extent and gate now stand on the borrowed pavement. |
| C10 | the DEM-inset stage's OWN apt.dat resolver (`auto_patch/osm_load.py` :624–:663 via v1 `apt_dat_reader.find_airport_apt_dat`, reached from `O4_Airport_Elevation_Insets`) — a SECOND resolver | the inset extent | MEASURE, not edit: after the borrow, does LGAV's inset still cover the layout 100 % (the log's "inset coverage", `report.load.dem_provenance`)? If the extent falls short of the borrowed pavement, REPORT it — the inset regenerates only under `--refresh-data dem`, the owner's act; the resolver unification belongs to stage B of the v1 retirement. |
| C11 | the mod-cache directory (`sel.name`), `airport/dsf.find_text_dump` | the custom pack's name | UNAFFECTED. |
| C12 | `O4_Airport_Index` (Global-only index), the Swift app | apt.dat paths | UNAFFECTED: no wire event changes; the log line is plain text. |
| C13 | the `.axes.json` sidecar / census keys | any key naming the apt.dat | The lane greps `apt_dat` in `emit/` and `tools/harness/`: a key that names the path carries the borrowed path beside it; otherwise UNAFFECTED (state which). |

### §44.2 Twins (`tests/auto_patch_v2/test_airport_load.py`, beside `test_pack_selection_prefers_custom_pack_with_pavement`)

(a) a fixture root with a custom pack carrying the ICAO with two runway-strip
polygons and a Global Airports file with N polygons + one boundary → borrow
fires; pavements = 2 + N; boundary borrowed; signature and partition key carry
the borrowed sha; `pavement_source.coverage` < 0.25. (b) coverage ≥ 0.25 →
nothing borrowed, byte-identical to today (the CYXY fixture stays green). (c)
no Global block → nothing borrowed, no exception. (d) the custom block has a
row-130 boundary → the boundary is NOT borrowed. (e) the key at 0 → never.
`tests/test_harness.py` stays green (no census key changes unless C13 says so).

### §44.3 Closing test

ONE LGAV patch build through `tools/harness/build_airport.py LGAV` (the inset
is warm from the owner's 2026-09-14 build; the DEM is COPERNICUSGLO30 30 m —
LGAV's production frame). Expected: `planar.faces_by_role` gains `taxiway` /
`apron` faces against the before-column above; `report.load.pavement_source`
as in §44 (4); the object stage's pads now stand beside graded aprons (§20);
the census through `tools/harness/census.py`; NO shared-repo write. Register
the report with `tools/harness/frames.py`.

## RULINGS

## 2026-09-17a aptstamp MERGED (9ba48ba2 → 7e417c16; standing suite on the merged tree 1871 passed, 0 FAILED): ONE APT.DAT SELECTOR — the freshness stamp and gate watch the file the BUILD reads

auto_patch carried two apt.dat policies. The freshness gate and `engine_v2._stamp_header` re-derived v1's `osm_load._pick_best_apt_dat_against_osm` (first custom pack carrying a 1201/1202 taxi network, else fall back to Global Airports — user 2026-06-16, the MKStudios LPPT case); the build read `auto_patch_v2.airport.apt_dat.find_apt_dat` (§44 (1), the pack is the pack). MEASURED on the owner's install 2026-09-17 (both real selectors, read-only): of 1,327 CIFP airports carried by a custom pack the two disagreed at **225** — 220 v1=Global vs v2=the custom pack, 5 custom-vs-custom (KAUS, KJAN, MPTO, PAKD, YMML); 0 of a 60-airport sample of the 15,777 airports with no custom pack. Of the campaign airports only LPPT is in the set. For each disagreement the header stamped, and the gate re-derived, a file the build never opened — plus `o4_pack` and the pack-DSF identities — so editing the pack v2 DID read left the patch "current" and a stale patch was reused (twin: red on base, green after).

**THE BUILD IS THE AUTHORITY AND THE GATE FOLLOWS IT.** ONE selector: `find_apt_dat`, reached through `engine_v2.select_apt_dat`. `_pick_best_apt_dat_against_osm` keeps its name and delegates; v1's taxi-routing-fallback tail is DELETED (the v1 engine is retired, 13au; §44 (1) already ruled the tail out for the build; §44.1 C10 booked this unification for stage B). No v1 last-ditch resolver stands behind it. The 225 disagreeing airports rebuild ONCE; every agreeing airport's stamp bytes are unchanged. KNOCK-ON, same name, two other callers: `flat_site_mode` (:705, the DEM-inset stage) and the object-anchor worklist (`driver.py:605`) now read the pack v2 reads at those 225 — the inset side takes effect only under the owner's `--refresh-data dem`.

**UNWATCHED, STATED IN THE CODE:** §44's BORROWED Global Airports block (`o4_apt_dat_borrowed`; in the pack signature / partition-cache key, not in the freshness gate — the borrow is decided in the load stage after the stamp is cut). A Global Airports update in place does not invalidate a borrowed patch through the gate. Follow-up chip: `o4_apt_dat_borrowed_mtime` written in `pipeline/build.py`, read back through `layout.read_patch_source`.

Also: `auto_patch_v2/airport/apt_dat.py` reads pin `encoding="utf-8", errors="replace"` (v1's reader always has).

**OPEN, owner Q 17a-1:** `driver.py:1471`'s skip line says "no enabled scenery pack defines it", but neither selector reads `scenery_packs.ini`. 12 packs are `SCENERY_PACK_DISABLED` on the owner's install; the (now single) selector picks a disabled pack at 6 airports: LFMN, LPFR (Aerosoft), EBBR Light Fix, OBBI, OBBS, LEAM tdg. Should disabled packs be excluded from apt.dat selection? Measured, not changed.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

