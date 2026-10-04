# Ortho4XP/src — find it before you write it

The owner's priority is REUSE: small one-responsibility modules, and no
second implementation of a thing that exists (RULINGS 2026-10-04a/c).
The module list is GENERATED — never keep one by hand, here or in a brief.

## Before adding a function, a class or a module

Run from `Ortho4XP/` (paths print relative to it):

    venv/bin/python ../tools/blast.py --find <keyword> [<keyword>…]   # does it exist? name(args), file:line
    venv/bin/python ../tools/blast.py --map <package>                 # one line per module of the package
    venv/bin/python ../tools/blast.py --map                           # one line per package
    venv/bin/python ../tools/blast.py <file>                          # before EDITING: importers, tests, hazards

`--find` matches names and first docstring lines, private helpers
included: three `_ring_area` variants are the answer "extend one", not
"add a fourth". An empty answer says so in words.

The map is only as good as its inputs: every module opens with a
docstring whose FIRST line says what the module owns, and declares
`__all__`. A name shows in the map when another module uses it; export
what others need and nothing else.

## Where new code goes

- `auto_patch_v2/` is the airport engine. Its packages are LAYERED,
  bottom first — a package imports only the packages to its left:

      geom < law < model < airport < classify < planar < constraints < solve < emit < verify < pipeline

  `geom` (pure geometry), `law` (the law as data) and `model` (dataclasses)
  import nothing above them — a helper two packages need goes DOWN into
  one of these, never sideways. `pipeline` alone orchestrates. `../tools/ratchets.py layers` prints the import matrix
  and gates it: recorded upward imports may fall, never rise.
- A FAMILY (elevation providers, constraint builders, emit adapters, law
  tables) is a package with a base interface, a registry and one module
  per member. A new member is a NEW FILE in that package, never an append
  to a sibling.
- Reporting that production never calls (why / explain / census reads)
  lives in `Ortho4XP/tools`, not in the engine package.
- `auto_patch/` is the retired v1 engine's kept remainder (tile driver,
  readers, object stage): fix in place, add nothing new.
- Top-level `O4_*.py` is the tile-build core. A new responsibility is a
  new module; a file already past 1,000 lines does not take it.

## At the end

`venv/bin/python ../tools/ratchets.py` — identical-body duplicates and
upward imports are GATES; size and long functions are a report (1,000
lines is a guide and a warning: split by responsibility, never to make a
number). Report net lines and new public symbols.
