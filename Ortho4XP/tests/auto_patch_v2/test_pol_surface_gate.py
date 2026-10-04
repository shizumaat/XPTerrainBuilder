"""THE ``.pol``'s OWN ``SURFACE`` DECLARATION ADMITS IT AS PAVEMENT (owner
RULINGS 2026-10-04, issue #333: "We should recognize the conc_3.pol as
pavement").  SPJC's ``zannespol/conc_3.pol`` names no material token; the
file says ``SURFACE concrete``.  The declaration only ADMITS, and only
past the decorative/terrain name veto — every name the gate refused
before 2026-10-04 on the seven measured packs is still refused.
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


def test_conc3_admitted_by_its_surface_declaration(tmp_path):
    _pol(tmp_path, "zannespol/conc_3.pol", "concrete")
    assert not S.is_pavement_def("zannespol/conc_3.pol")        # the name tier
    assert S.pol_surface(str(tmp_path / "zannespol/conc_3.pol")) == "concrete"
    assert _gate(tmp_path)("zannespol/conc_3.pol") == (True, "concrete")
    # the surface code follows the declaration, not the (token-less) name
    assert S.pavement_surface_code("zannespol/conc_3.pol", "concrete") == 2
    assert S.pavement_surface_code("zannespol/conc_3.pol") == 1


def test_neutral_name_asphalt_surface_admits(tmp_path):
    _pol(tmp_path, "ground/tarmac_dark.pol", "asphalt")
    assert _gate(tmp_path)("ground/tarmac_dark.pol") == (True, "asphalt")
    assert S.pavement_surface_code("ground/tarmac_dark.pol", "asphalt") == 1


#: Names the gate REFUSED inside the measured packs' fields — each stays
#: refused even holding a HARD declaration (given one here where the real
#: file has none: the name veto must not depend on the file).
@pytest.mark.parametrize("rel,surface", [
    ("objectfede/lines/red_grid.pol", "asphalt"),                # SPJC
    ("lib/airport/lines/safety_area_red.pol", "asphalt"),        # SPJC, stock
    ("lib/airport/markings/DrapedDirSigns.pol", "concrete"),     # CYXY, stock
    ("MisterX_Library/Airport/Ground_Markings/Painted_Signs/"
     "Backgrounds_Black_Y.pol", "concrete"),
    ("ground/markings_stripes.pol", "asphalt"),                  # KASE
    ("Lib_Making/ground_polygon/Concrete/MAN/Asphalt_1_NOLINE.pol",
     "asphalt"),                 # HECA: "line" in NOLINE — reported, not admitted
    ("ground/grunge_1.pol", "concrete"),                         # KASE
    ("zannespol/gravel_01.pol", "asphalt"),      # a terrain word still vetoes
    ("zannespol/pasto80.pol", "grass"),          # a soft declaration never admits
    ("images/NLWF_0x0.pol", None),               # an orthophoto page, no SURFACE
    ("objectfede/3posSmall.pol", None),
])
def test_decorative_soft_and_undeclared_stay_refused(tmp_path, rel, surface):
    _pol(tmp_path, rel, surface)
    assert not S.is_pavement_def(rel)
    assert _gate(tmp_path)(rel)[0] is False


def test_paint_layer_group_withdraws_the_declaration(tmp_path):
    """KCLT ``ground_marks/mark_dir_amarillo.pol``: ``SURFACE concrete``
    in ``LAYER_GROUP markings +1`` is paint, whatever row comes first."""
    a = _pol(tmp_path, "ground_marks/mark_dir_amarillo.pol", "concrete",
             layer="LAYER_GROUP markings +1")
    assert S.pol_surface(a) is None
    assert _gate(tmp_path)("ground_marks/mark_dir_amarillo.pol") == (False, None)
    b = _pol(tmp_path, "g/late.pol", "asphalt", layer="")
    with open(b, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("LAYER_GROUP Markings -1\n")
    assert _gate(tmp_path)("g/late.pol") == (False, None)
    # conc_3's own rows: taxiways +3, then runways 2 — neither is paint
    c = _pol(tmp_path, "zannespol/conc_3.pol", "concrete")
    with open(c, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("LAYER_GROUP runways 2\n")
    assert _gate(tmp_path)("zannespol/conc_3.pol") == (True, "concrete")


def test_declaration_never_vetoes_a_name_admitted_def(tmp_path):
    """Admission-only: a material-token or stock name is judged as it
    always was, and its file is never opened."""
    _pol(tmp_path, "zannespol/concrete_1.pol", "grass")
    opened = []

    def resolve(p):
        opened.append(p)
        return str(tmp_path / p)
    gate = S.pavement_gate(resolve)
    assert gate("zannespol/concrete_1.pol") == (True, None)
    assert gate("lib/airport/pavement/asphalt_5L.pol") == (True, None)
    assert gate("lib/airport/Modern_Airports/Terminal_kit/x.fac") == (False, None)
    assert opened == []


def test_unresolved_pol_falls_back_to_the_name_tier(tmp_path):
    gate = _gate(tmp_path)                       # nothing on disk, no index
    assert gate("zannespol/conc_3.pol") == (False, None)
    assert S.pol_surface(None) is None
    assert S.pol_surface(str(tmp_path / "absent.pol")) is None


def test_library_pol_resolves_through_the_index(tmp_path):
    phys = _pol(tmp_path / "lib", "surfaces/slab.pol", "concrete")
    gate = _gate(tmp_path / "pack", {"vendor/apron/slab_a.pol": phys})
    assert gate("vendor/apron/slab_a.pol") == (True, "concrete")


def test_first_surface_row_and_memo(tmp_path):
    path = _pol(tmp_path, "g/a.pol", "Concrete")
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("SURFACE grass\n")
    assert S.pol_surface(path) == "concrete"
    calls = []
    gate = S.pavement_gate(lambda p: (calls.append(p), path)[1])
    assert gate("g/a.pol") == gate("g/a.pol") == (True, "concrete")
    assert calls == ["g/a.pol"]
