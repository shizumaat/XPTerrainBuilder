"""Twins for the Phase-B FLAG REGISTRY (``auto_patch.fabric_flags``).

The registry exists because of one owner rule in the batch plan: *a
change that is not individually disable-able is a defect*.  A registry
nobody can audit is the same defect wearing a different hat, so these
twins assert the three properties that make it auditable:

1. every flag is DEFAULT-ON and turns off on exactly ``"0"``;
2. every flag the SOURCE consults is REGISTERED here (a flag spelled at
   its call site is a flag bisection cannot find);
3. every registered flag is actually CONSULTED somewhere (a flag with no
   reader is a promise the build does not keep).
"""
import pathlib
import re

import pytest

from auto_patch import fabric_flags as FF


SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "auto_patch"


def test_every_flag_is_default_on():
    assert FF.FLAGS, "an empty registry audits nothing"
    for flag in FF.FLAGS:
        assert flag.default == "1", flag.env
        assert FF.on(flag.env) is True, flag.env
        assert FF.off(flag.env) is False, flag.env


@pytest.mark.parametrize("flag", FF.FLAGS, ids=lambda f: f.env)
def test_zero_disables_and_nothing_else_does(flag, monkeypatch):
    monkeypatch.setenv(flag.env, "0")
    assert FF.on(flag.env) is False
    # A typo fails towards the NEW default, never silently back to
    # production's old behaviour.
    for junk in ("", "false", "off", "no", "1", "2"):
        monkeypatch.setenv(flag.env, junk)
        assert FF.on(flag.env) is True, junk


def test_every_flag_carries_its_authority_row():
    for flag in FF.FLAGS:
        assert flag.what.strip(), flag.env
        assert flag.item.strip(), flag.env


def test_an_unregistered_name_raises_rather_than_defaulting():
    """A consulted-but-undeclared flag must not read as "on"."""
    with pytest.raises(KeyError):
        FF.on("O4_W2_NOT_A_REAL_FLAG")


def test_the_name_shape_is_enforced_at_construction():
    with pytest.raises(ValueError):
        FF.Flag(env="O4_W2_SOMETHING", what="w", item="i")
    with pytest.raises(ValueError):
        FF.Flag(env="O4_FABRIC_W2_X", what="w", item="i",
                default="0")


def _source_files():
    return [p for p in SRC.rglob("*.py") if p.name != "fabric_flags.py"]


def test_every_phase_b_flag_read_in_source_is_registered():
    """No ``os.environ`` reader of an ``O4_W2_*`` / ``O4_W3_*`` name may
    live outside the registry — that is how bisection stays complete."""
    pat = re.compile(r"""O4_FABRIC_W[23]_[A-Z0-9_]+""")
    stray: dict = {}
    for path in _source_files():
        text = path.read_text()
        for name in set(pat.findall(text)):
            if name not in FF.FLAG_INDEX:
                stray.setdefault(name, []).append(path.name)
    assert not stray, f"unregistered Phase-B flag names in source: {stray}"


def test_every_registered_flag_is_consulted_somewhere():
    blob = "\n".join(p.read_text() for p in _source_files())
    for flag in FF.FLAGS:
        assert flag.env in blob, (
            f"{flag.env} is registered but nothing reads it — a flag with "
            f"no consumer is a promise the build does not keep")


def test_registry_report_names_only_the_disabled(monkeypatch):
    assert FF.registry_report() == ""
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_FANS", "0")
    line = FF.registry_report()
    assert "O4_FABRIC_W2_RETIRE_FANS" in line and "NON-DEFAULT" in line
    assert "O4_FABRIC_W2_SPARSE_ALL" not in line
