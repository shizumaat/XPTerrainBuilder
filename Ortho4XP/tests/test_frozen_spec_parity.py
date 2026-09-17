"""Both frozen engines carry the same interpreter belt.

``Ortho4XP_Qt.spec`` has pinned the embedded interpreter's string-hash
seed since the Qt bundle was first frozen; ``Ortho4XP.spec`` — the
engine the mac app embeds — did not, so the two frozen engines started
their interpreters differently.  A spec is Python: it must also still
parse, which is the only check available here (freezing is not run in
the suite).
"""

import ast
import os

ENGINE_ROOT = os.path.join(os.path.dirname(__file__), "..")
SPECS = ("Ortho4XP.spec", "Ortho4XP_Qt.spec")


def _source(name):
    with open(os.path.join(ENGINE_ROOT, name)) as handle:
        return handle.read()


def test_every_spec_parses():
    for name in SPECS:
        ast.parse(_source(name), filename=name)


def test_every_spec_pins_the_hash_seed():
    for name in SPECS:
        assert "('hash_seed=0', None, 'OPTION')" in _source(name), name


def test_every_spec_names_the_scenery_pack_module():
    """Whether scenery_packs.ini is honoured (owner RULINGS 2026-09-17b)
    rides on ``O4_Scenery_Packs`` reaching the frozen bundle.  Its
    consumers import it at TOP LEVEL, so PyInstaller finds it statically;
    naming it in hiddenimports is the belt — the lazy-import class shipped
    a broken frozen engine on 2026-09-10."""
    for name in SPECS:
        assert "'O4_Scenery_Packs'" in _source(name), name
