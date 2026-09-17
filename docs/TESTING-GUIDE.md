<!-- DRAFT (session, 2026-09-17) for the owner to edit. Not rendered. -->
# XPTerrainBuilder beta — testing guide

Thank you for testing. This guide gets you from a download to a useful bug
report in one sitting. The release notes for your build
(`docs/RELEASE_NOTES-<version>.md`, also the text of the GitHub release) cover
installation per platform; this guide covers **what to do, what to look at,
and what to send back**.

## What we need from you

In order of value:

1. **Airport terrain that looks wrong in the sim.** This is the point of the
   beta. The app regrades runways, taxiways and aprons to real slope limits
   and stands scenery objects on the result. We need eyes on airports we have
   never looked at — especially ones **with custom scenery packs**, on
   **hilly ground**, **by the sea**, or with **tunnels, underpasses or
   bridges**.
2. **Builds that fail or stall**, with the log.
3. **Windows and Linux app problems.** Nobody but the author has run those
   apps yet: layout glitches, clipped text, dialogs that do not fit, anything
   that behaves differently from what the screen says.
4. Installation friction: a step in the notes that was wrong or missing.

We do **not** need reports about imagery quality, colour matching between
providers, or provider outages — those come from the imagery services.

## Before you start

- **X-Plane 12**, and enough disk: **3–8 GB per tile** at the default zoom
  level 16, plus several GB of shared cache. Use a drive with room.
- **Protect your scenery.** To stand a custom airport's objects on the new
  ground, a build rewrites object placements **inside that scenery pack**
  under `Custom Scenery`. Originals are kept beside them as `.anchor_bak`
  and restored before every rebuild — but for a beta, test on an X-Plane
  install (or a copy of `Custom Scenery`) you can restore.
- **Restart X-Plane after every build.** It caches scenery objects.
- Decide your test airport first. Best: one you know well on the ground,
  small or mid-sized, in a tile you have not built before.

## Your first build, step by step

1. **Launch** the app (per-platform steps are in the release notes; on macOS
   there should be no security dialog at all).
2. **Data folder.** Accept `~/XPTerrainBuilderData` or pick a folder on a
   roomy drive. Everything the app writes lives there.
3. **X-Plane folder.** Point it at your X-Plane 12 installation. The app
   checks for `Custom Scenery` and `Resources/default data/CIFP` and tells
   you what is missing. It will not build without a valid folder — that is
   deliberate.
4. **Pick one tile** on the map: the 1°×1° square containing your airport.
   Airports are marked; custom-scenery airports are marked differently.
5. **Imagery provider.** Pick any that covers the area; some need a free
   account (Settings ▸ providers). Leave zoom level at 16 for the first run.
6. **Build.** Leave the options at their defaults. Watch the Activity box and
   the console pane.

**What a healthy build looks like** (times measured on the author's Apple
Silicon Mac with warm caches; your first build also downloads data and will
be slower):

| Step | Typical | Slow case |
| --- | --- | --- |
| Vector data + **airports** | 3 min | 13 min for a tile with a large hub |
| Mesh | 30 s | 2–3 min |
| Masks | 15 s | 1 min |
| Imagery + DSF | 40 s cached | many minutes on first download |

During the airport stage the console names each airport and its step
(`[0/100] Loading…` → `[40/100] Classifying…` → `[65/100] Solving the
surface` → `[95/100] Emitting…`). A large hub sits in *Solving* for several
minutes; that is normal. **0 % CPU for minutes is not normal** — on macOS it
usually means a permission prompt for a removable drive is waiting behind a
window.

7. **Install.** With "auto-install finished tiles" on, the tile appears in
   `Custom Scenery` as `zOrtho4XP_<tile>`. Otherwise install it from the app.
8. **Restart X-Plane**, load at your airport, and look.

## What to look at in the sim

Taxi the whole field if you can; a slow low pass works for the rest. Look
from the cockpit — what a pilot would see is the acceptance test.

