# Flight manager, the dynamic World pack and the three app modes

Status: rev 1, 2026-11-10 (Fable spec author). RATIFIED by the owner 2026-11-10T16:40Z ("all as recommended", §20 Q1–Q6 → RULINGS 2026-11-10k).
Implements owner RULINGS 2026-11-10e (regions, build pane), 10g (flight manager), 10j (Build · Fly · Library), with 10c/10d (favorites, one disk budget) and the "dynamic World" end goal (memory `goal-loader-100gb-beta8.md`, update 15:22Z: retire every ThunderBlade ortho and run everything locally).
Builds on: `docs/specs/local-imagery-cache-1992.md` rev 5 (`claude/lfav`; "the loader spec"), the World pack kit (`claude/lworld`), the drape kit (`claude/ldrape d36fdf51a`), #2001, #1699.

Tags: **[measured]** this machine, this repo or the named recording; **[source]** a cited file; **[estimate]** worked out here; **[assumed]** not yet tested, with its test in §19.

## 1. Goals

1. A pilot names a flight (SimBrief, a `.fms`, or nothing at all) and the app makes the scenery for it: departure ready before the flight, the route built ahead of the aircraft, the destination graded while flying, imagery sharpened by the existing follow job. No X-Plane restart, no reload in the air except as a last resort.
2. ONE Custom Scenery pack ("the World pack") holds every tile the app manages; tiles change inside it while X-Plane runs.
3. The app always says how long until the flight is ready, from times measured on this machine, and the pilot waits for it (10g: no "depart now and reload").
4. Everything fits the one disk budget (10d); what the app built by itself can be taken back by itself.
5. Both apps, one layout (#1244); the engine owns the logic; wire names are class names.
6. End state: every ortho the owner flies comes from this system; the per-tile packs and the ThunderBlade library are retired by a converter, not by rebuilding.

Not in this spec: hosting (#1986), the community library's own features (#1699; only its home in Library mode), the #2001 texture preview's drawing (only its home and its position source), Windows/Linux measurements (phase X names them).

## 2. Design basis: what is measured

### 2.1 The CYYR World pack flight (2026-11-10, 14:51–15:23Z)

Kit and recording: `/Users/noah/XPTerrainBuilderData/.harness/frames/lworld/cyyr-worldkit/` (`flight_world.jsonl` 72.7 MB, recorder v3, 1,916 positions; `flight_world_report.txt`; `world_log.jsonl`; registered in `docs/frames.jsonl` on `claude/lworld`).

- **H1 passed [measured]:** `+53-063` swapped in on the ground at 14:51:42 (0.47 s, 13.5 km before its column loads, `world_log.jsonl`) and `+53-064` built on the fly (start 14:55:47, build 336 s, staged and swapped at 15:02:24, total 397 s, 36.7 km before its column) were both opened by X-Plane when their columns entered, with no reload. X-Plane's own log confirms it: `Log.txt` line 9144 `DSF load time: 6621037 for file Custom Scenery/zXPTerrainBuilder World/Earth nav data/+50-070/+53-063.dsf (2205408 tris, …)` and line 9180 for `+53-064` (1,869,001 tris, 4.9 s).
- **H2, H3 passed [measured]:** placeholders load as `0 tris` (e.g. `Log.txt` 6858–6948, 9132–9133) and per-tile subfolders `terrain/<tile>/`, `textures/<tile>/` work (982 test-pack DDS loads in the report).
- **Light tile cost [measured, one tile, nice 10, X-Plane flying, cold caches]:** vector 173 s, mesh 25 s, masks 24 s, imagery + DSF 109 s (`build_root/build_+53-064.log`), then 59 s for the DSFTool relayout and verify. Settings: `build_root/XPTerrainBuilder.cfg` (`elevation_level=90`, `auto_patch=None`, `airport_elevation_insets=None`, `cover_airports_with_highres=False`, `imagery_on_demand=True`, `placeholder_zl_drop=3`, BI ZL16).
- **Light tile size [measured]:** 100–104 MB staged (DSF 45–53 MB uncompressed, the rest 512 px textures).
- **Frame time [measured, derived from the recording's `frame_s`]:** while the on-the-fly build ran (airborne, n=396) median 21.8 ms, p90 32.4, max 39.7; after it (n=1,248, over photo tiles) median 30.5, p90 35.4, max 48.8. One nice-10 build cost nothing visible on this 18-core, 128 GB Mac. Not an A/B (different scenery under the aircraft).

### 2.2 X-Plane 12's DSF window

From every `.dsf` open in the recording joined to the aircraft position [measured, derived here]:

| UTC | Opened | Aircraft | Reads as |
|---|---|---|---|
| 14:58:58–59:02 | column −63, rows 52–54 | lon −60.652 | column shift at B − 0.652 (B = −60) |
| 15:06:29–33 | column −64 | lon −61.652 | 0.652 |
| 15:13:59–14:03 | column −65 | lon −62.651 | 0.651 |
| 15:20:24–43 | column −66 | lon −63.657 | 0.657 |
| 15:14:23–25 | row 51, columns −65…−62 | lat 52.900, southbound | row shift 0.100 past the edge |
| 15:21:43–46 | row 54, columns −66…−63 | lat 53.100, northbound | 0.100 |

**The model.** X-Plane holds 4 columns × 3 rows. Columns are `B−2 … B+1` around a tile boundary B; B moves one column when the aircraft is more than 0.65° of longitude from it. Rows are `R−1 … R+1` around a row R; R moves when the aircraft is more than 0.10° beyond R's edge. At a flight load B = round(lon), R = floor(lat) [assumed from the CYYR start: lon −60.447 gave columns −62…−59]. A tile's DSF, `.ter` and textures are opened only when its column or row enters. The CYXY flight 2 gave four column shifts at 0.64–0.65 at 60°N (`O4_World_Pack.py:338-344`, lworld) [source, not re-derived].

**Lead.** When a tile enters, the aircraft is 1.35° of longitude or 0.90° of latitude from the tile's near edge:

| Latitude | East–west lead | 120 kt | 250 kt | 450 kt |
|---|---|---|---|---|
| 0° | 150 km | 40.6 min | 19.5 min | 10.8 min |
| 45° | 106 km | 28.7 min | 13.8 min | 7.6 min |
| 53° (measured) | 90 km | 24.4 min | 11.7 min | 6.5 min |
| 60° | 75 km | 20.3 min | 9.7 min | 5.4 min |
| north–south, any | 100 km | 27.1 min | 13.0 min | 7.2 min |

Time between two column entries along a parallel at 53°N: 1,086 s / 521 s / 289 s at 120 / 250 / 450 kt [estimate].

**Two defects in the kit's `xp_window`** (`O4_World_Pack.py:347-370`, lworld): the east branch (lines 359–360) uses `tlon − 1 + 0.65`, one degree late (correct: `tlon − 2 + 0.65`); the row rule (lines 355, 363–368) has no 0.10° hysteresis (it errs early, which is safe). Phase W0 replaces the function with a tracker that keeps B and R (§8.1).

### 2.3 The load witness in `Log.txt`

X-Plane writes `H:MM:SS.mmm I/SCN: DSF load time: <µs> for file Custom Scenery/<pack>/Earth nav data/<block>/<tile>.dsf (<N> tris, …)` for every DSF it loads [measured: 1,149 such lines in `/Users/noah/X-Plane 12/Log.txt` after the flight; placeholders `0 tris`]. Tailing it tells the engine, with no plugin and no sudo, which of our tiles X-Plane has loaded in this session and whether it read the placeholder or a real tile. It does not record unloads; the tracker of §8.1 covers those. [assumed: flushed within seconds in flight, U3.]

### 2.4 What already exists and is reused

| Piece | Where |
|---|---|
| World pack layout, placeholders, relayout, verify, one-rename swap | `src/O4_World_Pack.py` (lworld): `write_placeholder` :88, `is_placeholder` :114, `relayout_tile` :162, `verify_tile` :209, `dsf_header` :255, `swap_in` :302, `swap_out` :320, `ini_install` :373 |
| Drape tiles | `src/O4_World_Drape.py`, `O4_World_Drape_Fetch.py` (`claude/ldrape d36fdf51a`): `pol_text` :87, `drape_dsf_text` :106, `write_drape` :151, `verify_drape` :230 |
| Position, camera, reload command | `src/O4_XPlane_WebAPI.py`: `POS_REFS` :54 (incl. `frame_s`, `paused`), `PositionReader` :134, `reload_scenery` :229, `camera_position` :236 |
| Follow job, spawn/jump reload, tier planner, index | `src/o4_engine/imagery_follow.py`, `src/O4_Imagery_Spawn.py`, `O4_Imagery_Tier_Plan.py`, `O4_Imagery_OnDemand_Index.py` |
| Flight plan readers and route → tiles | `src/O4_Flight_Plan.py`: `parse_fms` :122, `parse_simbrief` :178, `fetch_simbrief` :231, `densify` :284, `route_tiles` :351; Swift twin `Sources/SceneryKit/FlightPlan.swift`, `RouteTiles.swift` |
| Measured build times | `src/o4_engine/tile_time_model.py` (`~/.ortho4xp/tile_build_times/`, 312 tiles recorded on this Mac; `record_build` :309, `predict_step_seconds` :686, `airport_seconds_range` :741) and `auto_patch.build_time_model` (`~/.ortho4xp/auto_patch_build_times`); ranges in `plan_estimate.py` (`tile_estimate` :201, spreads :64–65, `disk_verdict` :296) |
| Build queue | `session.build` (`session.py:957`), `enqueue_build` :1147 (joins a running run), `cancel_tile` :1408 (stops after the current step), per-build `overrides` |
| Machine slots and priority | `src/O4_Machine_Slots.py`: `BUDGET` :111 (3 GB per worker, 2 reserved cores), `NICE = 10` :120, `lower_priority` :427 |
| One disk budget | `src/o4_engine/storage_budget.py` (`claude/lfav`): `TIERS` :57, `TIER_HOOKS` :62, `status` :109, `hold` :160 |
| Rebuild data out of tile folders | `src/O4_Rebuild_Cache.py` (`claude/lrebuild`) |
| Converter of existing tiles (P1c) | `src/o4_engine/imagery_convert.py` (`converted_tiles` :235, `imagery_ondemand_convert` :399), `src/O4_Imagery_OnDemand_Convert.py` |
| Which pack draws a tile's mesh | `src/O4_Mesh_Order.py`: `drawn_mesh_dsf` :69, `tile_mesh_order` :87 |
| Capability flags, frozen protocol 1.32 | `src/o4_engine/events.py:192-227` |

## 3. Vocabulary

**Tile kinds in the World pack**

| Kind | What X-Plane gets | Made by | Cost | Size |
|---|---|---|---|---|
| `placeholder` | empty overlay DSF, 328 bytes; X-Plane draws its own scenery | region switch | none | one disk block |
| `drape` | overlay DSF of draped photo squares over X-Plane's own mesh | build-ahead (if D1 chooses it) | 15–37 s [source: master, ldrape] | ~39 MB [source] |
| `light` | our 90 m mesh, no grading, 512 px imagery | build-ahead (if D1 chooses it) | 397 s cold [measured], ~220–260 s with caches warm [estimate] | ~100 MB [measured] |
| `full` | the normal build: graded airports, the user's settings, 512 px placeholders sharpened on demand | the user in Build mode; the flight manager for departure, destination, alternate | minutes to tens of minutes, from the ledger | ~80 MB + rebuild data ~140 MB in `Rebuild_cache` [memory note figures] |
| `external` | nothing of ours: another enabled pack draws this tile's mesh (`drawn_mesh_dsf`) | the user, other tools | | |

`drape` and `light` are the two candidates for the **intermediate** kind; §17 is the decision point. The scheduler only sees a kind with a cost, so both paths are specified once.

**Roles in a flight:** `departure`, `enroute`, `destination`, `alternate`.

## 4. User flows

### 4.1 Build mode (today's view)

Unchanged, except: with `imagery_on_demand` on, "Install in X-Plane automatically" and "Skip tiles already built" are hidden and behave as on (10e (1); `BuildPane.swift:545-546`, `O4_Qt_GUI.py:1472,1482`; lane `lregions`), and a finished build is **published into the World pack** (§7.3) instead of a new `zOrtho4XP_<tile>` folder, so a tile built while X-Plane runs can appear without a restart. The follow line leaves this pane (§14).

### 4.2 Library mode

What the app keeps: built tiles and airports (today's Library window content), Favorites, Storage with the disk budget (moved from Settings, 10j), the World regions (10e (3)), pack health (missing art, old forests, optimise, mesh order, stale tiles), the patch library (#1699 section, as today), and "Convert existing tiles" (§13). The map shows tile kinds and favorites' stars.

### 4.3 Fly mode

1. **Open.** The side pane shows "New flight" and the last flights. If X-Plane answers with a flight loaded while the app is in another mode, a banner offers "Open Fly"; the app never switches by itself (10j).
2. **Name the flight.** Three sources in one list:
 - "SimBrief: latest plan" (username or pilot ID remembered; network);
 - the `.fms` files of X-Plane's `Output/FMS plans/`, newest first, read automatically (10g; 111 files on this Mac);
 - "Open plan file…" (`.fms`, `.lnmpln`).
 A fourth entry, "No plan: follow the aircraft", starts free flight (§8.5).
3. **Flight card.** Origin, destination, alternate if the plan has one, distance, time en route. Controls: "Also build the alternate" (off by default, 10g), cruise speed (prefilled from the plan, else from the last flight with this aircraft, else 250 kt), corridor width (default: the tiles the route crosses plus those within 20 km of it).
4. **Preparing.** The readiness checklist (§6.2) with one countdown: "Ready in about 12 min". The map draws the route, the corridor tiles by kind and state, and the first DSF window. Budget and network are checked first (§11, §12); a problem there is said before anything is built.
5. **Ready.** Notification "Ready for departure". If X-Plane is already standing at the departure with scenery loaded before the tiles existed, the app reloads the scenery once, on the ground, as the last readiness step, and says so ("Scenery reloads now, about N s"). If X-Plane has not loaded the flight yet, nothing reloads.
6. **Flying.** The pane shows the next tiles with their margins ("+53-066 ready 4 min before it loads"), the destination's line ("graded in flight, ready 18 min before its column loads"), the follow line (sharpening), aircraft and track on the map, "Live flight preview" (#2001). No build controls.
7. **Falling behind.** The app says what will happen and what helps: "Building is 3 min behind at this speed: +54-070 will show X-Plane's own scenery. Slowing to 380 kt keeps it." En-route tiles never cause a reload.
8. **Diversion.** "Divert…" (the alternate first, or any airport by search). Also offered when the aircraft has left the corridor for two minutes. §8.6.
9. **Arrival.** On the ground at the destination: "Flight complete". The record keeps what was built, how long each took, and what was late.

Departing before "Ready" is the pilot's choice in X-Plane; the app does not offer it. If it happens the app says once which tiles will be late and carries on by §8.

## 5. Engine: modules, commands, events

### 5.1 New modules (one responsibility each; none appends to an existing family file)

| Module | Holds |
|---|---|
| `src/O4_World_Pack.py` | from lworld, minus `xp_window`/`tile_reach`; plus the binary definition rewrite (§7.3) |
| `src/O4_World_Window.py` | pure: `WindowTracker`, entry lines, entries along a route |
| `src/O4_XPlane_Log.py` | pure: `Log.txt` tail reader, DSF load records |
| `src/O4_World_Regions.py` | the region table (lane `lregions` owns the name and content; §7.1) |
| `src/O4_Flight_Schedule.py` | pure: jobs, deadlines, feasibility, countdown, dispatch order |
| `src/o4_engine/position_feed.py` | ONE 1 Hz reader of the Web API, fanned out to the follow job, the World job, the flight manager and the map (today the follow job owns its own `PositionReader`) |
| `src/o4_engine/world_commands.py`, `world_job.py` | the `world_*` commands; the build-ahead job |
| `src/o4_engine/flight_commands.py`, `flight_manager.py` | the `flight_*` commands; the flight record and its job |

Command modules, not session methods, registered in the `jsonl.py` table beside `imagery_follow_start` (`jsonl.py:379`), so they stay out of the session's import closure (the reason given at `imagery_commands.py:36-38`). `O4_Flight_Plan.py` is extended in place (alternate, times, `list_fms_plans`); it is the family's one file.

### 5.2 Commands (JSONL names; the in-process Qt session calls the same handlers)

| Command | Reply / completion |
|---|---|
| `world_status` | sync: the fields of `WorldStatus` plus the region rows |
| `world_install {scenery_dir}` | creates the pack folder and its `scenery_packs.ini` row (`ini_install`); `restart_needed` true when X-Plane is running |
| `world_regions_set {regions: [id]}` | `{"status":"started"}`, then `WorldReady` (placeholders written or removed) |
| `world_job_start {mode: "track"\|"flight", flight?}` / `world_job_stop` | starts or stops build-ahead; `WorldStatus` events follow. Starts by itself, like the follow job (loader spec §4.1), when on-demand is on, a region is enabled and positions arrive |
| `world_tile_set {lat, lon, kind: "placeholder"}` | Library action "Give this tile back" (swap-out, §7.4) |
| `world_migrate {dry_run, tiles?}` | `WorldReady` (phase M) |
| `flight_plans_list {xplane_dir}` | sync: `[{path, name, origin, destination, modified_at}]`, newest first |
| `flight_plan_read {path}` | sync: the plan |
| `flight_plan_simbrief {user}` | `{"status":"started"}`, then `FlightReady` with the plan |
| `flight_create {plan, build_alternate?: false, cruise_kt?, corridor_km?}` | `{flight}`; preparation starts; `FlightStatus` events follow |
| `flight_update {flight, build_alternate?, cruise_kt?, corridor_km?}` | sync |
| `flight_status {flight?}` | sync snapshot, same fields as the event |
| `flight_divert {flight, to: "alternate" \| ident \| [lat, lon]}` | sync |
| `flight_reload {flight}` | the offered reload, pressed by the pilot |
| `flight_end {flight}` / `flight_list` | sync |
| `aircraft_watch {on}` | `AircraftPosition` at 1 Hz while on (#2001 and the Fly map) |

A flight build is never interactive: it passes `missing_art="leave"`, the default boundary policy and "not now" to pack questions (`session.build` asks through events otherwise, `session.py:973-976`); each question skipped is listed on the flight record for Build mode.

### 5.3 Events (class name = wire name; Swift matches them as string literals)

Added to `src/o4_engine/events.py` and, in the SAME PR, to `Sources/SceneryKit/OrthoEngineClient.swift` (the `case "…"` switch at :373–591 and the completion list at :1210), with decoders in new `Sources/SceneryKit/FlightWire.swift` and `WorldWire.swift`.

- **`FlightReady`** `(request, result, error)`: completion of an async flight command, same shape as `PlanEstimateReady` (`events.py:928`).
- **`WorldReady`** `(request, result, error)`: completion of `world_regions_set`, `world_migrate`.
- **`FlightStatus`**, every 2 s and at once on a change:
`flight`, `state` (`preparing` `ready` `flying` `arrived` `closed` `error`), `phase` (`parked` `taxi` `airborne` `approach` `landed`, empty while X-Plane is not read), `ready`, `countdown_s` (None = no defensible figure; views show a dash, the `RunEta` rule at `events.py:497-503`), `reason` (one sentence, ready to show), `items` (rows `[key, state, eta_s, detail]`, §6.2), `jobs` (rows `[tile, role, kind, state, remaining_s, margin_s]`), `route_km`, `done_km`, `eta_s`, `late`, `shed`, `reload` (empty, `ground_pending`, `offered`, `scheduled`, `sent`), `diverted_to`.
- **`WorldStatus`**, every 2 s and on a change:
`state` (`off` `idle` `following` `building` `paused` `error`), `reason`, `installed`, `seen_by_xplane` (None unknown), `restart_needed`, `tiles` (`{placeholder, drape, light, full, staged}` counts), `queue`, `building` (rows `[tile, kind, step, remaining_s]`), `loaded` (tiles X-Plane has loaded by the witness), `last_swap` (`[tile, kind, utc]`), `slots`, `frame_ms`, `governor` (`ok`, `reduced`), `bytes`.
- **`FlightNotice`** `(flight, code, title, text, severity)`: one-shot; the apps post it as a system notification. Codes: `ready`, `reloading_on_ground`, `falling_behind`, `tile_late`, `destination_ready`, `destination_late`, `diversion_ready`, `offline`, `budget`, `arrived`.
- **`AircraftPosition`** `(lat, lon, alt_m, track_deg, speed_ms, on_ground, paused)`.

### 5.4 Capability flags (appended to `CAPABILITIES`, `events.py:198`; the number stays 1.32)

`world_pack` (W1), `world_job` (W2), `flight_manager` (F1), `flight_notices` (F2), `aircraft_position` (U2/#2001), `world_migrate` (M). `tests/test_engine_capabilities.py` and `Sources/SceneryKit/EngineCapabilities.swift` gain each with its feature.

### 5.5 Settings (registry `src/O4_Cfg_Vars.py`; both apps, same rows)

| Key | Home | Default |
|---|---|---|
| `world_regions` | Library ▸ World | empty until chosen (Q5) |
| `world_intermediate` (`light` \| `drape`) | Settings ▸ Imagery, expert, until D1 | set by D1 |
| `fly_corridor_km` | flight card | 20 |
| `fly_build_slots` (0 = automatic) | Settings ▸ Build Engine, expert | 0 |
| `fly_sim_priority` (`smooth` \| `balanced` \| `fast`) | Fly pane | `balanced` |
| `flight_notifications` | Settings ▸ General | on |

`simbrief_user` stays the app preference it is (`O4_Qt_Flight_Plan.py:44`).

## 6. Data model

### 6.1 The flight record

`<data folder>/Flights/<id>.json`, written atomically; one flight is active at a time.

```
id            "20261110T1612Z-<origin>-<destination>"
source        {kind: simbrief|fms|lnmpln|none, name, read_at}
origin, destination, alternate      {ident, lat, lon}   (alternate may be null)
build_alternate                     false
waypoints     [{ident, lat, lon, alt_ft?, t_s?}]
profile       {cruise_ms, cruise_alt_ft?, ete_s?, basis: plan|aircraft|default}
corridor_km   20
state, phase, created_at, ready_at, departed_at, arrived_at
tiles         [{tile, role, kind, state, deadline_s, est_s: [lo, hi],
              started_at, finished_at, swapped_at, late: bool}]
skipped_questions  [..]      notes [..]
```

Plan reading adds to `O4_Flight_Plan.FlightPlan` (`:83`): `alternate`, per-waypoint `alt_ft` and `t_s`, `ete_s`, `cruise_ms`. From SimBrief: the OFP's alternate, navlog times and cruise speed **[assumed field names; a real OFP, anonymised, becomes the fixture in F1]**. From `.fms` 1100: `ADEP`/`ADES` and the waypoint altitudes (present in the owner's files, e.g. `CYLWCYYC.fms`); it has no times, so the cruise speed field decides.

### 6.2 Readiness items

Each row: `key`, `state` (`done` `working` `waiting` `blocked` `failed`), `eta_s`, `detail`. The flight is ready when every row is `done`.

| Key | Done when |
|---|---|
| `world` | the World pack is installed and this X-Plane session has it (a World-pack line in `Log.txt`, or X-Plane is not running yet). Otherwise `blocked`: "Restart X-Plane once" (a new pack is only read at startup) |
| `budget` | the flight's bytes fit (§12) |
| `network` | the providers and map data answer, or everything this flight needs is already on disk (§11) |
| `prefetch` | map data, elevation and placeholder imagery for every corridor tile are on disk |
| `departure` | the departure tile is `full` (ours or `external`), its airport core sharp |
| `first_window` | every corridor tile inside the first DSF window (§8.2) is at its wanted kind. These cannot be swapped once the flight is loaded |
| `route` | the schedule is feasible: every en-route tile finishes before it loads if takeoff were now (§9) |
| `destination` | built, or its build finishes before its tile loads, with the margin shown |
| `alternate` | as `destination`; only when the checkbox is on |
| `loaded` | X-Plane has loaded the real `departure` and `first_window` tiles (the witness), or X-Plane has no flight loaded yet. If it loaded placeholders: one reload on the ground now (§7.5), then `done` |

### 6.3 Jobs

`{tile, role, kind, klass, deadline, est_s: [lo, hi], needs_network, state}`; `state` is `queued`, `fetching`, `building`, `staged`, `swapped`, `late`, `shed`, `failed`. `klass` is the dispatch class of §8.4.

## 7. The World pack lifecycle

### 7.1 Regions → placeholders

The region set is simHeaven's X-World continents (10e). The six installed on this Mac and their distinct DSF tiles [measured, `Custom Scenery/simHeaven_X-WORLD-Pro_<region>-*`]: Africa 2,858; America 5,791; Antarctica 177; Asia 6,767; Australia-Oceania 1,496; Europe 1,791; 18,880 in all. The table itself (which tile is in which region) is lane `lregions`' product; this spec reads it through `O4_World_Regions.tiles(region)`.

Enabling a region writes a placeholder for each of its tiles that has no DSF of ours yet (`write_placeholder`; each is DSFTool round-trip checked today, which is too slow for 6,767 tiles: write ONE checked placeholder per tile through a pure-Python DSF writer verified against DSFTool in a twin). Disabling a region swaps its `drape`/`light` tiles out (§7.4) and removes its placeholders; `full` tiles stay.

Placeholders cost one disk block each (328 bytes; ~75 MB for all 18,880 on APFS) [estimate], so a region's real cost is the tiles later built in it, not its placeholders. The region switch therefore mainly says **where the app may build by itself**. Whether placeholders are needed at all is H4 (U1): X-Plane probes every pack for a tile's DSF when the column loads (the recording shows failed opens in packs that lack the file), so a DSF that first appears before the column loads may be picked up too. Placeholders stay regardless: they are the tested path.

### 7.2 One owner per tile

A tile whose mesh another enabled pack draws (`O4_Mesh_Order.drawn_mesh_dsf`) is `external`: the World pack holds at most a placeholder for it, and build-ahead never builds it. This keeps the owner's 2,597 `zOrtho4XP_<tile>` packs working unchanged until §13 moves them.

### 7.3 Build → stage → publish

1. Every build (Build mode, flight, build-ahead) runs in an ordinary build folder under the data folder, never inside the pack. Existing consumers of a build folder are untouched during the build.
2. **Stage:** the result is laid out in `World_staging/<tile>/` in the pack's shape (`relayout_tile`): textures hard-linked, `.ter` references rewritten (`rewrite_ter`), DSF definition paths given the tile subfolder. The DSF rewrite moves from the DSFTool text round trip (59 s on a light tile, §2.1) to a **binary rewrite of the definition atom and the MD5 footer** (`dsf_header` already walks the atoms, `O4_World_Pack.py:255-278`); the DSFTool round trip stays as the twin's oracle on three tiles.
3. **Verify** (`verify_tile`, `dsf_header`), then **swap** by §7.5.
4. The build folder is removed; rebuild data lives in `Rebuild_cache/<tile>` (lrebuild). `light` and `drape` tiles keep no rebuild data: they are remade from the caches.
5. The tile is registered with the on-demand index (`imagery_ondemand.register_tiles`, `:111`) so the follow job sharpens it. The index learns the layout through three fields on the row, `textures_dir`, `terrain_dir`, `config_dir`, resolved in ONE function (`INDEX.texture_path`, `:284`); `_scan_tile` (`:451`), the lander (`imagery_follow_land.py:68-80,106`) and the downgrade read through it. For drape tiles `_read_ter` (`:399`) also reads a `.pol`'s `LOAD_CENTER` and `TEXTURE_NOWRAP`.

A later phase (W3) may write the World layout at the writer (`O4_DSF_Utils.py:364,380,387,409` for `.ter`, `:1321,1521,1748` for the definitions) to skip the stage step; not needed for the first flights.

### 7.4 Swap-out

`swap_out` puts the placeholder back in one rename. The tile's `terrain/` and `textures/` folders are removed only when X-Plane is not running or has not loaded the tile. Used by: the budget (§12), a region switched off, "Give this tile back".

### 7.5 Swap rules

- **S1 Whole and verified first.** Nothing in the pack changes before the staged tile verifies.
- **S2 Folders first, DSF last, one rename** (`swap_in`, `:302-317`). The DSF is the only change X-Plane can see.
- **S3 Unloaded tiles only, while X-Plane runs.** A tile may be swapped when BOTH the witness shows no load of it since the last scenery load and the tracker (§8.1) puts it outside the window by a margin (0.05° or 60 s of flight, whichever is more). If they disagree, the tile counts as loaded.
- **S4 A loaded tile is never changed in place.** Its new version waits staged until the tile has left the window, X-Plane quits, or a reload is allowed by S6. (Loader rule R4, spec §4.7: `.ter`, DSF and masks are read only at scenery loads.)
- **S5 Never remove a name a loaded tile may still open.** When a staged version replaces a loaded one just before a reload, new files are added and same-named files replaced one by one (`os.replace`); old names are deleted only after the witness shows the reload read the new DSF. (`_place_dir`, `:281-299`, renames the old folder away at once; that stays for unloaded tiles only.)
- **S6 Reload, last resort.** Allowed: (a) on the ground before departure, as the `loaded` readiness step; (b) in the air, once, for the destination or a diversion airport that could not be in place before its tile loaded, announced 30 s ahead with "Not now", and only asked (never automatic) inside 20 km of that airport below 3,000 ft AGL; (c) after a spawn or jump, as P5 already does. Never for an en-route tile. (Q4.)
- **S7 Follow job.** The swap of a tile holds `imagery_follow.paused()` for that tile only; the job no longer pauses for every build (§8.7).
- **S8 Log.** Every swap is a line in `logs/world_pack.log` and a `WorldStatus` change.
- **S9 Windows.** A rename over a DSF another process holds can be refused; retry through `O4_Held_File.retrying_a_held_file` and stay staged if it keeps failing. Unmeasured (phase X).

## 8. Build-ahead

### 8.1 The window tracker

`O4_World_Window.WindowTracker` keeps B and R from the position feed by the rules of §2.2, restarts at a flight load or jump (the witnesses of `O4_Imagery_Spawn`), and is corrected by the witness: a load line for a tile the tracker held outside the window moves B or R to agree. While its history is unknown (first position of a session) it answers with the union of the plausible windows, so "loaded?" errs toward yes and deadlines err early.

### 8.2 Deadlines from a route

The route is densified at 5 km (`O4_Flight_Plan.densify`, `SAMPLE_STEP_KM` :50). A tracker is run along it from the departure. For each corridor tile, the first sample at which it enters gives its **entry point**; its deadline is the time the aircraft reaches that point, less the margin of S3 and the swap time. Tiles in the window at the first sample are the **first window**: their deadline is "before the flight loads" (readiness row `first_window`). The first window is taken as the union for B = floor(lon) and ceil(lon), so a start position near a column edge cannot leave a tile out.

Corridor: the tiles the route crosses, plus those within `fly_corridor_km` (`route_tiles`, `:351`); the destination's and departure's eight neighbours inside the regions; never `external` tiles or tiles outside the enabled regions (they stay X-Plane's own scenery, and the map shows them so).

Times: before takeoff, offsets from takeoff by the plan's profile (waypoint times when the plan has them, else cruise speed with a 250 kt climb/descent leg); in flight, from the aircraft's projection on the route and the faster of its measured groundspeed (`O4_Imagery_Follow_Motion`, position deltas) and the plan's.

### 8.3 What the numbers allow [estimate, from §2]

One light tile takes 397 s cold. Along a parallel at 53°N a new column enters every 1,086 / 521 / 289 s at 120 / 250 / 450 kt. With n corridor tiles per column and m build slots in flight the job keeps up when `n × 397 / m ≤` that period:

| | 120 kt | 250 kt | 450 kt |
|---|---|---|---|
| light, 1 tile per column | 1 slot | 1 slot | 2 slots |
| light, 3 tiles per column | 2 slots | 3 slots | 5 slots |
| drape (37 s), 3 tiles per column | 1 slot | 1 slot | 1 slot |

So with light tiles the app keeps up by itself at GA and turboprop speeds on a narrow corridor; a jet flight has part of its corridor built before departure, and the countdown says how much. Example: 1,000 km at 53°N, one tile per column, 15 tiles, one slot in flight: about 11 are built in flight and 4 before, adding about 26 min to the wait; with two slots, none. With drapes the wait is the departure and first window only.

### 8.4 Dispatch order

Classes, highest first:

| Class | Jobs |
|---|---|
| P0 | departure, first window, anything the `loaded` step needs (before departure only) |
| P1 | build-ahead: en-route tiles, earliest deadline first |
| P2 | destination (full, graded) |
| P3 | sharpening (the follow job's fetches) |
| P4 | alternate |

This is the brief's order (build-ahead > destination > sharpening > alternate). Two rules keep it from doing harm:

- **Laxity guard.** A job whose slack (deadline − now − remaining estimate, high end) falls under one build's length is dispatched next whatever its class, so the long destination build is not starved by a long corridor. A running lower-class build is interrupted only at a step boundary (`cancel_tile` semantics, `session.py:1408`) and resumes from its finished steps.
- **Shedding is not dispatch order.** When the set cannot all make it, what is given up, in order: the alternate; corridor tiles farthest from the route; corridor tiles on the route, latest deadline last. The destination is never shed; if it will be late the pilot is told (§4.3 step 7) and S6 (b) applies.

`enqueue_build` appends first-in-first-out today (`session.py:1147-1200`, `parallel.enqueue`); it gains `deadline` and `klass` per batch and the run picks its next tile by them. A `profile` override (`"light"`) joins `overrides` and is resolved in ONE engine function to the settings of §2.1; no view composes it.

### 8.5 Free flight (no plan)

Deadlines come from the track instead of a route: the tracker is run along the straight track for the lead time of §2.2 plus a turn margin of one row and column toward the turn. Candidates are the tiles that would enter within that horizon. This is also the mode after leaving a plan's corridor. With light tiles it holds at GA speeds; above that the pane says "Flying faster than tiles can be built here: ahead stays X-Plane's own scenery".

### 8.6 Diversion

`flight_divert` (or the pilot accepting the off-route offer) replaces the destination. The new airport's tile is built `full` in class P0. If its tile is still outside the window, it is swapped in before it loads when the estimate allows; otherwise it is built, staged, and S6 (b) applies. The pane shows the time until it is ready, so the pilot can hold. The old destination's build is stopped at its next step boundary unless it is the alternate.

### 8.7 The follow job beside builds

Today no fetch starts while any build runs (`imagery_follow.py:285-287`; `jsonl.py:379-380` passes `busy = session._building`). Build-ahead runs for most of a flight, so this becomes: builds happen outside the pack (§7.3), and the follow job is held only for the tile being swapped (S7). While a P0–P2 job's slack is under twice its estimate the follow job stays at one fetch slot (no adaptive growth, `O4_Imagery_Fetch_Slots`); otherwise it is adaptive as ruled in 10b (1). The per-host request budget is already shared with builds (loader spec §4.4).

## 9. Readiness and the countdown

**Estimates.** Per job, per step, from the recorded ledger: `tile_time_model.predict_step_seconds` (the tile's own last builds first, else the cross-tile fit), `airport_seconds_range` and the auto-patch model for graded airports, ranged by `plan_estimate`'s spreads (0.75–1.5 known, 0.5–2.5 unknown). Additions to the record's features (`features_for_record`, `:106`): `profile` (`full`, `light`, `drape`), `sim_running`, `slots`; `_same_tile_compatible` (`:365`) never mixes profiles; new step keys `drape` and `stage` join `STEP_KEYS` (`:56`). Before any light or drape build is recorded, the constants are the CYYR figures of §2.1 and the ldrape figures. Each finished job of the flight rescales the remaining estimates of its profile by measured / predicted, clamped to 0.5–2.5.

**Feasibility.** Jobs in dispatch order with their high-end estimates on m slots; job k finishes at `F_k`; it must hold `F_k ≤ T + d_k`, with T the wait until takeoff and `d_k` its deadline after takeoff (0 for P0). The countdown is the smallest such T: `max(F of the last P0 job, max_k(F_k − d_k))`, plus one build's length of slack because a build is not interrupted mid-step. It is recomputed every status tick from the real progress (`remaining_step_seconds`, `:79`). It shows "about N min"; with no defensible basis it shows a dash.

**After ready** the flight stays ready; building goes on by deadline, and waiting on the ground only adds margin.

**Phases** come from the position feed: `parked` (on the ground, under 2 m/s), `taxi`, `airborne` (15 m AGL and 25 m/s for 10 s), `approach` (within 40 km of the destination, descending), `landed`; the flight closes after 10 min parked at the destination or by "End flight".

## 10. Sharing the CPU with X-Plane

- **Priority.** Every build child already runs at nice 10 / below-normal (`lower_priority`, `O4_Machine_Slots.py:427`). The CYYR flight ran one such build with no visible frame cost (§2.1).
- **Slots.** While X-Plane answers and the phase is beyond `parked`, the machine-slot capacity is the flight capacity: `fly_build_slots`, or automatically `clamp((cores − 6) // 3, 1, 3)` and never more than memory admits (`BUDGET`, `:111`) [estimate; the 6 is X-Plane's share, to be set from the F1 flight]. While `parked` and preparing, the normal capacity less two more cores: the pilot is waiting and frame rate matters little.
- **Governor.** The feed reads `sim/time/framerate_period` (`POS_REFS` :77). Baseline: the p90 frame time over the last minute with no build running. If p90 over 30 s rises more than 25 % above it (`balanced`; 10 % `smooth`; off for `fast`), one slot is given back at the next step boundary, down to one for P0–P2 work and zero for P4; after 60 s back under, one is returned. `WorldStatus` carries `slots`, `frame_ms`, `governor`.
- **Landings.** The loader's 4 landings a second (R6) stands. X-Plane's own DSF read of a light tile took 4.9–6.6 s on its loader thread (§2.1); swaps are therefore spaced at least 10 s apart.
- **Timing honesty.** Times recorded with `sim_running` true are what the countdown predicts flights from; they are never compared with harness timings (CLAUDE.md: single runs swing ±25 %).

## 11. Network and offline

- **Planning.** SimBrief needs the network; `.fms` and files do not. A failed fetch is one sentence from `FlightPlanError`.
- **Corridor pre-fetch** (readiness row `prefetch`): regional map extracts, elevation (and airport insets for departure, destination, alternate), placeholder imagery for every corridor tile, before departure. After it, in-flight builds need no network; only sharpening does.
- **Offline while preparing.** Jobs whose inputs are all on disk build. The rest are `blocked`: "Needs internet". The flight is not ready. The pilot may choose, per flight, "Fly with X-Plane's own scenery there" for blocked en-route tiles; the departure and destination cannot be waived this way (Q3).
- **Offline in flight.** Builds continue from the pre-fetch; the follow job says "Offline: imagery stays low-res" (`imagery_follow.py:79`) and resumes by itself; a notice is posted once.
- **Failures.** A job that fails twice is `failed`; an en-route tile stays a placeholder; a failed destination build is a notice with the reason and the tile's Build-mode link. Convergence guard: two attempts per job, never a third.

## 12. The disk budget

- **Pre-check** at `flight_create`: bytes the flight adds = corridor tiles by kind (§3 sizes) + pre-fetch caches (`plan_estimate` ranges) + sharp imagery along the route (2.2–4.6 GB per flight hour at 250 kt, loader spec §4.3) [estimate], against `storage_budget.status` (budget, use, floor) and the volume's free space (`disk_verdict`). Outcomes: fits; fits after clearing N GB of older sharp imagery and caches (said, not asked); does not fit, `blocked` with the figures and the two remedies (raise the budget, narrow the corridor).
- **Protection.** The active flight's tiles and the sharp imagery ahead of the aircraft are exempt from `hold` and the follow job's sweep until the flight closes (a `protected_tiles` hook beside `protected_cache_keys`).
- **A new clearing tier (needs the owner, Q1).** 10d (2) puts DSFs and placeholders on the floor that is never cleared. Tiles the app built by itself (`drape`, `light`) would then only ever accumulate: up to ~1.9 TB (light) or ~0.7 TB (drape) for 18,880 tiles [estimate]. Proposed: a tier `world_intermediate`, after sharp imagery and before per-tile rebuild data (`TIERS`, `storage_budget.py:57`, through `TIER_HOOKS`): the least recently flown intermediate tile is swapped out to its placeholder (§7.4). Tiles the user built (`full`) and favorites stay on the floor.
- **Storage rows.** The World pack is one row in Library ▸ Storage with its split by kind.

## 13. Migration from per-tile packs

State [memory note, measured 2026-11-10]: 2,597 `zOrtho4XP_<tile>` entries in Custom Scenery, 2,443 of them links to ThunderBlade (8.4 TB). P1c (in main) makes a lean local on-demand copy of an entry and exchanges it at the entry's own name (`imagery_convert.py`); its manifest names where the full textures live, so the follow job lands them from the mounted library with no network.

- **M0 (from W1): coexist.** §7.2. Nothing of the owner's moves.
- **M1: converter target "world".** `world_migrate` (X-Plane closed; the converter already checks, `imagery_convert.py:112`) takes each converted or local entry: stage it into the World pack by §7.3 (binary definition rewrite; a 7z-compressed DSF is unpacked first, `O4_DSF_Compress` has no unpack today and gains one), verify, swap in, then set the entry's row to `SCENERY_PACK_DISABLED` and keep the entry for `revert`. `dry_run` reports counts, bytes and the time from a 6-tile sample. One tile is one atomic step; a run killed anywhere leaves every tile drawn by exactly one pack.
- **M2: retire the library volume.** When the owner says so: the disabled link entries and their ini rows are removed by a Library action (links only; the volume's files are never touched). From then on full textures come from the providers on demand. Rebuild data of local tiles moves by lrebuild's option A.
- Order: M1 only after one flight each of W2 and F1 on fresh tiles; M2 only on the owner's word.

## 14. UI homes, both apps

**The mode switch.** A segmented control Build · Fly · Library leads the map toolbar (`MapMainView.swift` toolbar :184–247; Qt toolbar `O4_Qt_GUI.py:1101-1172`). The side pane's content follows the mode; the map, its selection and the rest of the toolbar are shared (10j: one selection across modes). The last mode is remembered. The Library window (`XPTerrainBuilderApp.swift:52`; Qt `LibraryDialog`, `O4_Qt_GUI.py:1961-1970`) becomes the Library pane; the menu item selects the mode. Settings ▸ Storage (`SettingsLayout.swift:209`) moves to Library.

**Manifest rows for `Ortho4XP/tests/test_qt_layout_parity.py`** (Swift marker, Qt attribute; the lanes may adjust marker spellings but not the set or order):

```python
TOOLBAR = (                                     # line 45: "mode" leads
  ("mode", 'Picker("Mode"', "mode_switch"),
  ("imagery_preview", ...), ("scenery_filter", ...), ("search", ...), ("side_panel", ...),
)
MODE_PANES = (                                  # new
  ("build", "BuildPane(", "build_pane"),
  ("fly", "FlyPane(", "fly_pane"),
  ("library", "LibraryPane(", "library_pane"),
)
FLY_PANE = (                                    # new, top to bottom
  ("fly_offer", "FlyOfferBanner(", "fly_offer"),          # shown in Build/Library
  ("plan_source", 'Picker("Flight plan"', "plan_source_combo"),
  ("simbrief", "SimBriefRow(", "simbrief_row"),
  ("open_plan", 'Button("Open plan file…")', "open_plan_btn"),
  ("flight_card", "FlightCard(", "flight_card"),
  ("build_alternate", 'Toggle("Also build the alternate"', "chk_build_alternate"),
  ("cruise_speed", "CruiseSpeedField(", "cruise_speed_edit"),
  ("corridor", "CorridorWidthField(", "corridor_edit"),
  ("readiness", "ReadinessChecklist(", "readiness_list"),
  ("countdown", "FlightCountdown(", "countdown_label"),
  ("world_line", "WorldStatusLine(", "world_line"),
  ("follow_line", "ImageryFollowLine(model:", "follow_line"),   # moves here from BuildPane
  ("sim_priority", 'Picker("While flying"', "sim_priority_combo"),
  ("live_preview", 'Toggle("Live flight preview"', "chk_live_preview"),   # #2001
  ("divert", 'Button("Divert…")', "divert_btn"),
  ("end_flight", 'Button("End flight")', "end_flight_btn"),
)
LIBRARY_PANE = (                                # new, top to bottom
  ("tiles", "LibraryTilesSection(", "tiles_box"),
  ("world_regions", "WorldRegionsSection(", "regions_box"),      # 10e (3)
  ("storage", "StorageSection(", "storage"),                     # from Settings
  ("pack_health", "PackHealthSection(", "pack_health_box"),
  ("patch_library", "PatchLibrarySection()", "patch_box"),       # existing row, new owner
  ("convert", "ConvertTilesSection(", "convert_box"),            # §13
)
```

Existing rows whose owner changes in the same PR: `IMAGERY_ON_DEMAND` (:103) `follow_line` (BuildPane → FlyPane), `library_pin`, `library_menu`, `make_low_res` (LibraryView / StorageSettingsView → LibraryPane); `PATCH_LIBRARY` (:89) `library_section`, `publish`. `BUILD_BOX` (:59) keeps `auto_install` and `skip_built` as rows that are hidden while on-demand is on (lregions).

Map layers in Fly: route and corridor, tile kind and job state (building, staged, margin), the aircraft with its track, the first window outline while preparing. The words "placeholder", "drape", "light" do not reach the user: the map legend says "X-Plane's own scenery", "photo, quick", "built", "building".

Notifications: neither app posts system notifications today (no `UNUserNotification` or tray use in the sources). Mac: `UNUserNotificationCenter`; Qt: `QSystemTrayIcon.showMessage`. One `FlightNotice` is one notification.

The existing "Select from flight plan…" (Build mode, #829) stays as it is; its Swift reader (`FlightPlan.swift`) is not extended. The flight manager reads plans in the engine only.

## 15. Test plan

All offline, headless, `tmp_path`; no test touches the real Custom Scenery (#1999 guard).

| Twin | Proves | Fixture |
|---|---|---|
| Window tracker | every World-pack `.dsf` open burst of the CYYR flight is predicted within 0.02° and no entry is predicted without one; the mirrored (eastbound, northbound) run of the same track gives mirrored entries | a compact extract of `flight_world.jsonl` (positions + `.dsf` opens, a few hundred kB) under `tests/fixtures/world/`; the 72 MB file stays in the data repo. `tools/imagery_tier_replay.py extract` already reads recorder logs and gains the `.dsf` opens |
| Log witness | the nine World-pack lines of §2.1/§2.3 parse to tile, pack, tris, sim time; placeholder vs real | lines copied from the owner's `Log.txt` |
| Schedule (pure) | feasibility, countdown, laxity guard, shedding order on hand cases | none |
| **Flight replay** | the job driven by the recorded positions, a fake builder with table durations and a fake clock: `+53-064` at 397 s finishes 245 s before its column (as flown: swapped 15:02:24, opened 15:06:29); no swap of a loaded tile; countdown never rises without a cause; the same flight at 2× and 3× speed shows where light tiles stop keeping up | new `tools/flight_schedule_replay.py` (INDEX row and twin in the same commit) over the same extract |
| Swap rules | S1–S5, S7 on a `tmp_path` pack: refusal for a loaded tile, merge swap never removes a name, swap-out | none |
| Binary definition rewrite | equals the DSFTool round trip on three tiles (definition list, MD5 footer, `verify_tile` clean) | three small DSFs (`tools/fixtures/make_mesh_dsf_fixture.py`) |
| Plan readers | alternate, times, speeds; `flight_plans_list` on a folder of `.fms` | existing `tests/fixtures/flight_plan/` plus one real, anonymised SimBrief OFP |
| Budget | pre-check verdicts; the intermediate tier evicts oldest first and never a `full` tile or a favorite | none |
| Wire | every new event's fields decode in Swift from the JSON the Python class emits (one shared fixture file, as `flight_plan_cases.json` is shared); capability flags | `tests/test_engine_capabilities.py`, `swift test` |
| Layout | §14's manifest | `test_qt_layout_parity.py` |

Registry twins every lane brief names (they walk the tree and `blast.py` does not list them): `windows_text_io`, `patch_env_classification`, `tile_failures`, `console_encoding`; and the frozen engine's lazy imports for each new module.

**One owner flight per phase** (each with the recorder; the recording becomes the next phase's fixture):

| Phase | Flight | Pass |
|---|---|---|
| W1 | CYYR again, 40 min: one leg east, one north, one tile dropped in with NO placeholder (H4), follow job on | east and north entries where the tracker says; sharpening lands on a World tile; H4 answered |
| W2 | free flight, GA, 30 min, no plan | tiles ahead appear by themselves, no reload, no stutter noticed; `world_pack.log` margins all positive |
| F1 + U2 | a planned flight of about 45 min at turboprop speed from SimBrief, destination not built before | countdown within its stated range; destination graded and loaded with no reload; notifications arrive |
| F2 | the same route with a diversion to the alternate halfway | the diversion airport is ready or the one announced reload happens as S6 (b) says |
| M | one migrated region, any flight | migrated tiles draw as before; ini has one row for them |
| D | the ldrape A/B at 53°N 62°W (already written, `README_DRAPE.txt`) | its own a–g list |

No five-airport sweep and no harness airport build is part of any lane here; the departure and destination builds of the owner flights are the closing tests.

## 16. Lane plan

Opus lanes; effort per RULINGS 2026-10-20a. Wall-clock figures are estimates for one lane round including its tests, not builds. At most 8 lanes run; none of these needs a tile build before its owner flight. Every brief carries: "never raise the lane cap; delete your scratch builds when you report".

| Lane | Work | Effort | Needs | Wall-clock [estimate] |
|---|---|---|---|---|
| **W0** | `O4_World_Window` (tracker, route entries; fixes the east branch), `O4_XPlane_Log`, the fixture extract, both twins | high | lworld merged | 3–4 h |
| **W1** | World pack in the engine: land `O4_World_Pack` (+ binary rewrite, bulk placeholder writer), `world_commands` (`world_status`, `world_install`, `world_regions_set`, `world_tile_set`), stage/publish for every build, index fields + lander path, `position_feed`; Swift + Python wire for `WorldStatus`/`WorldReady`; the consumer census of §18 completed by grep before any consumer is edited | xhigh (layout change across consumers) | W0 interfaces frozen from this spec; lregions' table (stub until it lands) | 6–10 h |
| **F1a** | plan readers extended, `flight_plans_list`, flight record, `O4_Flight_Schedule` (pure) + twins | medium | nothing | 3–4 h |
| **U1** | the three modes in both apps (shell, panes swapped, Library and Storage moved, manifest rows); no flight logic | medium | nothing | 4–6 h |
| **W2** | `world_job` (track mode), deadline/class in the build queue, `profile` override, follow-job pause narrowed, governor, replay tool | high | W0, W1 | 5–8 h |
| **F1b** | `flight_manager` + `flight_commands`, readiness rows, countdown, budget pre-check, pre-fetch, `FlightStatus`/`FlightReady` on both sides | high | F1a, W2 (queue API), lfav merged | 5–8 h |
| **U2** | Fly pane and map layers in both apps on the frozen events of §5.3; `AircraftPosition`; #2001's checkbox home | medium | U1; can start on §5.3 fixtures before F1b lands | 4–6 h |
| **F2** | diversion, alternate, notices in both apps, S6 (b) | medium | F1b, U2 | 3–5 h |
| **M** | `world_migrate`, DSF unpack, Library ▸ Convert | medium | W1 flown, lrebuild merged | 4–6 h |
| **D** | whichever intermediate D1 chooses becomes the default; the other is deleted | medium | the ldrape flight | 2–4 h |
| **X** | Windows and Linux: held-file renames, `Log.txt` location, process detection (`_xplane_running` answers False on Windows, `imagery_convert.py:115-116`), junction-free layout check | medium | W2 | 4–6 h + a Windows flight |

Parallel waves: **1** W0, F1a, U1 (and W1 once W0's signatures are agreed) → **2** W1, W2 after it, U2 → **3** F1b → **4** F2, M, D, X. With the owner flights between waves this is about three working days of master time [estimate]. W1 and W2 share `imagery_follow.py` and the index; they run one after the other. U1 and lregions both touch the Build pane: U1 starts from lregions' branch or after it lands.

Per the two-round cap, a lane that misses twice goes to a Fable review, not a third Opus try.

## 17. Decision point D1: the intermediate kind

| | `light` (flown) | `drape` (committed, not flown) |
|---|---|---|
| Time per tile | 397 s cold [measured] | 15–37 s, download dominates [source] |
| Size | ~100 MB [measured] | ~39 MB at 512 px, DSF ~23 kB [source] |
| Keeps up at 450 kt | no, part of the corridor is built before departure (§8.3) | yes, one slot |
| Ground shape, water, roads, autogen, airports | ours at 90 m; no grading; default roads/autogen need the overlay step unless simHeaven is installed | X-Plane's own, all kept |
| Seam to a built tile | mesh to mesh | X-Plane's ground beside ours: a step is possible |
| Far view | reaches the horizon | Laminar: drapes are built near the aircraft and fade out [source: master, Supnik 2011] |
| Cost in the sim | a normal tile | a second fill of the ground, more VRAM, CPU when drapes rebuild [source] |
| Water under the photo in XP12 | ours | unknown |
| Sharpening by the follow job | works (`.ter`, measured) | needs the step-up opens of `.pol` textures confirmed on the flight's recording (U5) |

**The switch is the owner's read of the ldrape flight** (`README_DRAPE.txt` items a–g):
- all of a, b, c, e (photo out to 15–20 km or more) and f (fps within about 10 %) pass → `world_intermediate = drape`; `light` is deleted with its profile;
- e fails only at altitude (photo fades in the far view) but a–c, f pass → drape below a cruise altitude the flight gives, light above it: the one case where both stay, chosen per tile by the plan's altitude at that tile;
- a, c or f fails → `light`; the drape modules are deleted (refuted mechanisms are deleted, not kept gated).

Everything else in this spec is the same on both paths; only the job's `kind`, its estimate and its size change.

## 18. Consumer census (required before W1 edits any consumer, RULINGS 2026-08-30l)

The World pack is a new layout: one pack, many tiles, per-tile subfolders, and thousands of DSFs that are not built tiles. 39 engine modules join `textures`, `terrain` or `Earth nav data` to a folder by literal (grep, main). Ruled by class here from static reading; W1 completes the list by grep and seam-probes the scan rows before editing.

| Consumer class | Examples | Ruling |
|---|---|---|
| Build writers | `O4_DSF_Utils`, `O4_Tile_Utils`, `O4_Imagery_Utils`, `O4_Overlay_Utils` | unchanged: builds run in an ordinary build folder (§7.3) |
| On-demand index, lander, downgrade, cores, favorites | `O4_Imagery_OnDemand_Index`, `imagery_follow_land`, `imagery_downgrade`, `O4_Imagery_OnDemand_Cores` | read through the row's `textures_dir` / `terrain_dir` / `config_dir`; one resolver |
| Installed-scenery scans | engine `scan` (`session.py`), `O4_Custom_Scenery`, `O4_Tile_Info`; Swift `InstallationScanner.collectDSFTiles` (`InstallationScanner.swift:447`), `DSFReader` | a World-pack DSF is classified by its `sim/creation_agent`: placeholder = not a tile; drape/light/full = a tile of that kind. Without this the whole map reads as built. Both scanners, same PR |
| Mesh order and ini filing | `O4_Mesh_Order`, `O4_Scenery_Packs`, `O4_Scenery_Packs_Tidy` | the World pack is one ortho-group row; a placeholder never counts as a mesh; `hidden_by`/`hides` are per tile inside it |
| Per-tile checks | `O4_Imagery_Freshness`, `O4_Tile_Texture_Check`, staleness, `O4_Tile_Failures`, `O4_Stopped_Build` | take a tile view (DSF path, terrain dir, textures dir, record path) instead of a folder; `full` tiles only |
| Library actions | `o4_engine/library.py` (delete, links), `links_install` | delete = swap-out by §7.4; "install" does not apply to a World tile |
| Storage accounting | `storage.py`, `storage_installed.py`, `storage_redundant.py`, `plan_estimate.py` | the World pack is one store with a split by kind; hard links counted once (`O4_Disk_Usage.counted_once_bytes`) |
| Converter | `imagery_convert.py`, `O4_Imagery_OnDemand_Convert` | unchanged until M; M adds the world target |
| 3D preview, pack tools | `O4_Qt_Preview3D_*`, `O4_Qt_Pack_Optimise`, MSFS converters | `full` tiles through the tile view; no change for packs |
| Tile bundles | `tile_bundle/paths.py` | exports a World tile from its tile view; import publishes by §7.3 |

Emittable check: the layout is not a model, it has flown (H3).

### 18.1 Completed census (W1, 2026-11-10, branch `claude/lw1`)

Grep `["'](Earth nav data|textures|terrain)["']` over `src/`: 60 files; 20 are `auto_patch*` airport-pack readers and 1 is `Unused/`, leaving the **39** engine modules of the ruling above. Plus the non-literal consumers of installed tiles and the Swift scanners. Seam probe: the scanners run, old code (`c77d214ee`) against new, on one `tmp` Custom Scenery (World pack: 3 placeholders + 1 published tile; one `zOrtho4XP_` link).

| Consumer | Where | Reads a World tile? | W1 | Seam probe (old → new) |
|---|---|---|---|---|
| `O4_Custom_Scenery.pack_tiles`, `_terrain_probe` | :202, :282 | yes (map packs, mesh order, tidy) | CHANGED: a placeholder is no tile (head read only of DSFs ≤ 4 kB); a per-tile `terrain/<tile>/`, `textures/<tile>/` is probed | pack `landmark`, 4 tiles → `ortho`, 1 tile |
| `O4_Scenery_Links.iter_installed_tiles` (engine `scan`, `O4_Cfg_Migrations`) | :280 | yes | CHANGED: the World pack's real tiles are installed tiles | installed `[(46,8)]` → `[(45,7),(46,8)]` |
| `O4_Scenery_Links.install` (`links_install`, Qt Library) | :205 | yes | CHANGED: no link for a tile the World pack holds | — (twin) |
| `O4_Mesh_Order` (`_drawn_order`, `_our_name`) | :46 | yes | CHANGED: a World-pack tile is ours; a placeholder is an overlay, never a mesh | `checked` False → True |
| Swift `InstallationScanner.collectDSFTiles`, `terrainAndTextureProbe` | :447, :475 | yes | CHANGED, same rule as the engine (size from the listing already read) | old code fails the twin: 3 tiles, not `ortho` |
| Swift `DSFReader` (sample DSF) | | the sample | unchanged: the sample is now a real tile | |
| `O4_Imagery_OnDemand_Index` | :136 | yes | CHANGED: `textures_dir`/`terrain_dir`/`config_dir` columns (schema 3), one resolver `_tile_dir` behind `texture_path`; the manifest's `world_layout` restores them on rebuild; `.pol` `LOAD_CENTER`/`TEXTURE_NOWRAP` read | |
| `imagery_follow_land.TierLander` | :109 | yes | CHANGED: lands at `texture_path(row)`; the converter's output (written in the build folder) mirrored into the pack | |
| `imagery_downgrade`, `imagery_ondemand._serve_full` | `texture_path` | yes | unchanged code (resolver) | |
| `O4_Tile_Info`, engine `scan` built half, `library.py` :96, `O4_Qt_GUI` :2527–2572, `plan_estimate` :228 | build folder | no | unchanged: W1 keeps the build folder (§7.3 step 4 not done) | |
| `O4_Imagery_Freshness` :94/442/502, `O4_Stopped_Build`, staleness, `O4_Tile_Texture_Check` | build folder | no | unchanged; OPEN: after a landing in the pack the build folder's copy is the placeholder, so these need the tile view before the build folder goes | |
| Build writers: `O4_DSF_Utils`, `O4_Tile_Utils`, `O4_Imagery_Utils`, `O4_Overlay_Utils`, `O4_DDS_Cache`, `O4_Imagery_Prefetch`, `O4_Imagery_Fetch_Selfcheck`, `O4_Default_Terrain_Map`, `O4_File_Names`, `O4_Tile_Staging` | build folder | no | unchanged | |
| `O4_Scenery_Packs` (`EARTH_NAV_DATA`, `load_order`), `O4_Scenery_Packs_Tidy` | | the row | unchanged: one ortho-group row (`ini_install`); tidy files only unlisted packs | |
| `O4_Imagery_OnDemand_Budget.dsf_bytes` :73, `storage_installed` (`zOrtho4XP_` prefix) | | no | OPEN: the pack's DSF copies (~50 MB a tile, rewritten, not linked) are in no storage row | |
| `storage_redundant` :99 | pack roots | yes | unchanged (correct) | |
| `imagery_convert` :252, `O4_Imagery_OnDemand_Convert` | | no | unchanged until M (`_xplane_running` moved to `xplane_root.xplane_running`) | |
| `tile_bundle/paths.py` :87 | comment | no | unchanged; export of a World tile OPEN | |
| `build_airports.py` :111, `O4_MSFS_*`, `O4_Pool_Selfcheck`, 20 `auto_patch*` modules | airport / other packs | no (no `apt.dat` in the World pack) | unaffected | |
| False positives: `O4_Tile_Failures` :699, `O4_Imagery_OnDemand_Text`, `events.py`, `O4_Vector_Utils` (scope label), `O4_Qt_Preview3D_*`, `O4_Qt_Pack_Optimise`, `imagery_follow.py` (count keys) | | | none | |
| Swift `OrthoEngine.tileStates`, `BuildModel.refreshTileStatesLegacy` | `zOrtho4XP_` names | no | legacy fallback (engines without sessions); not reached | |

Deviation for the spec author: §5.5's `world_regions` key is not added. RULINGS 2026-11-10e (3) and 10k (Q5, "on-demand regions start as the regions that already hold the user's tiles") make the World regions the six `imagery_on_demand_<region>` switches lane `lregions` landed; `world_regions_set` writes those, so one setting cannot disagree with another.

## 19. Unknowns and their tests

| | Unknown | Test | Phase |
|---|---|---|---|
| U1 | H4: is a DSF with no placeholder picked up when its column loads? | drop one in on the W1 flight | W1 |
| U2 | The window eastbound, at other latitudes (X-Plane may hold more columns toward the poles), and the first-load B and R | recorder on every owner flight; the tracker twin gains each recording | W1 onward |
| U3 | Is `Log.txt` flushed within seconds in flight, on each OS? | tail it during the W1 flight and compare with the recorder's open times | W1, X |
| U4 | Time of a light build with warm caches, and of a `full` destination build beside X-Plane | the ledger after W2 and F1's flights (`sim_running` records) | W2, F1 |
| U5 | Do `.pol` textures step up by distance like `.ter` ones (drape sharpening)? | recorder on the drape flight | D |
| U6 | Stall length of a scenery reload with the World pack (loader U9 still open) | time it on the ground in F1's flight | F1 |
| U7 | SimBrief's real field names for times, speeds, alternate | one real OFP as fixture | F1a |
| U8 | Windows: rename over a DSF or folder X-Plane has open | phase X swap stress | X |
| U9 | X-Plane's share of cores for the automatic slot rule | frame-time governor's log on F1's flight | F1 |

## 20. Questions for the owner

- **Q1 Budget.** May tiles the app built by itself (never ones you built, never favorites) be given back, oldest-flown first, when the budget is full? Without it they only accumulate (§12).
- **Q2 Corridor.** Default width: the tiles the route crosses plus 20 km each side. Wider means a longer wait before departure with light tiles. Is narrow the right default?
- **Q3 Offline.** When some en-route tiles cannot be built for lack of internet, may the pilot choose "fly with X-Plane's own scenery there" for that flight? (Departure and destination could not be waived.)
- **Q4 Reload in the air.** For a destination or diversion airport that could not be in place in time: one reload, announced 30 s ahead with "Not now", and only asked near the ground. Or always ask?
- **Q5 Regions.** Start with no region chosen and ask on first use of Fly, or start with the regions that already hold your tiles?
- **Q6 Dispatch order.** The brief's order puts build-ahead above the destination. This spec keeps it for dispatch but never gives the destination up when something has to be dropped (§8.4). Confirm.

## 21. Sources not verified

SimBrief's OFP fields (U7); `Log.txt` flush timing (U3); the window outside the two recorded latitudes and westbound/one north–south pair (U2); H4 (U1); DSFTool on a 7z DSF (§13 assumes it cannot and unpacks first); Windows and Linux throughout (phase X); the CYXY flight-2 window figures (read from a code comment); the drape figures (from the master's message and `README_DRAPE.txt`, not flown); the region table (`lregions` had no code to read; counts here are the installed X-WORLD-Pro packs' DSF tiles, not simHeaven's documentation); the per-tile sizes of `full` tiles (memory note figures, not re-measured).
