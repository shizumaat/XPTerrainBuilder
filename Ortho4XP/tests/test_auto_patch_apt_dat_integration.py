"""CIFP path-resolution tests: ``cifp_reader.xplane_root_from_cifp_path``
and ``elevation._find_cifp_path``.

Standalone path-resolution tests; require no X-Plane install or
fixture data.
"""
from auto_patch import cifp_reader as AP
from auto_patch.elevation import _find_cifp_path


# ──────────────────────────────────────────────────────────────────────
# xplane_root_from_cifp_path
# ──────────────────────────────────────────────────────────────────────
class TestXplaneRootFromCifpPath:
    def test_standard_custom_data_layout(self, tmp_path):
        """A real X-Plane-style directory tree: Custom Data/CIFP
        under an X-Plane root.  xplane_root should come back as
        the root.
        """
        xp = tmp_path / "X-Plane 12"
        cifp = xp / "Custom Data" / "CIFP"
        cifp.mkdir(parents=True)
        (xp / "Custom Scenery").mkdir()
        assert AP.xplane_root_from_cifp_path(str(cifp)) == str(xp)

    def test_alternative_resources_layout(self, tmp_path):
        """Laminar's default scenery CIFP lives under Resources/."""
        xp = tmp_path / "X-Plane 12"
        cifp = xp / "Custom Data" / "CIFP"
        cifp.mkdir(parents=True)
        (xp / "Resources").mkdir()
        assert AP.xplane_root_from_cifp_path(str(cifp)) == str(xp)

    def test_returns_none_for_missing_path(self):
        assert AP.xplane_root_from_cifp_path(None) is None
        assert AP.xplane_root_from_cifp_path("") is None

    def test_returns_none_when_root_doesnt_look_right(self, tmp_path):
        """If the derived root has neither Custom Scenery nor
        Resources, reject it — the path doesn't look like an
        X-Plane install.
        """
        weird = tmp_path / "not_xplane" / "Custom Data" / "CIFP"
        weird.mkdir(parents=True)
        assert AP.xplane_root_from_cifp_path(str(weird)) is None


# ──────────────────────────────────────────────────────────────────────
# _find_cifp_path — AIRAC update vs the stock cycle
# ──────────────────────────────────────────────────────────────────────
def _make_cifp(root, subdirs, *icaos):
    """Create ``<root>/<subdirs>/<ICAO>.dat`` for each icao."""
    d = root
    for part in subdirs:
        d = d / part
    d.mkdir(parents=True, exist_ok=True)
    for icao in icaos:
        (d / f"{icao}.dat").write_text("RWY:RW18L, , ,00746, ,IVKQ,1, ;\n")
    return d


CUSTOM = ("Custom Data", "CIFP")
STOCK = ("Resources", "default data", "CIFP")


class TestFindCifpPath:
    """An install with no Navigraph must still resolve CIFP data.

    Before the stock fallback existed this returned None for every
    airport on a stock install, and ``_compute_elevations`` silently
    skipped the whole segmented-runway / FAA-profile block — no error,
    just a runway draped without threshold elevations.
    """

    def test_prefers_custom_data_over_stock(self, tmp_path):
        """An AIRAC update wins wherever it has the airport."""
        _make_cifp(tmp_path, CUSTOM, "KCLT")
        _make_cifp(tmp_path, STOCK, "KCLT")
        got = _find_cifp_path(str(tmp_path), "KCLT")
        assert got == str(tmp_path.joinpath(*CUSTOM, "KCLT.dat"))

    def test_falls_back_to_stock_when_no_custom_data_dir(self, tmp_path):
        """The plain no-Navigraph install: only the stock cycle exists."""
        _make_cifp(tmp_path, STOCK, "KCLT")
        got = _find_cifp_path(str(tmp_path), "KCLT")
        assert got == str(tmp_path.joinpath(*STOCK, "KCLT.dat"))

    def test_falls_back_per_file_not_per_directory(self, tmp_path):
        """A PARTIAL AIRAC update — Custom Data/CIFP exists and has some
        airports, but not this one — still resolves from stock.

        A directory-level choice (pick Custom Data because it exists,
        then look only there) would return None here.
        """
        _make_cifp(tmp_path, CUSTOM, "EGLL")
        _make_cifp(tmp_path, STOCK, "EGLL", "KCLT")
        got = _find_cifp_path(str(tmp_path), "KCLT")
        assert got == str(tmp_path.joinpath(*STOCK, "KCLT.dat"))
        # ...while an airport the update DOES carry still comes from it.
        assert _find_cifp_path(str(tmp_path), "EGLL") == str(
            tmp_path.joinpath(*CUSTOM, "EGLL.dat"))

    def test_none_when_neither_location_has_the_airport(self, tmp_path):
        _make_cifp(tmp_path, CUSTOM, "EGLL")
        _make_cifp(tmp_path, STOCK, "EGLL")
        assert _find_cifp_path(str(tmp_path), "KCLT") is None

    def test_icao_is_upper_cased(self, tmp_path):
        _make_cifp(tmp_path, STOCK, "KCLT")
        assert _find_cifp_path(str(tmp_path), "kclt") == str(
            tmp_path.joinpath(*STOCK, "KCLT.dat"))

    def test_empty_root_is_safe(self):
        assert _find_cifp_path("", "KCLT") is None
        assert _find_cifp_path(None, "KCLT") is None

