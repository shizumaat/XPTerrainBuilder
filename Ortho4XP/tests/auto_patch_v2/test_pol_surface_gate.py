"""THE ``.pol`` PAVEMENT GATE.

Owner RULINGS 2026-10-04e (1), issue #337: a draped ``.pol`` whose own
file declares ``SURFACE asphalt`` or ``SURFACE concrete`` is pavement
whatever its name, minus markings (``LAYER_GROUP markings`` and the
paint/sign name families).  RULINGS 2026-10-04d (2), issue #333: the
``conc`` word is the name fallback where the file is unresolvable or
declares no surface.  The refusals below are the defs measured inside the
fields of SPJC, HECA, CYXY, KCLT, KASE, NLWF and OTHH, with their own
files' rows.
"""
from __future__ import annotations

import os

import pytest

from auto_patch_v2.airport import dsf as S

D = S.PolDeclaration


def _pol(root, rel, surface=None, layer="LAYER_GROUP taxiways +3"):
    path = os.path.join(str(root), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = ["A", "850", "DRAPED_POLYGON", layer, "", "TEXTURE tex.png"]
    if surface is not None:
        rows.append(f"SURFACE {surface}")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rows) + "\n")
    return path


def _gate(root, index=None):
    from auto_patch_v2.airport import obj8
    return S.pavement_gate(lambda p: obj8.resolve_resource(p, str(root), index))


# ── 04e (1): the file's declaration is sufficient ────────────────────────

@pytest.mark.parametrize("rel,surface,layer", [
    ("zannespol/conc_3.pol", "concrete", "taxiways +3"),             # SPJC
    ("Ground/Poly/ASPH1.pol", "asphalt", "runways +1"),              # OTHH
    ("Ground/Poly/ASPH1_upper.pol", "asphalt", "runways +4"),
    ("Ground/Poly/Stone_Tiles1.pol", "asphalt", "runways +2"),
    ("textures/tarmac_dark.pol", "asphalt", None),      # no layer row at all
    # HECA: "line" in NOLINE refused the NAME; the file names its own layer
    ("Lib_Making/ground_polygon/Concrete/MAN/Asphalt_1_NOLINE.pol",
     "asphalt", "taxiways +1"),
])
def test_hard_surface_admits_whatever_the_name(tmp_path, rel, surface, layer):
    _pol(tmp_path, rel, surface, f"LAYER_GROUP {layer}" if layer else "")
    assert _gate(tmp_path)(rel) == (True, surface)
    assert S.pavement_surface_code(rel, surface) == (2 if surface == "concrete" else 1)


@pytest.mark.parametrize("rel,surface,layer", [
    # paint: the markings layer group refuses, whatever the name
    ("ground_marks/mark_dir_amarillo.pol", "concrete", "markings +1"),   # KCLT
    ("g/neutral_slab.pol", "asphalt", "Markings -1"),
    ("lib/airport/signs/DrapedRwySigns.pol", "concrete", "markings"),
    ("lib/airport/markings/DrapedDirSigns.pol", "concrete", "markings"), # CYXY
    ("lib/airport/lines/safety_area_red.pol", "asphalt", "markings -1"),
    ("Ground/Markings/safe_area_yellow.pol", "asphalt", "markings -1"),  # OTHH
    ("objectfede/lines/red_grid.pol", "asphalt", "markings -1"),         # SPJC
    ("lib/airport/markings/colored_area_green.pol", "asphalt", "markings -2"),
    # a decorative NAMESPACE refuses even on a pavement layer
    ("objectfede/lines/red_grid.pol", "asphalt", "taxiways +1"),
    # a paint/sign WORD stands against a file that names NO layer group
    ("g/apron_signs.pol", "concrete", None),
    ("g/taxi_line_fill.pol", "asphalt", None),
    # a terrain word refuses whatever the file says (OTHH Grass3: asphalt,
    # ``LAYER_GROUP shoulders 5``, ``TEXTURE Grass3.dds``)
    ("Ground/Poly/Grass3.pol", "asphalt", "shoulders 5"),
    ("zannespol/gravel_01.pol", "asphalt", "taxiways +1"),
    # a soft declaration never admits
    ("zannespol/pasto80.pol", "grass", "taxiways +1"),
    ("g/slab.pol", "gravel", None),
    # no SURFACE row: KASE grunge / Stp_WSP, NLWF ortho pages, OTHH dirt
    ("ground/grunge_1.pol", None, "runways 4"),
    ("ground/Stp_WSP.pol", None, "runways 3"),
    ("images/NLWF_0x0.pol", None, None),
    ("objectfede/3posSmall.pol", None, "airports +1"),
    ("Ground/dirt/Tireskid.pol", None, "markings +5"),
    ("lib/airport/ground/terrain/soil_1.pol", None, None),
])
def test_markings_terrain_soft_and_undeclared_stay_refused(tmp_path, rel, surface, layer):
    _pol(tmp_path, rel, surface, f"LAYER_GROUP {layer}" if layer else "")
    assert not S.is_pavement_def(rel)
    assert _gate(tmp_path)(rel)[0] is False


