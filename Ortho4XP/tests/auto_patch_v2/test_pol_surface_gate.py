"""``conc_3.pol`` IS PAVEMENT (owner RULINGS 2026-10-04d (2), issue #333:
"We should recognize the conc_3.pol as pavement").  SPJC's
``zannespol/conc_3.pol`` names no material token; ``conc`` is admitted as
a WORD, and the ``.pol``'s own ``SURFACE`` / ``LAYER_GROUP`` rows confirm
or refuse it.  Every other name the gate refused on the seven measured
packs (SPJC, HECA, CYXY, KCLT, KASE, NLWF, OTHH) is still refused.
"""
from __future__ import annotations

import os

import pytest

from auto_patch_v2.airport import dsf as S


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


@pytest.mark.parametrize("rel", [
    "zannespol/conc_3.pol", "Ground/Conc-2.pol", "g/conc.pol", "g/conc4.pol",
    "g/apron_conc.pol", "conc/slab_a.pol", "g/CONC_DARK.pol"])
def test_conc_word_admits(rel):
    assert S.is_pavement_def(rel)
    assert S.pavement_surface_code(rel) == 2


@pytest.mark.parametrize("rel", [
    "terminal/concourse_floor.pol", "g/zinconc.pol", "g/second_apron.pol",
    "g/conch.pol", "g/reconcile.pol", "g/conc_3.fac", "g/conc_3.lin",
    # the skip tokens veto the abbreviation as they veto a material token
    "g/conc_lines.pol", "g/conc_grunge.pol", "markings/conc_3.pol",
    "g/conc_gravel.pol"])
def test_conc_inside_another_word_or_decorative_refuses(rel):
    assert not S.is_pavement_def(rel)


def test_conc3_confirmed_by_its_own_declaration(tmp_path):
    path = _pol(tmp_path, "zannespol/conc_3.pol", "concrete")
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("LAYER_GROUP runways 2\n")          # conc_3's own second row
    assert S.pol_surface(path) == "concrete"
    assert _gate(tmp_path)("zannespol/conc_3.pol") == (True, "concrete")
    assert S.pavement_surface_code("zannespol/conc_3.pol", "concrete") == 2
    _pol(tmp_path, "g/conc_1.pol", "asphalt")
    assert _gate(tmp_path)("g/conc_1.pol") == (True, "asphalt")
    assert S.pavement_surface_code("g/conc_1.pol", "asphalt") == 1


@pytest.mark.parametrize("surface,layer,read", [
    ("grass", "LAYER_GROUP taxiways +3", "grass"),
    ("gravel", "", "gravel"),
    ("concrete", "LAYER_GROUP markings +1", S.PAINT),   # KCLT mark_dir_amarillo's rows
    ("asphalt", "LAYER_GROUP Markings -1", S.PAINT)])
def test_declaration_refuses_the_abbreviation(tmp_path, surface, layer, read):
    _pol(tmp_path, "g/conc_3.pol", surface, layer)
    assert _gate(tmp_path)("g/conc_3.pol") == (False, read)


def test_unresolved_or_undeclared_leaves_the_name_standing(tmp_path):
    assert _gate(tmp_path)("zannespol/conc_3.pol") == (True, None)     # no file
    _pol(tmp_path, "g/conc_9.pol", None)
    assert _gate(tmp_path)("g/conc_9.pol") == (True, None)             # no SURFACE row
    assert S.pol_surface(None) is None
    assert S.pol_surface(str(tmp_path / "absent.pol")) is None


#: Names the gate REFUSED inside the measured packs' fields — each stays
#: refused even holding a HARD declaration (the declaration confirms an
#: abbreviation; it admits nothing by itself).  The obviously-pavement
#: ones (HECA ``Asphalt_1_NOLINE``, OTHH ``ASPH*`` / ``Stone_Tiles*``)
#: are REPORTED to the owner, not admitted.
@pytest.mark.parametrize("rel,surface", [
    ("objectfede/lines/red_grid.pol", "asphalt"),                # SPJC
    ("objectfede/3posSmall.pol", "asphalt"),
    ("lib/airport/lines/safety_area_red.pol", "asphalt"),        # stock
    ("lib/airport/markings/DrapedDirSigns.pol", "concrete"),     # CYXY, stock
    ("ground_marks/mark_dir_amarillo.pol", "concrete"),          # KCLT
    ("ground/markings_stripes.pol", "asphalt"),                  # KASE
    ("ground/grunge_1.pol", "concrete"),
    ("ground/Stp_WSP.pol", "asphalt"),
    ("images/NLWF_0x0.pol", "asphalt"),                          # NLWF
    ("Lib_Making/ground_polygon/Concrete/MAN/Asphalt_1_NOLINE.pol", "asphalt"),
    ("Ground/Poly/ASPH1.pol", "asphalt"),                        # OTHH
    ("Ground/Poly/Stone_Tiles1.pol", "asphalt"),
    ("Ground/Poly/Grass3.pol", "asphalt"),
    ("Ground/dirt/Tireskid.pol", "asphalt"),
    ("zannespol/gravel_01.pol", "asphalt"),
    ("zannespol/pasto80.pol", "grass"),
])
def test_previously_refused_names_stay_refused(tmp_path, rel, surface):
    _pol(tmp_path, rel, surface)
    assert not S.is_pavement_def(rel)
    assert not S.is_pavement_def(rel, surface)
    assert _gate(tmp_path)(rel) == (False, None)


def test_name_admitted_defs_open_no_file(tmp_path):
    """A material-token or stock name is judged as it always was — a
    declaration cannot veto it, because its file is never read."""
    _pol(tmp_path, "zannespol/concrete_1.pol", "grass")
    opened = []
    gate = S.pavement_gate(lambda p: opened.append(p))
    assert gate("zannespol/concrete_1.pol") == (True, None)
    assert gate("lib/airport/pavement/asphalt_5L.pol") == (True, None)
    assert gate("lib/airport/Modern_Airports/Terminal_kit/x.fac") == (False, None)
    assert gate("Ground/Poly/ASPH1.pol") == (False, None)
    assert opened == []
    assert gate("zannespol/conc_3.pol") == gate("zannespol/conc_3.pol") == (True, None)
    assert opened == ["zannespol/conc_3.pol"]                   # memoised


def test_library_conc_pol_resolves_through_the_index(tmp_path):
    phys = _pol(tmp_path / "lib", "surfaces/slab.pol", "grass")
    gate = _gate(tmp_path / "pack", {"vendor/apron/conc_a.pol": phys})
    assert gate("vendor/apron/conc_a.pol") == (False, "grass")


def test_object_resource_surface_code_unchanged():
    """``pavement_surface_code`` also prices object-pavement resources:
    the abbreviation is a ``.pol`` reading only."""
    assert S.pavement_surface_code("objects/conc_pad.obj") == 1
    assert S.pavement_surface_code("objects/concrete_pad.obj") == 2
