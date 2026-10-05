"""NO AIRPORT-SPECIFIC CODE — the standing twin of owner RULINGS 2026-10-05e.

"We must always build general rules that work at all airports as we fix
issues with particular test cases."  An airport is a TEST CASE: it shows a
defect, and the fix is a rule every airport is read by.  Nothing in the
engine or the app may ask which airport it is building.

Three readings, all static, all in milliseconds:

  * no string literal in `Ortho4XP/src/**.py` IS an airport code (a
    comment or a docstring may name the airport a rule was found at — the
    tokenizer reads literals, and a docstring is never exactly four
    characters);
  * no string literal in `Sources/**.swift` is one either;
  * no law table (`**/law/*.toml`) carries a table or a key named for an
    airport, EXCEPT the recorded affordances in `RECORDED` below.

THE RECORDED SET MAY FALL, NEVER RISE — AND IT IS EMPTY.  It held the one
affordance that existed when the rule was written, `law/airports.toml
[OTHH] kerb_wall_corridors` (RULINGS 2026-09-10ap); owner RULINGS
2026-10-05g replaced it by a general rule every airport is read by (ramps
spec §12h) and the table is deleted.  Adding a row here is an owner ruling,
cited beside it.

The airport codes are every ICAO the campaign has a registered frame for
(`docs/frames.jsonl`) plus the sweep set — the airports a lane is tempted
to name.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import tokenize
import tomllib

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "Ortho4XP" / "src"
SWIFT = REPO / "Sources"
SWEEP = {"CYXY", "SPJC", "KCLT", "KASE", "HECA", "NLWF", "OTHH", "LEMD"}

# (law file relative to src, airport table, key): the recorded affordances.
# May fall, never rise (owner RULINGS 2026-10-05e) — empty since 2026-10-05g.
RECORDED: set[tuple[str, str, str]] = set()

_CODE = re.compile(r"[A-Z][A-Z0-9]{3}")


def _rel(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def airport_codes() -> set[str]:
    codes = set(SWEEP)
    frames = REPO / "docs" / "frames.jsonl"
    if frames.is_file():
        with frames.open(encoding="utf-8") as f:
            for line in f:
                try:
                    icao = json.loads(line).get("icao")
                except ValueError:
                    continue
                if isinstance(icao, str) and _CODE.fullmatch(icao):
                    codes.add(icao)
    return codes


def python_literals(root: pathlib.Path, codes: set[str]) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.py")):
        with tokenize.open(path) as f:
            for tok in tokenize.generate_tokens(f.readline):
                if tok.type != tokenize.STRING:
                    continue
                try:
                    value = ast.literal_eval(tok.string)
                except (ValueError, SyntaxError):
                    continue        # an f-string or a bytes prefix
                if isinstance(value, str) and value.upper() in codes:
                    found.append(f"{_rel(path)}:{tok.start[0]}: {value!r}")
    return found


def swift_literals(root: pathlib.Path, codes: set[str]) -> list[str]:
    found = []
    quoted = re.compile(r'"([A-Za-z][A-Za-z0-9]{3})"')
    for path in sorted(root.rglob("*.swift")):
        text = path.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("//", 1)[0]
            for m in quoted.finditer(code):
                if m.group(1).upper() in codes:
                    found.append(f"{_rel(path)}:{n}: {m.group(1)!r}")
    return found


def law_affordances(root: pathlib.Path, codes: set[str]) -> set[tuple[str, str, str]]:
    """Every (file, airport, key) a law table names an airport for —
    as a table (`[OTHH]`) or as a key anywhere in the file."""
    named = set()

    def walk(rel, node, airport):
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            here = key.upper() if isinstance(key, str) else ""
            if here in codes:
                if isinstance(value, dict) and value:
                    for sub in value:
                        named.add((rel, here, str(sub)))
                else:
                    named.add((rel, here, ""))
                walk(rel, value, here)
            else:
                walk(rel, value, airport)

    for path in sorted(root.rglob("law/*.toml")):
        with path.open("rb") as f:
            walk(path.relative_to(root).as_posix(), tomllib.load(f), "")
    return named


def test_the_code_list_is_not_vacuous():
    codes = airport_codes()
    assert SWEEP <= codes and len(codes) >= len(SWEEP)


def test_no_python_literal_names_an_airport():
    assert python_literals(SRC, airport_codes()) == []


def test_no_swift_literal_names_an_airport():
    assert swift_literals(SWIFT, airport_codes()) == []


def test_the_law_names_no_airport_beyond_the_recorded_set():
    named = law_affordances(SRC, airport_codes())
    assert named <= RECORDED, (
        "a law table names an airport — build the general rule instead "
        f"(owner RULINGS 2026-10-05e): {sorted(named - RECORDED)}")


def test_the_recorded_set_is_not_stale():
    """A recorded affordance that is gone must leave RECORDED too, so the
    set only ever falls."""
    assert RECORDED <= law_affordances(SRC, airport_codes())


def test_the_readers_see_an_offence(tmp_path):
    """Positive control: each reader flags what it exists to flag."""
    codes = {"OTHH", "HECA"}
    (tmp_path / "law").mkdir()
    (tmp_path / "m.py").write_text(
        '"""found at OTHH"""\n# HECA\nif icao == "HECA":\n    pass\n',
        encoding="utf-8", newline="\n")
    (tmp_path / "law" / "x.toml").write_text(
        "[heca]\nflat = true\n[basin]\nOTHH = 2\n",
        encoding="utf-8", newline="\n")
    (tmp_path / "a.swift").write_text(
        '// "OTHH"\nlet a = icao == "OTHH"\n',
        encoding="utf-8", newline="\n")
    assert [s.split(": ")[-1] for s in python_literals(tmp_path, codes)] == ["'HECA'"]
    assert [s.split(": ")[-1] for s in swift_literals(tmp_path, codes)] == ["'OTHH'"]
    assert law_affordances(tmp_path, codes) == {
        ("law/x.toml", "HECA", "flat"), ("law/x.toml", "OTHH", "")}
