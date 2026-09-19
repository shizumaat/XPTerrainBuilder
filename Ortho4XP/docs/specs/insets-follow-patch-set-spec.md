# Insets follow the patch set; boundary airports ask

Spec: 2026-09-18, DRAFT FOR RATIFICATION (Fable, design only — no
implementation code accompanies it). **AMENDED 2026-09-18 (rev 2) to the
owner's answers, RULINGS `## 2026-09-18c`; rev 3 (2026-09-18) RULES the
implementer's three slice-1 deviations — §C.1 rewritten (the ask
geometry is the AIRSIDE CLAIM, not a scalar patch reach), OQ1/OQ2 closed
by RULINGS 2026-09-18e.** Ruling of record:
`docs/RULINGS.md` the 2026-09-18 entry "insets follow the patch set;
boundary airports ask" (the key 18b is carried TWICE in RULINGS — cite
by subject) as AMENDED by 18c. Same-day peer law it must not collide with:
`## 2026-09-18a` (tile cfgs are sparse; engine-owned write-through).
Pre-ship mode and BUILD ECONOMY (`Ortho4XP/CLAUDE.md`) govern the
implementer; deviations STOP-and-report to this spec's author.

Related but ORTHOGONAL: `docs/specs/round13-border-aware-inset-fetch-spec.md`
is about PROVIDER data borders (state/country lidar projects inside one
inset). This spec is about 1° TILE borders. Nothing in R13 changes.

## 0. The ruling and the measured facts

Owner, verbatim: (1) "Use the existing setting that determines which
airports get an auto-patch, default is ICAO only, and we should only
download high res elevation insets for the airports that are getting
patched." (2) "When a tile has an airport that cross the boundary, we
should present a dialog asking the user if they want to build the
adjacent tile as well or skip creating a patch for the airport(s) on
boundary."

Measured (brief; not re-derived): app 1.0.350, tile +38-010, ~3 h.
LPMT's production-DEM window crossed lon −9;
`auto_patch_v2/airport/dem_production.py` `_warm_tile` (:799-850) ran
`INSETS.ensure_insets_for_tile` over all 17 OSM aerodromes of the
never-built +38-009 — ~190 MB each at 0.5 m, ~90 KB/s, from inside the
auto-patch POOL CHILD, where `UI.progress_bar` / `task_meter` never reach
the app.

One fact read by this lane (shared corpus, read-only, one sidecar):
`Elevation_data/+30-010/N38W010_airport_insets/LPMT_portugal50cm.json`
`bounding_box_wgs84` east = −8.98365. With the 2,000 m margin
(0.02305° of longitude at 38.5°N) LPMT's OSM boundary ends at
**−9.0067: ~580 m WEST of the line.** LPMT's BOUNDARY does not cross
lon −9; only its 2 km inset box / DEM window does (by ~1.4 km). This
matters for §C.1 (the owner's Q2 answer: LPMT's class does not ask).

Owner answers folded into this revision (18c): **Q1** the inset set
follows its OWN dropdown (`airport_elevation_insets` → None/ICAO/All),
§A rewritten; **Q2** window-only crossers (class M, LPMT) do NOT ask and
download nothing (rev 3: the ask geometry is the AIRSIDE CLAIM, §C.1); **Q3** insets already on
disk keep being used; **Q5** no-UI default = skip, loudly; harness
`--boundary {skip,neighbour}` default skip; Q4 not asked, moot (§A.4).

## A. ONE mode predicate, TWO selections (AMENDED by the owner's Q1 answer, RULINGS 2026-09-18c)

Owner, verbatim (18c): "There's a "Fetch airport lidar insets" boolean
setting. Change this to be a drop down list with the same options as
"Auto-patch airport" so the user can choose which airports get detailed
insets." The inset set therefore follows **`airport_elevation_insets`**
(now None / ICAO / All), NOT `auto_patch`. Auto-patch Off no longer
implies no insets, and insets Off no longer implies no patches. What
stays from the first draft: ONE spelling of the mode filter, one
derivation site per selection, trim at the fetch site only.

### A.1 What exists today

| # | site | what it decides |
|---|---|---|
| 1 | `src/auto_patch/driver.py:1287-1384` (the `for icao, filepath in sorted(cifp_airports.items())` loop of `generate_auto_patches`) | PATCH set, inline: mode filter (`mode == "ICAO" and not (len(icao) == 4 and icao.isalpha())`, :1289) → manual patch → `parse_cifp_file` → `airport_in_tile` (`cifp_reader.py:233`) → `pair_runways` → `xplane_root_from_cifp_path` → (worklist, up-to-date reuse) → `_pick_best_apt_dat_against_osm` is None ⇒ skipped-not-built (RULINGS 17a selector) |
| 2 | `src/O4_Vector_Map.py:3089-3112` (`include_patches`) | the same mode filter AGAIN, to decide which on-disk `*_auto.patch.osm` are applied |
| 3 | `src/O4_Vector_Map.py:710-727` `resolved_auto_patch_mode` / `auto_patch_runs` | the `auto_patch` normaliser (legacy bool `True`/`False` → `"All"`/`"None"`) |
| 4 | `src/O4_Airport_Elevation_Insets.py:8441-8458` `insets_enabled_for_tile` — `if not getattr(tile, "airport_elevation_insets", False)` | the inset MASTER GATE, a truthiness read of a bool |
| 5 | `INS:8460` `_airport_bounding_boxes` | INSET set = every string-keyed entry of `dico_airports`; consults nothing |

### A.2 The one mode predicate and the two normalisers (frozen interface)

New module `src/auto_patch/selection.py` (pure; no network, GUI or DEM
imports; importable by the core without importing the rest of
`auto_patch` — keep its imports to stdlib + `cifp_reader`):

    MODES = ("None", "ICAO", "All")          # ordered: None < ICAO < All

    def mode_admits(code: str, mode: str) -> bool
        # "None" -> False; "All" -> True;
        # "ICAO" -> len(code) == 4 and code.isalpha()
        # THE one spelling. Sites 1, 2 and the inset trim all call it.

    def resolved_auto_patch_mode(tile) -> str      # moved from O4_Vector_Map
        # (re-exported there); legacy True -> "All", False -> "None" — UNCHANGED.

    def resolved_inset_mode(tile) -> str
        # tile.airport_elevation_insets normalised — see A.5 for legacy values.

`mode_admits` is applied to DIFFERENT code strings by the two
selections, and that is deliberate, not drift: the patch set tests the
CIFP identifier; the inset set tests the `dico_airports` KEY (ICAO /
IATA / local_ref / NAME — `O4_Airport_Utils` key order). Under `"ICAO"`
a 3-letter IATA key, an `LP63`-class local ref and a "Pista de Lavre"
name key all fail `len == 4 and isalpha` — exactly the 17-strip class
of the measured incident. Tuple-keyed unnamed strips are skipped before
the predicate, as today (`INS:8478-8486`).

### A.3 Selection 1 — the PATCH set (from `auto_patch`)

    @dataclass(frozen=True)
    class PatchCandidate:
        icao: str                 # CIFP identifier, upper case
        cifp_file: str
        runways: dict             # parse_cifp_file() result (reused by the driver)
        disposition: str          # "patch" | "manual" | "no_apt_dat"
                                  # | "no_xplane_root" | "boundary_skipped"
        reason: str
        apt_dat: str = ""        # rev 3, ACCEPTED deviation: the 17a-selected
                                  # apt.dat path, engine-internal (never on the
                                  # wire); "" unless disposition needs it. It is
                                  # what makes "moved, not added" true AND is the
                                  # no-network geometry source of §C.2.

    def select_patch_airports(tile, cifp_path, mode, *,
                              manual_icaos, boundary=None) -> list[PatchCandidate]

The driver loop's head lifted unchanged in ORDER and RESULT; `"patch"`
= "this build will BUILD or REUSE an auto-patch" (the up-to-date reuse
stays in the driver). `mode == "None"` returns `[]` without touching
CIFP. The apt.dat selection is MOVED earlier, not added.

