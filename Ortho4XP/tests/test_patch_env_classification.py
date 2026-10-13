"""Every ``O4_`` environment variable is classified (issue #607).

``auto_patch.provenance_env`` holds the one table of the variables the patch
stamp ``o4_cfg`` never reads (who runs the build, how it is scheduled, where
it logs and keeps scratch) and of the settings read outside ``config.py``.
The app's process id was in neither — nothing made anyone decide — so it was
hashed into every patch and every airport rebuilt after each app launch.

This twin walks the source the engine, the app, the harness and the release
scripts are made of, collects every ``O4_`` name spelled as a variable, and
fails on one that is in no class.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ORTHO = Path(__file__).resolve().parents[1]
REPO = ORTHO.parent
sys.path.insert(0, str(ORTHO / "src"))

from auto_patch import provenance, provenance_env  # noqa: E402

#: Where an ``O4_`` variable can be read or set.
SCANNED = (ORTHO / "src", ORTHO / "tools" / "harness", ORTHO / "Ortho4XP.py",
           ORTHO / "Ortho4XP_Qt.py", ORTHO / "tests" / "conftest.py",
           REPO / "Sources", REPO / "scripts")
SUFFIXES = (".py", ".swift", ".sh")

#: A variable is a quoted all-capitals literal (``"O4_X"``: Python, Swift)
#: or a shell expansion / assignment (``$O4_X``, ``${O4_X:-…}``, ``O4_X=``).
#: A module (``O4_UI_Utils``) or a retired gate named in a comment is not.
_VARIABLE = re.compile(
    r"""["'](O4_[A-Z][A-Z0-9_]*[A-Z0-9])["']"""
    r"""|\$\{?(O4_[A-Z][A-Z0-9_]*[A-Z0-9])"""
    r"""|\b(O4_[A-Z][A-Z0-9_]*[A-Z0-9])=""")

#: Quoted ``O4_`` literals that are not environment variables.
NOT_VARIABLES = {
    "O4_NAME", "O4_X",               # the gate-regex's own doc examples
    # raster metadata keys (``elevation_access.vertical_units``)
    "O4_VERTICAL_UNIT_SOURCE", "O4_VERTICAL_UNIT_DECLARED",
    "O4_VERTICAL_UNIT_APPLIED",
}


def _spelled() -> dict[str, str]:
    """``name -> first file that spells it``, over :data:`SCANNED`."""
    found: dict[str, str] = {}
    for root in SCANNED:
        paths = [root] if root.is_file() else sorted(
            p for p in root.rglob("*") if p.suffix in SUFFIXES)
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in _VARIABLE.finditer(text):
                name = next(g for g in match.groups() if g)
                found.setdefault(name, str(path.relative_to(REPO)))
    return found


def test_the_scan_sees_the_variables_that_caused_607():
    spelled = _spelled()
    assert len(spelled) > 150, "the source walk collapsed"
    for name in ("O4_PARENT_PROCESS_ID", "O4_PARALLEL_BUILD_SIBLINGS",
                 "O4_INSET_SCRATCH_DIR", "O4_AUTO_PATCH_STRICT"):
        assert name in spelled
        assert name in provenance_env.RUN_ENVIRONMENT


def test_every_variable_the_source_spells_is_classified():
    gates = set(provenance.introspect_config_gates())
    assert len(gates) > 100, "gate introspection collapsed"
    homeless = {
        name: where for name, where in _spelled().items()
        if name not in gates
        and name not in provenance_env.RUN_ENVIRONMENT
        and name not in provenance_env.SETTINGS_OUTSIDE_CONFIG
        and name not in NOT_VARIABLES}
    assert not homeless, (
        "O4_ variables in no class.  Each is hashed into every patch's "
        "o4_cfg stamp until someone decides: add it to provenance_env."
        "RUN_ENVIRONMENT (it identifies or steers the RUN and cannot change "
        "a patch — say why) or to SETTINGS_OUTSIDE_CONFIG (a change to it "
        f"must rebuild): {homeless}")


def test_the_two_tables_are_disjoint_and_name_only_live_variables():
    run = set(provenance_env.RUN_ENVIRONMENT)
    settings = set(provenance_env.SETTINGS_OUTSIDE_CONFIG)
    assert not run & settings
    spelled = set(_spelled())
    # O4_FORCE_APT_DAT is argued in the digest's own docstring and read by
    # tools outside the walk; every other entry must still be spelled.
    gone = (run | settings) - spelled - {"O4_FORCE_APT_DAT"}
    assert not gone, f"classified but no longer in the source: {sorted(gone)}"
    assert all(why.strip() for why in provenance_env.RUN_ENVIRONMENT.values())


@pytest.mark.parametrize("name", sorted(provenance_env.RUN_ENVIRONMENT))
def test_a_run_variable_never_moves_the_digest(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
    unset = provenance.config_digest()
    for value in ("1", "0", "4711", "/tmp/elsewhere"):
        monkeypatch.setenv(name, value)
        assert provenance.config_digest() == unset, (name, value)


@pytest.mark.parametrize("frozen", [False, True])
def test_a_setting_and_a_stranger_still_move_the_digest(monkeypatch, frozen):
    """Fail-safe, in a checkout and in a FROZEN engine (no ``config.py`` to
    introspect): a classified setting moves the stamp, and so does a
    variable nobody classified."""
    if frozen:
        monkeypatch.setattr(provenance, "_config_source_path", lambda: None)
    for name in ("O4_FORCE_APT_DAT", "O4_INSET_BAKE_INTERP",
                 "O4_NOBODY_CLASSIFIED_THIS"):
        monkeypatch.delenv(name, raising=False)
        unset = provenance.config_digest()
        monkeypatch.setenv(name, "1")
        assert provenance.config_digest() != unset, name
        monkeypatch.delenv(name)


def test_unclassified_names_only_the_stranger(monkeypatch):
    gates = provenance.introspect_config_gates()
    environ = {"PATH": "/bin", "O4_PARENT_PROCESS_ID": "9",
               "O4_INSET_BAKE_INTERP": "bilinear", next(iter(gates)): "1",
               "O4_NOBODY_CLASSIFIED_THIS": "1"}
    assert provenance_env.unclassified(gates, environ) == [
        "O4_NOBODY_CLASSIFIED_THIS"]
    assert "O4_PARENT_PROCESS_ID" not in provenance_env.digested_environment(
        environ)