- **Runways:** a smooth profile end to end, a gentle crown, no steps or
  sudden ramps, no sag in the middle. A runway on genuinely sloping ground
  should still slope.
- **Taxiways and junctions:** no kinks where two taxiways meet, no sharp
  ramps onto the runway, no "roller-coaster" along a long taxiway.
- **Aprons:** broadly flat where aircraft park, no ridges or pits, no step
  where the apron meets a taxiway or a building.
- **Edges of the pavement:** the ground beside it should blend away. Report
  **walls, cliffs, spikes, pyramid-shaped mounds or deep pits** beside
  taxiways and around the airport boundary.
- **Objects from scenery packs:** buildings, jetways, fences, light poles
  and vehicles should stand on the ground — not float, not sink, not sit on
  a visible pedestal. Check terminals with basements or underground roads.
- **Tunnels, underpasses, bridges:** road tunnels under taxiways should be
  open with walls; bridges should carry their deck at the right height.
- **Water:** shorelines beside the airport should be water at sea level, with
  no terrain rising out of the sea and no pavement under water.
- **Roads** crossing or skirting the field: no steps where a road meets
  pavement.
- **Tile seams:** if you build two neighbouring tiles, fly the join and look
  for a crack or a step.

A defect is worth reporting even if small. Equally useful: "I checked the
whole of XXXX and it looks right."

## How to report

Open an issue at <https://github.com/shizumaat/XPTerrainBuilder/issues>, one
issue per airport or per problem, with:

1. **The version triple** — the three lines of `VERSION.txt` from your
   download (`app=`, `engine=`, `sha=`), also shown in the About box.
2. **Platform** and OS version.
3. **Airport ICAO**, the tile, the imagery provider and zoom level, and the
   **scenery pack** the airport comes from (name and version), or "default
   Global Airports".
4. **Screenshots from the sim** with the position: latitude/longitude if you
   can (X-Plane's data output or the map), otherwise taxiway/stand names and
   which way you are looking. One wide shot and one close shot beat ten
   close ones.
5. **The log**:
   - macOS: `~/Library/Logs/XPTerrainBuilder/engine-stderr.log`
   - Windows / Linux: `<data folder>/logs/engine-stderr.log`
   - and the console pane, copied (it has a copy button).
6. For a failed build, the **exact line** the app printed, e.g.
   `*** Tile +30+031: airport HECA failed at the verify stage — …`.

If the app would not start a build, say what the Build button's tooltip
said — it states the reason.

## Things that are expected (not bugs)

- An airport the app declines to grade is **skipped with a line saying
  why** (for example, no airport layout exists for it in your X-Plane
  install). The tile still builds.
- The same airport built on macOS, Windows and Linux differs slightly. Tell
  us your platform; do not file the difference itself.
- A scenery pack you **disabled in X-Plane is ignored**: its airport is
  graded from the next enabled pack or from Global Airports and shows a
  gray mark on the map. If an airport looks like it was built from the
  wrong pack, tell us which packs you have for it and which are enabled.
- Windows shows a SmartScreen warning (the app is not code-signed yet);
  Linux needs the listed apt packages; macOS is Apple Silicon only.

## Going further, if you have time

- An airport with a **third-party scenery pack** versus the same airport on
  default scenery.
- A **large hub** (expect a long airport stage) and a **grass or gravel
  strip**.
- **Stop** a tile mid-build and **resume** it.
- Build with **no network** after a first successful build: it should
  complete from cache, or say plainly what it could not fetch.
- Change the data folder in Settings, quit, relaunch: it should remember.
- On Windows and Linux: open every Settings category and the first-run
  wizard on your smallest screen and tell us what does not fit.

## Undoing a build

- Remove the tile: delete `Custom Scenery/zOrtho4XP_<tile>`.
- Restore a scenery pack: inside the pack, each rewritten file has its
  original beside it as `<name>.anchor_bak`; a rebuild restores them
  automatically, and deleting the tile does not. If in doubt, reinstall the
  pack.
- Remove everything the app wrote: delete the data folder and
  `~/.ortho4xp`.