DERIVATION SITE: `O4_Vector_Map.load_airports_and_prepare_dem`, right
after `build_airports_dico`: `tile.auto_patch_selection = …`, once.
Consumers: `generate_auto_patches` (iterates it; recomputes when the
attribute is absent — lab tools), `include_patches` (`mode_admits` +
refuses to APPLY a `boundary_skipped` airport's stale patch, §C.5), §C's
boundary check, and the A.6 cross-report.

### A.4 Selection 2 — the INSET set (from `airport_elevation_insets`)

    def inset_keys(dico_airports, mode) -> list[str]
        # string keys k of dico_airports with mode_admits(str(k).strip().upper(), mode)

DERIVATION SITE: inside `ensure_insets_for_tile` (`INS:8581`), the ONE
fetch entry: `boxes = _airport_bounding_boxes(tile, dico_airports,
only=inset_keys(dico_airports, resolved_inset_mode(tile)))`.
`_airport_bounding_boxes(only=None)` is unchanged for its other callers
(§B rows 2-4). This is the only trim; every reader stays disk-driven
(owner Q3 answer, §B.1).

MANUAL-PATCH airports (first draft's Q4, not asked, the "yes" stands):
moot under this design — the inset set no longer looks at the patch set
at all; a manually patched 4-letter airport is inset under ICAO like any
other.

### A.5 The setting change, and legacy values

`O4_Cfg_Vars.py:310` `airport_elevation_insets` becomes

    "type": str, "default": "ICAO", "values": ("None", "ICAO", "All"),
    "value_labels": {"None": "Off", "ICAO": "Airports with ICAO codes",
                     "All": "All airports"},

— the same three labels as `auto_patch` (:210-221); the hint is
rewritten (PROPOSED copy, the lead's to finalise): "Which airports get
automatic high-resolution elevation insets … "Off" fetches none and
bakes none (the build is byte-identical to the feature being absent)."
Settings label (`O4_Settings_Model.py:136`, `SettingsLayout.swift:98`)
PROPOSED: **"Airport lidar insets"** (a dropdown no longer reads as
"Fetch …").

**`"None"` KEEPS THE OLD `False` MEANING IN FULL — master gate off:**
`insets_enabled_for_tile` becomes `resolved_inset_mode(tile) != "None"`
(+ GDAL), so under Off nothing is fetched AND nothing on disk is
composited, baked, balloted or used for the smoothing radius, exactly
as `False` today. The owner's Q3 answer ("keep using insets already on
disk") governs airports OUTSIDE the set under ICAO/All; it does not turn
Off into "use what is cached". (Stated so the implementer does not have
to guess; if the owner wants Off-but-use-disk that is a fourth mode and
a new question, not this spec.)

LEGACY VALUES — **RULED (owner, RULINGS 2026-09-18e "OWNER ANSWERS OQ1/OQ2"):**
`True → "ICAO"`, `False → "None"`, absent → default `"ICAO"`.
`resolved_inset_mode` accepts, from any source: bool `True`/`False`;
the strings `"True"/"true"/"1"` and `"False"/"false"/"0"` (what a str-typed
read of an old cfg line yields); the three mode strings; anything else →
one WARNING line and `"ICAO"`. Where each legacy value lives and what
handles it:

| where | today | rule |
|---|---|---|
| global `Ortho4XP.cfg` line `airport_elevation_insets=True` | parsed as bool | read through the normaliser; REWRITTEN as the mode string the next time the global cfg is saved (no separate migration pass) |
| tile cfgs (RULINGS 18a sparse; AS LANDED after peer lane `b2cfgstamp`, RULINGS 2026-09-18d "lane b2cfgstamp MERGED": `migrate_tile_cfg` is DELETED) | key present only when it differed from the global | (i) an UNSTAMPED (pre-1.0.352) tile cfg is not migrated at all — `retire_unstamped_tile_cfg` (`O4_Settings_Model.py:596`) MOVES it to `*.pre352.bak`, so a legacy per-tile `False` there goes to the backup with the rest of the file and the tile starts from the global. That is the peer's ruled behaviour; this spec adds NOTHING to it (no rescue of the one key). (ii) a STAMPED cfg carrying a bool token (written by 1.0.352+ before this change) is read through `resolved_inset_mode`, and the legacy inspector `legacy_tile_settings` normalises BEFORE its foreign-enum test (`_normalize_legacy_mode_value`, landed at `:763`) so `"False"` is never reported/replaced as a foreign enum. `sparse_tile_values` (`:446`) then applies as usual (equal to the global ⇒ key removed). |
| JSONL `tile_settings_write` (`session.py:1329`, landed with `b2sparsecfg`) and the settings validator (`O4_Settings_Model.py:915-930`) | bool tokens validated as bool | the key is now a str enum: `values` validation applies; a front end older than this change sending `true`/`false` is mapped by the same normaliser, not rejected |
| `global_airport_elevation_insets` (schema snapshot :457) | bool mirror | follows the registry automatically (generated) |
| patch freshness stamp (`auto_patch/provenance.py:748`) records `str(value)` | `"True"` | records the NORMALISED mode and normalises the stored side on compare — otherwise every auto-patch on every install reads stale once and rebuilds (a tile-wide 60 s × N regression for a relabel). Twin: a stamp with `"True"` is current under `"ICAO"`. |
| v2 frame provenance `cfg:airport_elevation_insets` (`dem_production.py:884`) | `str(bool)` | records the normalised mode (string metadata; digest-neutral by the existing twin) |
| harness `DEM_FRAME_KEYS` (`tools/harness/build_airport.py:315`) compares dev cfg vs app cfg | raw compare | compares NORMALISED values — a lane cfg still saying `True` against an app cfg saying `ICAO` is the same frame, not a divergence refusal |

Behaviour change to state plainly: under the proposed map an upgraded
install that had the box CHECKED goes from "every named aerodrome" to
"ICAO-coded airports". That is the owner's intent in the original
ruling ("default is ICAO only"); nothing on disk is deleted and orphans
keep being used (§B.1).

### A.6 The two differences, and what records them

* **patch ∖ inset** (patched, not inset — e.g. `auto_patch=All`,
  insets `ICAO`, a 3-letter field; or insets Off): the airport solves on
  the production frame WITHOUT meter-class data — base raster, smoothed.
  Lawful (it is every no-coverage airport today). It must not be
  mistaken for a cold frame, and it must be visible:
  - `frame_state` / `airport_inset_frame_problem` are called with
    `expects_inset = inset mode admits this airport's key` (§B row 13);
    when False, a missing inset is NOT a problem, no refusal, no warm.
    (An orphan on disk is still baked and still recorded — Q3.)
  - one level-0 line per such airport, from the A.3 derivation site:
    `Auto-patch: XYZ is patched but outside the inset selection (airport lidar insets = ICAO) — solving on the base elevation.`
  - v2 provenance `inset_selection: "mode=ICAO admitted=False"` beside
    the existing `cfg:` keys; harness `frame.json` carries the same two
    fields. The harness single-airport entry REFUSES nothing new: an
    airport outside the inset selection is a legitimate (recorded) frame.
* **inset ∖ patch** (inset, not patched — `auto_patch=None`/manual/
  no-apt.dat/`boundary_skipped`, insets on): the inset only improves the
  draped mesh and the smoothing radius, as for any airport today. No
  line needed beyond the fetch log. NOTE the consequence for §C "skip":
  a boundary-skipped airport KEEPS its HOME-tile inset when the inset
  mode admits it (the first draft withdrew it; under the owner's Q1
  answer the inset key alone decides). No neighbour fetch happens for it.

## B. CONSUMER CENSUS (every reader of the inset set / directory / index)

Accessors grepped: `_airport_bounding_boxes`, `ensure_insets_for_tile`,
`ensure_airport_insets`, `list_cached_inset_dems`, `_read_index`,
`airport_inset_directory`, `airport_inset_dem`, `is_cached`,
`inset_completion_*`, `airport_inset_frame_problem`,
`seam_harmonized_ballot_insets`, `ensure_inset_water_supplement`.
`INS` = `src/O4_Airport_Elevation_Insets.py`.

RULING COLUMN KEY — **TRIM**: reads the selector. **DISK**: stays
driven by what is on disk, deliberately. **N/A**: does not read the set.

| # | consumer (file:line) | reads | ruling |
|---|---|---|---|
| 1 | `INS:8581` `ensure_insets_for_tile` → `:8460` boxes → `:7390` `ensure_airport_insets` (pool `:7816`) | dico → fetch set | **TRIM** — the one derivation site (§A.4), by `resolved_inset_mode` + `mode_admits` on the dico key. Only network consumer of the set. |
| 2 | `src/O4_Elevation_Level.py:594` (coastline approach-visibility ladder) | `_airport_bounding_boxes` as "where are airports" | **unchanged (`only=None`)**. Not an inset; non-default `elevation_level="coastline"` only. Noted, no action (it is not an inset and does not read either mode). |
| 3 | `dem_production.py:783` `_required_inset_box`; `tools/harness/build_airport.py:708` | boxes for ONE icao (the airport being built) | **unchanged arithmetic; gated by `expects_inset`** (§A.6) — the airport being built is in the PATCH set but, since 18c, not necessarily in the INSET set. The required box is computed only when the inset mode admits its key. |
| 4 | `tools/harness/build_airport.py:1258` `warm_airport_insets` (`--warm-insets`) | boxes filtered to human-named icaos | **unchanged** — an explicit, named, ledgered authorisation outranks the selector. |
| 5 | `tools/harness/build_airport.py:1540` `--refresh-data dem` → `ensure_insets_for_tile(refresh=True)` | whole-tile refresh | **TRIM, automatically** (it calls row 1). It reads the tile's inset mode like any build; a refresh of +38-009 under ICAO then refetches its ICAO-keyed airports, not 17. `prog.note` text changes from "for N airport(s)" to "for K selected (insets = MODE) of N". |
| 6 | `INS:8870` `assemble_inset_composite_source` (`O4_Mesh_Utils.py:2716`) | `list_cached_inset_dems` | **DISK**. An orphan inset (cached, airport no longer selected) keeps feeding the composite. See §B.1. |
| 7 | `INS:9227` `bake_airport_insets_into_alt_dem` (`O4_Airport_Utils.py:971,1113`; `O4_Mesh_Utils.py:2794`) | same | **DISK**. |
| 8 | `INS:11568` working-grid decision + `INS:11454/11465` `seam_harmonized_ballot_insets` (`O4_DEM_Utils.py:596`) | own + seam-component cached insets, probes from index (`INS:11014`) | **DISK**. The ballot is over files; a shrunk FETCH set removes no file, so no existing ballot moves (§B.1). |
| 9 | `INS:10282` `resolve_airport_smoothing_radius` (`O4_Airport_Utils.py:1019`) | cached insets intersecting each airport's mask | **DISK**. Smoothing itself still runs over ALL of `dico_airports` — unpatched airports are still smoothed at the base-grid radius, as any airport without coverage is today. |
| 10 | `INS:8348` `ensure_inset_water_supplement` (`O4_Vector_Map.py:~2458`) | every cached inset | **DISK**. Fewer insets on a fresh corpus ⇒ fewer detected basins, identical to an airport with no provider coverage today. |
| 11 | `O4_Vector_Map.py:755` `_airport_auto_roads_layer` | inset sidecar boxes → per-airport Overpass road queries | **DISK**, and it SHRINKS on fresh corpora for free: no inset ⇒ no road query for an unpatched strip. Correct — that feed exists for the v2 solve. The `airport_small_roads` cache stamp (the 1.0.349 abort class) is keyed on its own inputs; implementer verifies the stamp does not embed the box COUNT (one grep, no build). |
| 12 | `INS:8793` `is_cached` + `INS:8690-8740` stamp + `o4_engine/parallel.py:464` `STEP_FETCH_SUBSYSTEMS` | `complete.json` | **TRIM, schema-tolerant** — §B.2. |
| 13 | `dem_production.py:74` `frame_state` (`airport_insets_present`, `airport_inset_problem_kind`), `:708` `_compose`, `:875` "bake reports NO inset" | dir presence + THIS airport's record (`INS:10457` `airport_inset_frame_problem`, `:10442`) | **unchanged predicate, changed caller** — per-airport checks are about the airport being built (in the set). `_compose`'s two `_warm_tile` calls are deleted (§C.6). NEW: `frame_state(…, expects_inset: bool = True)`; the caller passes `mode_admits(icao, resolved_inset_mode(tile_of_that_cell))`. When False, neither the missing-dir problem nor the per-airport problem is raised (§A.6 patch∖inset: lawful base-DEM frame, recorded). The `:875` "bake reports NO inset while the file exists" check is unchanged (an orphan that exists must still bake — Q3). |
| 14 | `tools/harness/build_airport.py:678-713` `require_dem_frame`, `frame.json`, `dem_cache_state` | same predicate | **unchanged**; gains row 13's `expects_inset` for home and neighbour cells alike. `frame.json` gains `inset_selection: {mode, admitted}`; `DEM_FRAME_KEYS` (`:315`) compares `airport_elevation_insets` NORMALISED (§A.5) as ADDITIVE string metadata, proven digest-neutral by the existing `..._never_moves_a_frame_identity` twin. |
| 15 | `tools/inset_coverage_census.py:97-110,398` | its own copy of the box arithmetic (twin-pinned) | **unchanged arithmetic**; gains `--mode {None,ICAO,All}` (default: the cfg value) (the INSET mode; default: the cfg value) so the census reports "expected insets" against the selected population, not every aerodrome. Extension of a near-fit, not a fork. |
| 16 | `src/auto_patch/flat_site_mode.py:114-132` `tile_icao_candidates` | dico 4-letter keys ("same population as the inset fetch") | **unchanged**; docstring corrected: the inset population is the dico keys the inset mode admits — under ICAO exactly this function's population; under All a superset; under None empty (flat-site then runs for airports with no inset, which is its purpose). Flat-site substitution for an unpatched 4-letter airport is today's behaviour and is not touched. |
| 17 | `O4_Airport_Utils.py:1044` `warn_if_delivered_inset_clips_airport`; `:972,1120` `overlay_flat_site_insets` | per-airport cached inset | **DISK**. |
| 18 | `driver.py:1388` `_freshness_stamps_now` (patch freshness reads the tile DEM's inset provenance) | baked provenance | **normalised** (§A.5): the stamp's `airport_elevation_insets` field (`provenance.py:748`) stores and compares the normalised mode, so the bool→enum relabel rebuilds nothing. A REAL mode change (ICAO→None) legitimately stales patches whose inset provenance changes. |
| 19 | `session.py:1116` `features.insets_fetched`; `tools/check_build_time.py:321` | fetch counter | **unchanged**; §D's neighbour fetches increment the SAME counter on the home tile (a neighbour fetch is download wall time in this build). |
| 20 | `O4_Bathymetry_Band.py:1055,1134,1329,1602` | provider definitions + `fetch_inset` only | **N/A** — never reads the airport inset set, dir or index. |
| 21 | `tools/fetch_airport_elevation_insets.py:168`, `tools/flat_site_sweep.py:142`, `tools/apron_drape_read.py:133` | explicit tools | **unchanged** (named-airport instruments). |
| 23 | `INS:8447` `insets_enabled_for_tile` (master gate; called by rows 1, 6-8, 12 and `:8870`, `:11568`) | TRUTHINESS of the key | **MUST CHANGE** → `resolved_inset_mode(tile) != "None"`. HAZARD: the string `"None"` is truthy — left alone, Off would read as ON. `"None"` keeps the full old-`False` meaning (§A.5). |
| 24 | `INS:10583` `resolve_airport_smoothing_radius` — `if not getattr(tile, "airport_elevation_insets", False) or not has_gdal` | TRUTHINESS | **MUST CHANGE** — same hazard; calls `insets_enabled_for_tile` semantics via the normaliser. |
| 25 | `src/auto_patch/provenance.py:748` (freshness stamp key list) | `str(value)` | **normalised** — row 18 / §A.5. |
| 26 | `dem_production.py:884` (`cfg:` provenance keys) | `str(value)` | **normalised string**; metadata only. |
| 27 | `tools/harness/build_airport.py:315` `DEM_FRAME_KEYS` | dev-vs-app cfg compare | **normalised compare** (§A.5). |
| 28 | `O4_Cfg_Vars.py:310,768`; `O4_Settings_Model.py:136` (label, scope `tile`), `:676-685` (foreign-enum rule), `:915-930` (validator), `:435/:488` (18a sparse + migrate); `session.py:1329` `tile_settings_write` | registry + settings plumbing | **CHANGE** per §A.5 (type, values, labels; legacy map BEFORE the foreign-enum rule). |
| 29 | `Sources/SceneryKit/Resources/o4_schema_snapshot.json:121-126,457-462` (+ `global_` mirror); `Sources/XPTerrainBuilder/SettingsLayout.swift:98`; `Sources/SceneryKit/OrthoConfig.swift` (snapshot loader) | bundled schema; settings row | **REGENERATE** the snapshot (byte-for-byte twin `tests/test_schema_snapshot.py`); the Swift row renders from schema type — a `str` with `values` must render as the same picker `auto_patch` uses (verify, no new control). Any Swift code reading the key as `Bool` (grep at slice time: none found outside the schema/layout today) must go through the string. |
| 30 | tests reading the key as bool: `test_airport_elevation_insets.py` (6), `test_fetch_cache_predicates.py` (3), `test_auto_patch_freshness.py` (2), `test_base_elevation_providers.py`, `test_dem_baked_query.py`, `test_flat_site_mode.py`, `test_inset_bake_and_seam.py`, `test_object_elevation_ordering.py` (1 each) | fixtures set `True`/`False` | **KEEP AS-IS** where they set bools — they become the legacy-value coverage for free; add mode-string cases beside them, do not rewrite them. |
| 22 | Qt/Swift/session imports of `INS` (`O4_Qt_GUI.py:2323,2417,3874`, `O4_Qt_Settings.py:662`, `session.py:1386`) | provider registry only | **N/A**. |

### B.1 Orphans: cached insets for airports that left the set

RULED (owner Q3 answer, RULINGS 18c): orphans stay on disk and
stay USED (under ICAO/All; Off is the master gate, §A.5). Nothing is deleted, nothing is filtered at read time.

* Shared corpus `/Users/noah/XPTerrainBuilderData`: no file moves, so
  every ballot (row 8), bake, composite and smoothing radius on it is
  byte-identical after this change. No control in the artifact ledger is
  invalidated; no `--refresh-data` event is needed.
* Existing built tiles' seams: unaffected. The seam-factor ballot is a
  function of files present; this change removes none. (The known limit
  at `INS:11342-11348` — a never-fetched neighbour contributes nothing —
  is unchanged in kind; the neighbour simply contributes FEWER insets
  when it is eventually built.)
* The cost: two installs with the same settings and different cache
  HISTORY render an unpatched strip differently (one has the orphan).
  That class already exists (a failed fetch, a provider outage negative).
* The alternative — filter `list_cached_inset_dems` by the selection —
  is REJECTED in this draft: it needs the selection in step 2 (another
  process), needs the NEIGHBOUR's selection inside the seam ballot, moves
  surfaces and ballots on every existing corpus, and invalidates every
  shared control.

### B.2 `is_cached` and the completion stamp

`_inset_completion_key` (`INS:8740-8765`) gains `"selection_mode"`
(`"None"|"ICAO"|"All"`), and the stamp body gains `"selected"` (sorted
keys fetched-for; informational).

* Compare rule for `selection_mode` is ORDERED, not equality:
  `None < ICAO < All`; the tile is cached when `stamp_mode >= wanted`.
* A stamp WITHOUT the key (every stamp on disk today, e.g.
  `N38W010_airport_insets/complete.json`, schema `2026-07-30`) was
  settled over every string-keyed aerodrome — a superset of any
  selection — and reads as `All`. **`INSET_COMPLETION_SCHEMA` is NOT
  bumped.** Reason: a bump makes every tile on the shared corpus
  "uncached", the next guarded build re-runs the pass and tries to
  REWRITE `complete.json` — a shared-repo write inside DEM prep, which
  the harness refuses (CLAUDE.md "guard-blocked write inside DEM prep").
* `selection_mode` is the INSET mode (`resolved_inset_mode`), and it is
  now independent of `auto_patch`: the stamp and `is_cached` never read
  `auto_patch`, CIFP, manual patches or apt.dat. That makes the stamp
  EXACT, not a proxy: the inset set is a pure function of (airports
  layer, inset mode), both already in the key. The first draft's AIRAC
  residual is gone.
* `wanted == "None"`: `is_cached` is trivially True (existing
  disabled-is-cached branch, via the changed master gate, row 23).
* A per-tile mode (the key is a TILE var, sparse under 18a) is read from
  the tile object the scheduler already holds; a tile whose override was
  removed by write-through simply compares against the global mode.
* Legacy-bool stamps do not exist (the stamp never recorded the bool),
  so there is no stamp migration.

## C. BOUNDARY AIRPORTS

### C.1 What "crosses the boundary" means (REWRITTEN rev 3 — deviation 1 RULED)

**The measurement that refuted rev 2** (lane `insetpatchset1`, commit
`76ca638f`, `docs/DEFERRED_VERIFICATION.md`): max EMITTED node beyond
`_own_extent(margin 0)` — HECA 1,179.4 m (worst node 30.14771547619,
31.42227039529), CYXY 1,110.1 m ⇒ scalar `R_patch` = 1,200 m; max
`ProductionDem.z_many` reach — HECA 11,945 m, CYXY 5,090 m. With
E ⊕ 1,200 m LPMT (boundary −580 m) crosses lon −9 by ~+620 m ⇒ class S
⇒ ASKS — contradicting the outcome the owner's Q2 answer was given on.
The implementer STOPPED, correctly. The tail is groundside: service
roads, parking and access roads following OSM ways away from the field.
**`E ⊕ one scalar` is REFUTED and deleted from this spec** (no `R_patch`
constant is written; candidate (iii) "scalar per class" is rejected for
the same reason — the groundside tail has no meaningful bound).

**What the dialog protects, from the code** (`planar/overlay.py:916`
`seam_bands`, `constraints/seams.py:63` `seam_pins`, `emit.toml:88`
`half_width_m = 5.0`): every graticule line crossing the layout's extent
is cut out as a ±5 m band draped on the DEM; every band-edge vertex is a
HARD pin at `dem_z`, each served from ITS OWN tile's raster. So:

* NEAR-side pins come from the HOME raster — warm by construction. The
  home tile's mesh ends at the tile border. A cold neighbour cannot move
  them.
* FAR-side pins (5 m and beyond into the neighbour) come from the
  neighbour's raster — but the far side of THIS solve is meshed by
  nobody unless the NEIGHBOUR's build generates its own patch for the
  airport, which it does only when a CIFP threshold lies in it
  (`cifp_reader.airport_in_tile`), and then from ITS OWN solve on ITS OWN
  warm frame. Pin↔pin grade rows across the band are exempt
  (`constraints.seam_exempt`), the band itself is cut, so far-side values
  do not propagate to the near side.

What a cold neighbour therefore costs is not a wrong pin in the home
mesh; it is (1) a REFUSED or silently-warmed build (the 3-hour class —
removed by §C.6 for everyone), and (2) for an airport whose AIRSIDE
really continues across the line, a HALF-BUILT AIRPORT: runway/taxiway/
apron patched and inset on one side, default terrain on the other, and a
seam-factor ballot the unbuilt side never joined (`INS:11342-11348`
known limit). (2) is what the owner's words describe — "an airport that
cross the boundary … build the adjacent tile as well" — and it is a
property of the AIRSIDE, not of a service road. Airside-is-king: the
groundside conforms and never drives a decision about the airside.

**RULED — the ask geometry is the AIRSIDE CLAIM (candidate (i)):**

    A(airport) = union of apt.dat runways (row 100 rectangles) and
                 airside pavement (row 110 taxiway/apron polygons)
                 from the 17a-selected apt.dat (PatchCandidate.apt_dat),
                 buffered by R_air.

* apt.dat row 130 BOUNDARY is NOT in A: a fence line around grass is not
  "the airport crossing"; with no pavement across the line there is no
  half-built airside. (It also keeps A strictly inside the geometry the
  owner was shown for Q2: LPMT's boundary is −580 m and its pavement
  farther still.)
* OSM geometry is NOT used (candidate (ii) rejected): it is absent on
  exactly the never-built tiles where the question matters, it would
  make preflight and build-time disagree, and the OSM aerodrome polygon
  is the same fence-line class as row 130.
* `R_air` = the widest adjacent-ground band the airside can emit: the
  runway graded strip half-width (`zones.toml:22`, 75 m for code 3/4) +
  lip (`zones.toml:14`, 3 m), i.e. **R_air = 100 m**, written as ONE law
  value `emit.seam.ask_reach_m = 100.0` beside `emit.seam.half_width_m`.
  CONFIRMATION (implementer, same two captures, no build, ≤ 1 replay
  each): max distance beyond the UNBUFFERED airside claim of any emitted
  node whose role is in the AIRSIDE family (runway, taxiway roles, apron,
  graded_strip, adjacent_ground:*; NOT groundside_pavement, roads,
  object_pad, building, parking). Expected ≤ 100 m. If it measures
  > 100 m and ≤ 300 m, set the law value to the measurement rounded up
  to 50 m and report; > 300 m ⇒ STOP-and-report (an airside role is
  wandering, which is a different bug).
* **CLASS S** := A touches another 1° cell. **Everything else is class
  M** — including an airport whose groundside roads, parking, inset box
  or DEM window cross the line.
* **LPMT: pavement is more than 580 m from lon −9; A reaches at most
  ~−480 m. CLASS M. No dialog, no neighbour fetch — the owner's Q2
  answer holds as given.** No owner question arises.

**Class M with emitted geometry ON the line (the groundside tail).** No
clipping, no new geometry law — it is today's seam law, unchanged:
the band is cut, both band edges are pinned, near side from the home
raster, far side through the class-M CONTEXT-ONLY read (RULED, owner Q2
answer (a)): the neighbour is composed from whatever is on disk, never
fetched — warm ⇒ production compose; cold ⇒ base raster only, one loud
`[dem]` line and `provenance["context_only:<stem>"]`; no base raster ⇒
NaN ⇒ `v.dem_z is None` ⇒ `seam_pins` already skips the vertex (`:66`).
Emittable: it is a heightfield patch whose far side lies outside the
home tile's mesh and is generated by no other tile. Lawful under §38:
the pin law is met on both edges with the values each tile's raster
serves; nothing is relaxed. ONE interventional twin carries this claim
(§E test 6a): perturb the FAR-side raster by +10 m on a straddling
capture and assert every NEAR-side solved z moves < 0.01 m. If it fails,
STOP-and-report — the decoupling above is then wrong and class M is not
free.

"Needs a decision" = class S, disposition `"patch"`, AND the neighbour
frame is not already warm: `frame_state(neighbour)` has problems, or
`INS.is_cached(neighbour_tile)` is False under the NEIGHBOUR tile's own
INSET mode (its cfg, sparse per 18a). With the neighbour's inset mode
`"None"` the inset half is trivially warm and only its airports layer
(smoothing masks) can be cold. An already-built neighbour asks nothing.

### C.2 Preflight (before the build starts; cheap; NO network)

New session command **`boundary_airports`** (`EngineSession` method,
auto-exposed by `jsonl.py`'s handler table; arguments
`tiles: [[lat, lon], …]`). The handler replies `{"status": "started",
"request_id": N}` AT ONCE and works on a worker thread — a handler runs
on the transport read loop and must never block it (the
`airport_index` / `provider_sign_in` precedent). For each tile it runs
`select_patch_airports` with THAT tile's cfg (`CFG.Tile(lat, lon,
"").read_from_config()` — `auto_patch` is a tile var and, under 18a,
sparse: absent key ⇒ global), CIFP parsed ONCE for the whole request and
bucketed by cell, then tests P (or W) against the cell edges using:

the AIRSIDE CLAIM of §C.1, parsed from `PatchCandidate.apt_dat` (a local
file the 17a selector already chose; reuse v2's apt.dat row reader —
`airport/load.py`'s runway/pavement parse that feeds `_own_extent` — do
NOT write a second parser). A candidate without an apt.dat is
`no_apt_dat`: it gets no patch, so it never asks. ONE geometry, ONE
source, the SAME at preflight and at build time.

Never a query. Completion is a
new event (additive ⇒ **PROTOCOL_VERSION 1.8**):

    @dataclass(frozen=True)
    class BoundaryAirportsReady(EngineEvent):
        request_id: int = 0
        airports: list = field(default_factory=list)
        #   [{"icao", "name", "home": [lat, lon],
        #     "neighbours": [[lat, lon], …],      # cold ones only
        #     "crossing_m": float}]   # how far A reaches past the line;
        #   class S only — class M airports are never listed
        add_tiles: list = field(default_factory=list)
        #   union of cold neighbours NOT already in `tiles`, sorted
        remembered: str = ""      # "" | "neighbour" | "skip" (C.4)
        error: str = ""

`airports == []` ⇒ the front end proceeds straight to `enqueue_build`
with no dialog. `remembered != ""` ⇒ no dialog either; the front end
applies it (and still shows the per-airport lines in its log view).

### C.3 The answer

`EngineSession.build` / `enqueue_build` gain ONE additive keyword,
`boundary_policy: "neighbour" | "skip" | None = None`, forwarded by
`parallel.py` to worker children with the batch's other per-batch
settings (it sits beside `provider`/`zoomlevel` in the batch record) and
landed on the tile object as `tile.boundary_policy`.

* **"neighbour"** — the front end sends
  `tiles = selected ∪ BoundaryAirportsReady.add_tiles`. ONE dialog for
  the whole batch. The engine then warms each cold neighbour FRAME
  through §D; ordering is handled by a lock, not the scheduler (§D.2).
  Transitivity: an added tile may itself carry a boundary airport. The
  preflight is NOT iterated to a fixed point (Lisbon-to-Vladivostok
  chain); the added tiles' own boundary airports follow the same policy
  at build time, EXCEPT that a neighbour outside the batch is then never
  added — those airports fall to "skip" with their loud line. Stated in
  the dialog copy.
* **"skip"** — nothing is added. Each deciding airport becomes
  `disposition="boundary_skipped"` in the patch selector (§A.3): no
  patch, never in `tasks`, never expected
  by the manifest (the same place the `no_apt_dat` skip lives,
  `driver.py:1352-1374`, so H1's fatal path is not armed), and one
  level-0 line per airport:
  `Auto-patch: LPMT crosses into tile +38-009 (not built) — patch SKIPPED by your boundary choice; build +38-009 with +38-010 to patch it.`
  Collected on the tile build summary beside `skipped_no_apt_dat`. Its
  HOME-tile inset is unaffected (the inset key alone decides, §A.6); no
  neighbour fetch happens for it.
* **`None`** — resolve from cfg (C.4).

The build-time check uses the SAME function on the SAME apt.dat, so it
agrees with the preflight by construction; it exists because the answer
is a POLICY, not a list of ICAOs (CLI, harness, an added tile's own
straddlers, a front end older than 1.8) — there is no "unasked airport"
state.

### C.4 Remembered answer; CLI; harness

New **app-level** cfg var (in `cfg_app_vars`, NOT a tile var — under 18a
a tile var would be frozen per tile and need write-through; this is a
preference about how the user is asked):

    "auto_patch_boundary": {"type": str, "default": "Ask",
        "values": ("Ask", "Build adjacent", "Skip patch"), …}

* The dialog's "remember" checkbox writes it through the engine-owned
  settings-write path RULINGS 18a specifies (if that lane has not landed
  when slice 2/3 start, the front end's existing global-cfg write — an
  app var has no tile write-through to do); `remembered` in
  the event is this value mapped to `neighbour`/`skip`.
* Non-interactive contexts NEVER block. With `boundary_policy=None` and
  cfg `"Ask"`: CLI batch builds (`Ortho4XP.py` without a front end) and
  any front end older than 1.8 resolve to **"skip"** with the loud line
  (RULED, owner Q5 answer, 18c; rationale: never download or build what was not
  asked for; the 3-hour class cannot recur by default).
* **Harness.** `build_airport.py ICAO` (pipeline CLI, `core_hosted=False`)
  is UNCHANGED: it never warms, and a cold neighbour frame refuses with
  the `--refresh-data` scope, by the standing frame law. `build_airport.py
  --tile LAT LON` gains **`--boundary {skip,neighbour}`**, default
  `skip`, recorded in `frame.json`; `neighbour` means "the neighbour
  frame must ALREADY be warm" — a cold one REFUSES naming
  `--refresh-data osm_layers,dem` for that tile (the harness never
  downloads implicitly; §D's fetch is armed only when `core_hosted` and
  NOT under the shared-repo guard). `run_tile_mesh_only.py`: no patch
  generation, untouched.

### C.5 Stale patches under "skip"

`include_patches` (`O4_Vector_Map.py:3089-3112`) must not APPLY an
on-disk `LPMT_auto.patch.osm` from an earlier build when LPMT is
`boundary_skipped` this run: same loop, one more `continue` with
`(boundary choice: skipped)`. The file is NOT deleted (no destructive
op; a later "neighbour" build reuses or rebuilds it by the freshness
law). `tile.auto_patch_selection` is the source; when absent (step run
in isolation) it is recomputed — the selector is pure and cheap.

### C.6 What replaces `_warm_tile`

`ProductionDem._warm_tile` (`dem_production.py:799-850`), `_may_warm`
(`:792-797`) and both call sites in `_compose` (`:711-727`, `:750-760`)
are **DELETED** (BUILD ECONOMY: refuted mechanisms are deleted, not
gated). The pool child never fetches again. The owner's 2026-09-10
ruling it implemented ("why wouldn't the app just refresh it?") is
still honoured — by §D, in the main process, for the patch set only,
after an explicit choice. After deletion `_compose` does: `frame_state`
→ declared neighbour cold ⇒ `_degrade` ⇒ `ColdDemFrame` exactly as today
when a warm attempt failed (the `hint` text loses "TRIED to warm" unless
§D recorded an attempt on the tile object's provenance); UNDECLARED
(class M) neighbour ⇒ the context-only path of C.1.
`tests/auto_patch_v2/test_v2coldframe_warms_in_production.py` is
rewritten against §D's function, not kept green by a shim.

### C.7 Front ends (both ship it — Qt parity is law)

Flow, identical in both: user presses Build → front end sends
`boundary_airports` → on `BoundaryAirportsReady` with a non-empty list
and no remembered answer, ONE modal sheet → `enqueue_build(tiles′,
boundary_policy=…)`. A preflight `error` or a 10 s timeout proceeds with
`boundary_policy=None` (engine default) and logs the reason — the
preflight can never be the thing that stops a build.

UX COPY — **PROPOSED; the lead owns the final wording**:

> **Airports on a tile boundary**
> These airports extend into tiles you have not built:
> • LPMT Montijo — tile +38-010, extends into +38-009
> Their elevation patches need the neighbouring tile's terrain.
> **[Build adjacent tiles too (adds 1 tile)]**  **[Skip these airports' patches]**  [Cancel]
> ☐ Remember my choice (change it in Settings ▸ Airports)
> _Footnote:_ Adjacent tiles may have boundary airports of their own;
> those are patched only if their neighbour is also in this build.

* Swift: `Sources/SceneryKit/OrthoEngineClient.swift` (decode
  `"BoundaryAirportsReady"` — a string literal; send `boundary_airports`;
  pass `boundary_policy` in the `enqueue_build` arguments,
  `BuildModel.swift:1246,1368`), `Sources/XPTerrainBuilder/BuildModel.swift`
  (the gate before enqueue; the added tiles join the run's tile list so
  TileClocks/RunEta rows exist for them), a new sheet view, the setting
  row in `SettingsLayout.swift`.
* Qt: `src/O4_Qt_GUI.py` build start (`:3125-3170`, both
  `enqueue_build` sites) subscribes to the event in-process; dialog in a
  new small module; the setting appears through the cfg-vars registry
  automatically (`O4_Qt_Settings.py`).

`tools/blast.py` hazards quoted (index 43122f8):

* `events.py` / `OrthoEngineClient.swift`: "WIRE PROTOCOL … the wire
  name IS the Python class name … Swift matches string literals.
  Renaming either silently breaks the GUI." Standing drift:
  `python_only=['ImageryDownloadsDone']` (pre-existing; do not "fix" it
  in this lane). CO-CHANGED `OrthoEngineClient.swift(100%)`,
  `BuildModel.swift(100%)`, `session.py(80%)`, `parallel.py(60%)`,
  `jsonl.py(60%)`. "19 python handlers cover all 13 swift call sites" —
  becomes 20/14.
* `session.py`: ROLE LITERAL `building` present (untouched). 14 direct
  test importers — run `test_engine_session.py`, `test_engine_jsonl.py`,
  `test_engine_parallel.py` once.
* `O4_Airport_Elevation_Insets.py`: imported by 52 files; ENV FLAGS
  `O4_INSET_SEAM_HARMONIZE` (default ON) — untouched; WRITES
  `<inset dir>/<ICAO>_<provider>.tif`. Tests:
  `test_airport_elevation_insets.py`, `test_fetch_cache_predicates.py`,
  `auto_patch_v2/test_v2insetframe.py`, `test_v2insetmanifest.py`.
* `O4_Vector_Map.py`: 16 ROLE literals (untouched); READS
  `Patches/<tile>/<ICAO>_auto.patch.osm`. Tests:
  `test_cifp_missing_refusal.py`, `test_fetch_cache_predicates.py`,
  `test_harness.py`.
* `driver.py`: ENV `O4_AUTO_PATCH_REBUILD`; WRITES the auto patch;
  tests `test_auto_patch_freshness.py`, `test_auto_patch_engine_dispatch.py`,
  `test_cifp_missing_refusal.py`.
* `dem_production.py`: 1 src importer (`load.py`), 4 tests (above).

## D. "Build adjacent": what is fetched, in what order, with what progress

### D.1 The frame prelude (one function, main process)

New `O4_Vector_Map.ensure_tile_frame(lat, lon, *, reason)`: for ONE
tile — create its OSM dir, fetch-or-load the airports layer
(`OSM_queries_to_OSM_layer(AIRPORTS_QUERIES, …, cached_suffix="airports")`),
`build_airports_dico`, and `INSETS.ensure_insets_for_tile` with THAT
tile's cfg (so THAT tile's INSET mode — §A.4; the patch selection of the
neighbour is not needed and not computed) — i.e. exactly the fetch half of that
tile's own step 1, so when the neighbour's own build runs it finds
`is_cached` True and fetches nothing twice. The base raster is NOT
fetched here (`compose_tile_dem_from_disk` / `O4_DEM_Utils.DEM` owns that
and already does it on compose).

Called from `load_airports_and_prepare_dem` right after the home tile's
own `ensure_insets_for_tile`, once per cold neighbour of each deciding
airport, only when `tile.boundary_policy == "neighbour"` (and
`core_hosted`, and no shared-repo guard armed). "The neighbour's selection" means the neighbour tile's INSET selection:
for +38-009 under the default ICAO that is its 4-letter-keyed
aerodromes, not 17 strips; under its mode `"None"` it is nothing (only
the airports layer is fetched); under `"All"` it is all 17 — the user
chose that, and §D.3 shows it. The home airport's own key is admitted or
not by the NEIGHBOUR cell's mode for the neighbour's inset dir, exactly
as that tile's own build would decide.

### D.2 Ordering without a scheduler edge

Two tiles can need each other's frame (A in X reaches Y, B in Y reaches
X), so a dependency edge in `parallel.py` can cycle. Instead
`ensure_tile_frame` holds a per-tile `O4_File_Lock` on
`<tile>_airport_insets/.frame.lock` (the `.lock` family the shared-repo
guard already records as churn). Whoever arrives first — the
neighbour's own step 1 or the home tile's prelude — fetches; the other
waits on the lock (bounded: the lock primitive's existing stale-lock
deadline; on timeout it logs and proceeds to `frame_state`, which
refuses honestly) and then finds the pass settled. The home tile's own
`ensure_insets_for_tile` call takes the same lock for its own tile. No
change to `STEP_FETCH_SUBSYSTEMS` membership: `O4_Vector_Map` and
`O4_Airport_Elevation_Insets` are already in `"vector"`; the vector
step's fetch-admission predicate additionally requires
`INSETS.is_cached` of each declared cold neighbour (so a tile with a
neighbour fetch still holds a fetch token while it downloads).

### D.3 Progress that reaches the app

The fetch now runs in the tile's MAIN build process, where
`UI.progress_bar` and `TASK_METER` (`INS:7800-7822`, label
`"airport-insets"`) already reach the front end as `StepProgress`. Two
additions, no new event: (a) a level-0 line before each neighbour pass —
`Airport insets: tile +38-009 (neighbour of LPMT): 2 patched airport(s) — LPXX, LPYY`
— and one per completed inset with its size; (b) the task-meter label
for a neighbour pass is `"airport-insets +38-009"` so the activity view
distinguishes it. Twin: a fetch reached from a process whose
`multiprocessing.parent_process()` is not None raises in tests (the
pool-child class cannot return silently).

## E. Feasibility, build time, tests, guards, closing build

**Emittability.** Nothing here changes mesh or patch geometry for a
patched airport with a warm frame. "Skip" emits no patch: the airport
drapes on the production DEM exactly as a `no_apt_dat` airport does
today — a lawful heightfield. Class S + "neighbour" is today's SPLP/SPJC
path with a smaller fetch. Class M context-only reads touch no emitted
vertex OF THE HOME TILE'S MESH (rev 3: class M may emit groundside geometry
on and across the line — measured tail 1.18 km — and that is lawful
under the unchanged seam law, §C.1; test 6a is the proof obligation).
**Unemittable as literally worded:** none. The first draft's one
tension (a dialog for LPMT, whose patch never reaches the line) is
resolved by the owner's Q2 answer: class M does not ask — and rev 3's
airside-claim geometry keeps LPMT in class M after the 1,200 m
measurement refuted the scalar. The Q1 answer
adds no emittability risk: patch∖inset is the existing no-coverage
surface, inset∖patch the existing draped-inset surface.

**Build-time impact statement (HARD LAW §6; budgets exclude download).**
Compute: `select_patch_airports` is the driver loop's head MOVED ~1
phase earlier, net ~0; the preflight runs outside any build. Expected
compute delta < 0.6 s per airport / < 3 s per tile — the implementer
confirms from the recorded phase ledger
(`~/.ortho4xp/auto_patch_build_times`), no timing run, no Fable-5
optimisation review unless the ledger tripwire (~2×) fires. Download
wall (not budgeted, but the point of the ruling): LPMT tile — 17
neighbour insets × ~190 MB at ~90 KB/s ≈ 3 h ⇒ **0 bytes** under "skip"
or class-M-no-ask; under "neighbour" only +38-009's patched airports.
Home tiles everywhere: +38-010 has 6 cached insets, 5 of them 4-letter
ICAO — ICAO mode stops fetching name-/ref-keyed strips (e.g. `LP63`-class
keys) on every fresh tile. Large reduction; no regression path.

**Test plan (headless, `tmp_path`, no network, run once each).**
1. `tests/test_patch_selection.py` — `mode_admits` table; selector
   dispositions on a synthetic CIFP dir + fake apt.dat root; `None` ⇒ `[]`
   without opening CIFP (monkeypatched `open` counter).
2. TWIN: driver loop and selector agree — the set of ICAOs
   `generate_auto_patches` queues/reuses == `{c.icao for c if
   c.disposition == "patch"}` on the same synthetic tile; and
   `include_patches` applies exactly those. (Kills spelling #2.)
3. `_airport_bounding_boxes(only=…)` / `inset_keys`: 17-aerodrome
   synthetic dico (ICAO, IATA, `LP63`-class ref, name, tuple keys) —
   ICAO ⇒ only 4-alpha keys; All ⇒ every string key (== today); None ⇒
   the pass returns before any box; `only=None` byte-identical to today
   (rows 2-4).
3a. SETTING + LEGACY (§A.5): `resolved_inset_mode` table — bool
   True/False, `"True"/"true"/"1"`, `"False"/"false"/"0"`, the three
   modes, garbage ⇒ warning + ICAO; **the truthiness hazard**:
   `insets_enabled_for_tile` and `resolve_airport_smoothing_radius` with
   the STRING `"None"` are OFF (rows 23-24); Off is byte-identical to
   old `False` on the existing gate-off fixtures.
3b. Tile-cfg plumbing AS LANDED (rev 3): a STAMPED sparse tile cfg
   carrying `airport_elevation_insets=False` resolves to `None` and
   `legacy_tile_settings` reports NO foreign enum for it; `=True` under
   global ICAO resolves to ICAO and `sparse_tile_values` drops it as
   equal-to-global; an UNSTAMPED cfg is retired to `*.pre352.bak`
   (the peer's twin already covers that — do not duplicate it, assert
   only that this lane added no migration path: `migrate_tile_cfg` stays
   absent); `tile_settings_write` accepts the three modes and maps a
   legacy bool; validator rejects `"Sometimes"`.
3c. Freshness: a patch stamp recording `"True"` is CURRENT under
   `"ICAO"`; ICAO→None is stale. `DEM_FRAME_KEYS` compare: dev `True`
   vs app `ICAO` is NOT a divergence.
3d. Schema: regenerate `o4_schema_snapshot.json`; `test_schema_snapshot.py`
   byte-for-byte green; the key's `type` is `str` with the three values
   and labels, its `global_` mirror likewise. Swift: a `SceneryKitTests`
   case that the bundled schema yields a picker-typed setting with 3
   values for the key and that a cfg line `=True` loads as `ICAO`
   (through whatever Swift-side cfg reader exists — if Swift parses cfg
   values itself, that reader needs the same map; grep at slice time).
3e. Independence + cross-report (§A.6): `auto_patch=None`, insets ICAO
   ⇒ insets fetched, no patches; `auto_patch=All`, insets ICAO, 3-letter
   field ⇒ patched, NO inset box, the "outside the inset selection"
   line, `expects_inset=False` ⇒ no cold-frame problem, provenance
   `inset_selection` recorded.
4. Stamp: legacy stamp (no `selection_mode`) reads cached under ICAO and
   All; ICAO-stamp + wanted All ⇒ not cached; **no write occurs** when a
   legacy stamp is read (assert under the conftest refuse-mode guard).
5. `frame_state(expects_inset=False)` names no missing-dir problem;
   default unchanged.
6. Boundary geometry (rev 3): synthetic apt.dat — (a) pavement 580 m
   from the edge with a groundside road crossing it ⇒ class M, not
   listed, no decision (the LPMT twin); (b) apron polygon 60 m from the
   edge ⇒ class S (R_air); (c) runway rectangle across the edge ⇒ S;
   (d) row-130 boundary across the edge, pavement 400 m short ⇒ M;
   (e) class S with a warm neighbour ⇒ no decision; preflight and
   build-time verdicts identical on all five.
6a. FAR-SIDE INVARIANCE (interventional; the claim §C.1 rests on): on a
   registered straddling capture (`frames.py list SPJC` / SPLP; replay
   only) or, if none replays, a synthetic two-cell planar fixture —
   far-side raster +10 m ⇒ max |Δz| over near-side vertices < 0.01 m;
   far-side raster ABSENT ⇒ far-side seam vertices unpinned, solve
   completes, near side unchanged.
6b. Class-M context-only read: cold neighbour ⇒ ZERO calls into
   `INSETS.ensure_*` / `OSM_queries_to_OSM_layer`, one `[dem]` line,
   `context_only:<stem>` in provenance, no `ColdDemFrame`.
7. Protocol: `boundary_airports` replies `started` at once;
   `BoundaryAirportsReady` serialises through `serialize_event`;
   `enqueue_build(boundary_policy=…)` reaches a (fake) worker child.
   Swift: `SceneryKitTests` decodes a recorded `BoundaryAirportsReady`
   line. Wire twin: `tools/blast.py --audit` shows no new drift.
8. "skip": airport absent from `tasks` and manifest, loud line present,
   stale on-disk auto patch NOT applied, no inset box for it.
9. `_warm_tile` gone: `ProductionDem` with `core_hosted=True` and a cold
   declared neighbour raises `ColdDemFrame` and performs ZERO calls into
   `INSETS.ensure_*` (monkeypatch raises). Pool-child fetch twin (§D.3).
10. `ensure_tile_frame` lock: two threads, one fetch (fake strategy
    counter == 1).

**Convergence guards (mandatory in the implementation brief).**
Materiality floor: surfaces are not a target here; the pre-registered
targets are COUNTS — (i) neighbour insets fetched for the LPMT twin = 0
under skip; (ii) home-tile fetch set == selector set; (iii) legacy-stamp
corpus writes = 0. Any elevation diff on a warm-frame control < 0.01 m
is PASS-with-residual. Attempt cap: 2 fix iterations per target, then
STOP-and-report. Heartbeat: START/step/EXIT in the lane's `.progress`.

**Closing build (ONE).** Not LPMT (network-heavy, app-only path). The
mechanism is proven by the SYNTHETIC TWIN (tests 6, 8, 9: a fake
two-tile corpus with a strip-heavy neighbour, fake fetch strategy
counting calls). The one real build is the cheap control through the
harness: `build_airport.py CYXY` on the shared corpus — single-tile
airport, asserts the no-boundary path is byte-stable (patch BODY hash ==
the ledger control at the base sha; selection recorded in `frame.json`).
If the lead wants a straddler too, SPJC is the registered class-S
fixture — orchestrator's call at batch time, not the lane's. The real
LPMT confirmation is the owner's next app build of +38-010 (expected:
minutes, no neighbour fetch) — a line in `docs/DEFERRED_VERIFICATION.md`.

## F. Implementation slicing (ONE Opus implementer per coupled set)

**Slice 1 — engine (one implementer; everything else depends on it).**
`src/auto_patch/selection.py` (new), `src/auto_patch/driver.py`,
`src/O4_Vector_Map.py` (`load_airports_and_prepare_dem`,
`include_patches`, `ensure_tile_frame`),
`src/O4_Airport_Elevation_Insets.py` (`_airport_bounding_boxes(only=)`,
`ensure_insets_for_tile`, completion key/stamp, `is_cached`, lock,
`insets_enabled_for_tile` :8447 and the :10583 truthiness read),
`src/auto_patch/provenance.py` (:748 normalised),
`src/auto_patch_v2/airport/dem_production.py` (delete `_warm_tile` /
`_may_warm`, `expects_inset`, normalised `cfg:` provenance,
`inset_selection`, context-only path),
`src/o4_engine/events.py` (+`BoundaryAirportsReady`, 1.8),
`src/o4_engine/session.py` (+`boundary_airports`, `boundary_policy`),
`src/o4_engine/parallel.py` (forward the policy; neighbour `is_cached`
in the vector predicate), `src/O4_Cfg_Vars.py` (`auto_patch_boundary` app var;
`airport_elevation_insets` bool → str enum, :310),
`src/O4_Settings_Model.py` (label :136; legacy map before the
foreign-enum inspector `legacy_tile_settings`; validator;
`sparse_tile_values` — all LANDED in slice 1 a–b),
`src/o4_engine/session.py` `tile_settings_write` (legacy bool accepted),
`Sources/SceneryKit/Resources/o4_schema_snapshot.json` (REGENERATED in
this slice, same commit as the registry change — the byte-for-byte twin
is red otherwise; it is a generated file, not Swift work), `tools/harness/build_airport.py` (`--boundary`, refresh note,
`frame.json` key), `tools/inset_coverage_census.py` (`--mode`),
`tools/INDEX.md` rows touched in the same commit, tests 1-10 incl. 3a-3e (engine
side), `docs/DEFERRED_VERIFICATION.md` line. STATUS (rev 3): steps (a) setting, (b) selector/trim, (c) the
measurement are MERGED on main (a30e8d74). What remains is **slice 1d —
the boundary half, ONE Opus implementer**: `src/auto_patch/selection.py`
(`airside_claim(apt_dat, icao)`, `crossing_cells(claim)`, the
`boundary=` argument → `boundary_skipped`), law value
`emit.seam.ask_reach_m` (`law/emit.toml` + its table reader),
`dem_production.py` (delete `_warm_tile` / `_may_warm`, context-only
path, `expects_inset` if not yet landed), `O4_Vector_Map.py`
(`ensure_tile_frame`, `include_patches` skip, policy read),
`O4_Airport_Elevation_Insets.py` (`.frame.lock`), `events.py` (1.8),
`session.py`, `parallel.py`, `O4_Cfg_Vars.py` (`auto_patch_boundary`) +
REGENERATED schema snapshot, `tools/harness/build_airport.py`
(`--boundary`), tests 5-10 incl. 6a/6b. ORDER: (1) test 6a FIRST — it is
the go/no-go for the whole class-M design, replay only; (2) the R_air
confirmation replay; (3) geometry + selector; (4) `_warm_tile` deletion
+ context-only; (5) protocol + policy + harness flag. Closing build:
unchanged (CYXY control through the harness).
Frozen for
slices 2-3: the command name, the event's class and field names, the
`boundary_policy` values, the `auto_patch_boundary` key and its three
values, and `airport_elevation_insets`' type/values/labels. ORDER inside
the slice: (1) setting + normalisers + truthiness reads + snapshot
(shippable alone — it already ends the 17-strip class on home tiles);
(2) patch selector; (3) boundary + `_warm_tile` deletion.

**Slice 2 — Swift (after slice 1's protocol lands; parallel with 3).**
`Sources/SceneryKit/OrthoEngineClient.swift`,
`Sources/XPTerrainBuilder/BuildModel.swift`, new
`Sources/XPTerrainBuilder/BoundaryAirportsSheet.swift`,
`Sources/XPTerrainBuilder/SettingsLayout.swift` (the new
`auto_patch_boundary` row; `:98` relabel of the insets row — it must
render as the enum picker `auto_patch` uses, driven by the regenerated
schema), `Sources/SceneryKit/OrthoConfig.swift` only if it special-cases
bool rendering for this key, `Tests/SceneryKitTests` decode + schema
tests (3d). Copy is a placeholder constant
block the lead edits.

**Slice 3 — Qt (parallel with 2).** `src/O4_Qt_GUI.py` (both
`enqueue_build` sites), new `src/O4_Qt_Boundary_Dialog.py`,
`tests/test_qt_*` headless dialog-model test (offscreen platform);
`src/O4_Qt_Settings.py` renders the insets key from the registry — verify
the checkbox became the combo with the three labels and that a legacy
`True` cfg shows "Airports with ICAO codes" (one headless test; no code
expected beyond the registry). Same
placeholder copy block.

## OWNER QUESTIONS

NONE OPEN. OQ1 and OQ2 were answered (RULINGS 2026-09-18e, "OWNER
ANSWERS OQ1/OQ2": True → ICAO, False → None, default ICAO; Off keeps the
old unchecked meaning in full). Rev 3's deviation ruling raises none:
the airside-claim geometry keeps LPMT's outcome exactly as the owner's
Q2 answer was given (no dialog, no neighbour fetch). One would arise
ONLY if test 6a fails — then, with the numbers: "LPMT: boundary −580 m,
groundside patch reach +620 m past the line; the far side turns out to
influence the near side — ask for such airports, or clip their
groundside at the tile line?" Not asked now.
