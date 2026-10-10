# flaky510 — `KeyError: 'USGS3DEP'` on Windows CI (issue #510)

## Traceback (run 38072353582 attempt 1, windows-latest, gw1)

    tests\test_elevation_gap_census_providers.py:66: mod.main()
    tools\elevation_gap_census.py:537: providers_mode(args)
    tools\elevation_gap_census.py:481: ladder_would_deliver(r, args, INSETS)
    tools\elevation_gap_census.py:440:
        root = INSETS.elevation_providers_dict[args.ladder_root]
    KeyError: 'USGS3DEP'

## Mechanism (reproduced)

`O4_Airport_Elevation_Insets.elevation_providers_dict` is a module global.
`initialize_elevation_providers_dict(directory)` REBINDS it, and every reader
(the census tool's `_engine()` among them) fills it lazily with
`if not elevation_providers_dict: initialize()`. A twin that parses a scratch
`.elv` directory leaves a non-empty registry of its own fakes; the next lazy
reader on the same worker trusts it.

On the failing run gw1's last registry write before the census test was
`tests/test_arcgis_export_image.py::test_a_definition_without_nodata_is_refused_at_parse`
(`initialize_elevation_providers_dict(str(tmp_path))`). Run whole, that file
ends with `test_the_shipped_exportimage_providers_carry_nodata`, which
re-parses the shipped directory and hides the leak; `--dist loadgroup` cuts
files across workers, and on the Windows runner the cut sometimes fell
between the two.

Reproduce from `Ortho4XP/` (red before, green after):

    venv/bin/python -m pytest -q -p no:randomly -n0 \
      "tests/test_arcgis_export_image.py::test_a_definition_without_nodata_is_refused_at_parse" \
      tests/test_elevation_gap_census_providers.py

## Fix

`tests/provider_registry_isolation.py` (`snapshot` / `restore`) and an
autouse fixture in `tests/conftest.py` put the registry back after every
test: the object is rebound, its codes restored, each definition restored
one level deep. Same shape as the `O4_UI_Utils.verbosity` fixture (#76).
No engine or tool code changed.

Not covered: an in-place edit of a value NESTED inside a definition (a list
such as `coverage_bboxes`) is not restored.

## Twin

`tests/test_provider_registry_isolation.py`: a pinned pair (scratch parse,
then the census tool's lazy read) plus two direct tests of the helpers. With
the fixture's restore disabled the pair fails (1 failed, 3 passed).

## Measured

- named files (twin, census, windows_text_io, console_encoding,
  no_airport_specific_code): 204 passed
- full non-Qt split: 9226 passed, 19 skipped, 1 xfailed, 1 xpassed
- `tools/ratchets.py`: exit 0

# Addendum — is it a Windows defect of the app? (owner: Beta 2 blocker)

## The CI failure is test-only

Reproduced on macOS with one worker (sequence above); the registry on the
failing worker was a scratch directory's, written by another test. Nothing
Windows-specific is in that path except where the scheduler cut the file.

## The frozen app's registry path

- Lazy, never at import: every reader runs `if not elevation_providers_dict:
  initialize_elevation_providers_dict()`.
- Directory: `FNAMES.Provider_dir = resource_path("Providers")`; frozen, that
  is `sys._MEIPASS/Ortho4XP_Data/Providers` — absolute, no cwd, no glob, no
  case folding; `sorted(os.listdir())`. Both specs bundle `./Providers`.
- A spawned pool worker re-imports the module with an empty registry and
  parses the same absolute directory on first use. Reads only; no shared
  state, so no race and no partial registry from spawn.

## A real defect found on the way (fixed)

The parser opened each `.elv` with the machine's default text encoding and
"skipped" a file it could not read. 19 shipped files carry UTF-8 non-ASCII
(7 of them in `attribution=` values). Measured by decoding the shipped files:

| ANSI code page | files that do not decode (provider dropped) |
|---|---|
| cp1252 | 0 (attributions garbled: the dash reads as three characters) |
| cp1250/1253/1254/1255/1257/1258/874 | 1 (TAIWAN20M) |
| cp932/936/949/950 | 9: AKHAINES AKHOMER CORALATLAS CWCB1M CWCB7V2LAS PITKIN1M PORTUGALTIDAL TAIWAN20M WADNR |

`USGS3DEP.elv` itself is ASCII and always parsed; what left the ladder on a
double-byte Windows were rungs it names (PITKIN1M) and ladder members.
Fix: the read names `ELV_ENCODING = "utf-8-sig"`.

## Release checks

None of PROJ / LERC / `--import-selfcheck` / `--pool-selfcheck` / tile smoke
read the provider files' count, and the runners are cp1252, where nothing is
dropped. `--import-selfcheck` (already run on all three frozen legs) now
prints a third line from `provider_registry_selfcheck()`: every `.elv` in
the bundle is in the registry, every `provider:` rung resolves, every
non-ASCII value is the file's UTF-8 text. No workflow edit needed.

Twin: `tests/test_provider_registry_selfcheck.py` (10 tests; 8 fail with the
`encoding=` removed).

Not done: the imagery provider reader (`O4_Imagery_Utils`) has the same
unnamed-encoding read; one shipped file (`Providers/Albania/AL.lay`) is
non-ASCII. `Providers/Sweden/.SE.lay.swp` is a stray editor swap file.
