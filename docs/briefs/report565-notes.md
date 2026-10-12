# report565 — failure report, engine half (issue #565, RULINGS 2026-10-12b / 12a (3))

## RESUME HERE

State 2026-10-12: engine half BUILT and twinned on `claude/report565`.
Left for the master: the two buttons (mac + Qt), the protocol bump in
`events.py`, the Swift client method. Nothing else is open in this lane.

## Design

Two modules in `Ortho4XP/src/o4_engine/` (stdlib only), one shell tool:

- `redaction.py` — `Redactor`: THE rules, one place. `Redactor.for_this_machine(roots)`
  knows the home folder, login, full name and host name.
- `failure_report.py` — `build_report(...) -> FailureReport(title, text, issue_body,
  issue_url, file_name)`, `write_report_file`, `log_excerpt`, and the engine command
  `failure_report(...)`. Everything from outside is redacted at the door, before it is
  cut to length; each rendering is redacted again on the way out (the rules are idempotent,
  twinned).
- `Ortho4XP/tools/failure_report.py` — the same from a shell (INDEX row, "Audits").

A failure is PLAIN DATA: `{"code","what","why","remedy","airports","detail"}` — the
entries of `BuildDone.failures` / `BuildDone.warnings` of #562 go back in unchanged.
Nothing of lane failmsg562 is imported. With no failure given (the shell tool on an old
log) the failure is read from the log's `Auto-patch: FAILED X (stage): detail` lines and
coded `unclassified`.

Log excerpt: the tile's LAST run = lines after the last `=== ... ===` header naming the
tile; only ITS `[+LAT+LON]` lines; blank and rule lines dropped. File: last 400 lines +
every `[provenance]` line once. Issue: the last 8 error lines + the last 30 quiet lines
(no progress ticks, no provenance), then fitted.

## Redaction rules (what leaves is checked against these)

1. Home + user: `/Users/<n>`, `/home/<n>`, `/root`, `X:\Users\<n>`, `X:\Documents and
   Settings\<n>`, `~` -> `<home>`; the names seen there and the declared ones (login, full
   name) -> `<user>` as a word anywhere; declared host -> `<host>`.
2. Paths: under a DECLARED root (data root, engine resources, X-Plane folder) the root
   becomes `<data>` / `<engine>` / `<xplane>` and the rest is kept. Undeclared: kept from the
   first folder that X-Plane or the engine names its own (`Custom Scenery`, `Global Scenery`,
   `OSM_data`, `Elevation_data`, `Orthophotos`, `Geotiffs`, `Masks`, `Patches`, `Tiles`,
   `Previews`, `Airport_mod_cache`, `Default_DSF_cache`, `yOrtho4XP_Overlays`). Any other
   absolute path (POSIX, drive, UNC, `file://`) -> `<path>/<last component>`.
3. Proxies: the value of anything named `*proxy*`, and every URL on a line that names a
   proxy -> `<proxy>`.
4. Credentials: URL `user:pass@`, secret-named query values (`key`, `apikey`, `token`,
   `sig`, ...), `Bearer`/`Basic` tokens, `password=`/`token=`/`api_key:` assignments ->
   `<redacted>`.
5. E-mail addresses -> `<email>`.

KEPT, said in the report header: scenery pack names, airport names, tile names, coordinates.
Ambiguity is resolved toward removal (a path with spaces has no certain end).

## URL cap — MEASURED on github.com, 2026-10-12, signed out, curl, filler bodies

| URL length | answer |
|---|---|
| 6,081 … 7,021 | 302 to sign-in, `return_to` carries the whole URL |
| 7,041 … 7,981 | HTTP 500 |
| 8,281 and above | HTTP 414 |

Second limit: the sign-in redirect re-encodes the URL (`%0A` -> `%250A`, 3 -> 5 chars).
A redirect of 7,642 chars is kept; at 7,892 GitHub answers a bare `/login` (24 chars) and
the prefill is LOST after sign-in. Enforced: `MAX_ISSUE_URL = 6800`,
`MAX_LOGIN_REDIRECT = 7500` (model `len(prefix) + len(quote(url, safe="-._~"))`, checked
against a real Location header in the twin). Spaces go as `+`, and `/ : , ( ) ! *` raw —
accepted by GitHub (302 with the prefill intact) and cheapest under the re-encoding.
Worked examples: 5,213 / 5,211 chars (redirect 7,482 / 7,424): the redirect limit binds.
NOT measured: a signed-in browser (no account in a lane); the 500 at 7,041 may or may not
apply there — the cap is under it either way.

## Wire shape

DONE (in `jsonl.py`, which failmsg562 does not touch — its tree edits events/session/parallel):

    -> {"cmd": "failure_report", "id": N, "lat": 45, "lon": -123,
        "failures": [...BuildDone.failures or .warnings entries...],   default []
        "airports": ["KPDX"],        default: the failures' own
        "app_version": "1.0.387",    default: read from the log's run header
        "app_name": "mac" | "qt",    default ""
        "log_path": "...",           default <data root>/logs/engine-stderr.log (the Qt log);
                                     the mac app passes ~/Library/Logs/XPTerrainBuilder/engine-stderr.log
        "xplane_dir": "...",         default ""
        "save_path": ""}             a file or folder; empty writes nothing
    <- {"reply": N, "ok": true, "result": {"title", "report", "issue_url", "issue_body",
        "file_name", "saved_path", "url_length"}}

Synchronous reply, no event class. `tile: "+45-123"` is accepted instead of lat/lon.
"Report this problem": call without `save_path`, show `report`, open `issue_url`.
"Save report file": call with `save_path` (save panel default name = `file_name`).

REQUESTED of the master / failmsg562 (their files):
- `events.py`: `PROTOCOL_VERSION` comment + bump (1.11 after failmsg562's 1.10, or folded
  into 1.10) so a front end shows the buttons only when the engine has the command. An
  older engine answers `unknown command`.
- `Sources/SceneryKit/OrthoEngineClient.swift`: a `failureReport(...)` request; Qt can call
  `o4_engine.failure_report.failure_report(...)` in process.

## Worked examples (real log, redacted) — `docs/briefs/report565-examples/`

- `report-+45-123.txt`, `issue-+45-123.txt` — KPDX (#559)
- `report-+47-123.txt`, `issue-+47-123.txt` — six airports, stale DSF dump (#560)

Made with `venv/bin/python tools/failure_report.py --tile T --url --out FILE` on
`~/Library/Logs/XPTerrainBuilder/engine-stderr.log`.