def test_paint_layer_wins_wherever_its_row_sits(tmp_path):
    path = _pol(tmp_path, "g/late.pol", "asphalt", "LAYER_GROUP taxiways +1")
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("LAYER_GROUP markings -1\n")
    assert S.pol_declaration(path) == D("asphalt", S.PAINT)
    assert _gate(tmp_path)("g/late.pol") == (False, "asphalt")
    # conc_3's own two rows — taxiways +3, then runways 2 — neither is paint
    c = _pol(tmp_path, "zannespol/conc_3.pol", "Concrete")
    with open(c, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("LAYER_GROUP runways 2\nSURFACE grass\n")
    assert S.pol_declaration(c) == D("concrete", "taxiways")


# ── 04d (2): the conc word, the fallback ─────────────────────────────────

@pytest.mark.parametrize("rel", [
    "zannespol/conc_3.pol", "Ground/Conc-2.pol", "g/conc.pol", "g/conc4.pol",
    "g/apron_conc.pol", "conc/slab_a.pol", "g/CONC_DARK.pol"])
def test_conc_word_admits_without_a_file(tmp_path, rel):
    assert S.is_pavement_def(rel)
    assert _gate(tmp_path)(rel) == (True, None)
    assert S.pavement_surface_code(rel) == 2


@pytest.mark.parametrize("rel", [
    "terminal/concourse_floor.pol", "g/zinconc.pol", "g/second_apron.pol",
    "g/conch.pol", "g/reconcile.pol", "g/conc_3.fac", "g/conc_3.lin",
    "g/conc_lines.pol", "g/conc_grunge.pol", "markings/conc_3.pol",
    "g/conc_gravel.pol", "Ground/Poly/ASPH1.pol"])
def test_no_file_no_conc_word_refuses(tmp_path, rel):
    assert not S.is_pavement_def(rel)
    assert _gate(tmp_path)(rel) == (False, None)


def test_conc_word_stands_on_a_file_with_no_surface_and_yields_to_one(tmp_path):
    _pol(tmp_path, "g/conc_9.pol", None)
    assert _gate(tmp_path)("g/conc_9.pol") == (True, None)
    _pol(tmp_path, "g/conc_8.pol", "grass")
    assert _gate(tmp_path)("g/conc_8.pol") == (False, "grass")
    _pol(tmp_path, "g/conc_7.pol", "concrete", "LAYER_GROUP markings +1")
    assert _gate(tmp_path)("g/conc_7.pol") == (False, "concrete")
    assert S.pol_declaration(None) == S.pol_declaration(str(tmp_path / "absent.pol")) == D()


# ── the name-settled defs open no file ───────────────────────────────────

def test_name_settled_defs_open_no_file(tmp_path):
    """A stock namespace, a clean material-token name, a decorative
    namespace and a terrain word are settled by the name: the file is
    never read, so a declaration cannot veto a material-token name."""
    opened = []
    gate = S.pavement_gate(lambda p: opened.append(p))
    assert gate("zannespol/concrete_1.pol") == (True, None)
    assert gate("lib/airport/pavement/asphalt_5L.pol") == (True, None)
    assert gate("lib/airport/Modern_Airports/Terminal_kit/x.fac") == (False, None)
    assert gate("objectfede/lines/red_grid.pol") == (False, None)
    assert gate("Ground/Poly/Grass3.pol") == (False, None)
    assert opened == []
    assert gate("Ground/Poly/ASPH1.pol") == gate("Ground/Poly/ASPH1.pol") == (False, None)
    assert opened == ["Ground/Poly/ASPH1.pol"]                  # memoised
    assert S.is_pavement_def("zannespol/concrete_1.pol", D("grass", "taxiways"))


def test_library_pol_resolves_through_the_index(tmp_path):
    phys = _pol(tmp_path / "lib", "surfaces/slab.pol", "concrete")
    gate = _gate(tmp_path / "pack", {"vendor/apron/slab_a.pol": phys})
    assert gate("vendor/apron/slab_a.pol") == (True, "concrete")


def test_object_resource_surface_code_unchanged():
    """``pavement_surface_code`` also prices object-pavement resources:
    the abbreviation is a ``.pol`` reading only."""
    assert S.pavement_surface_code("objects/conc_pad.obj") == 1
    assert S.pavement_surface_code("objects/concrete_pad.obj") == 2
