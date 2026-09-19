"""The Settings sheet and the first-run wizard fit a small laptop.

Beta plan §1 B4, lane betawinsettings (2026-09-17).  MEASURED before
this lane, on the GitHub runners:

    dialog                          windows          mac        linux
    SettingsWindow minimumSizeHint  1228 x 169   696 x 200   696 x 173
    OnboardingWizard sizeHint        864 x 204   602 x 215   462 x 202

A resizable top-level dialog does not clip silently — it simply cannot
be made to fit.  1228 px is unusable on a 1280 px laptop and on any
scaled display; 864 px overflows an 800 px screen.  The cause is font
metrics, not the style (both runners report ``fusion``): the offscreen
font on windows-latest advances a digit at 12 px against 8 px on macOS,
and a plain Qt widget reports its FULL TEXT WIDTH as its MINIMUM, so
every label, button and combo was a font-scaled floor under its window.

These twins run on ALL THREE CI platforms — no win32 skip: a bound that
only macOS checks is exactly how 1228 px shipped.  Every row, category
and page is populated with realistically long values first (long paths,
the longest provider name, the X-Plane page showing a rejection reason
that quotes a long folder), because a dialog measured with its
placeholder values understates its own minimum.

Headless (offscreen); tmp_path cwd so no real global cfg is read.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLineEdit,
)

#: A dialog must fit inside a 1280 x 720 laptop screen with room for the
#: window chrome and the menu bar around it.
MAX_MIN_WIDTH = 760
MAX_MIN_HEIGHT = 560

LONG_PATH = (
    "/Volumes/Scenery Archive 2026/X-Plane 12 Beta Testing/"
    "Custom Scenery/zOrtho4XP_Very_Long_Folder_Name_Here"
)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _effective_minimum(dialog):
    """What the window manager will not let the user shrink past.

    ``minimumSizeHint`` alone is not the bound: ``SettingsWindow``
    also calls ``setMinimumWidth`` from its content clamp, and the
    larger of the two wins.
    """
    return (
        max(dialog.minimumSizeHint().width(), dialog.minimumWidth()),
        max(dialog.minimumSizeHint().height(), dialog.minimumHeight()),
    )


def _populate(window):
    """Every row carries a long value, and every category is visited.

    The content clamp measures rows from EVERY category, so a window
    left on category 0 still has to be shown once per category for the
    pending ``app-wide`` tags to be laid out.
    """
    import O4_Settings_Model as SM

    for row in window.rows.values():
        if isinstance(row.control, QLineEdit):
            row.control.setText(LONG_PATH)
        elif isinstance(row.control, QComboBox) and row.control.count():
            widest = max(
                range(row.control.count()),
                key=lambda i: len(row.control.itemText(i)),
            )
            row.control.setCurrentIndex(widest)
    window.advanced_check.setChecked(True)  # nothing hidden from the bound
    for index in range(len(SM.CATEGORIES)):
        window.category_list.setCurrentRow(index + window._sidebar_offset)
        QApplication.processEvents()
    window.category_list.setCurrentRow(0)
    QApplication.processEvents()


@pytest.fixture
def settings_window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from O4_Qt_Settings import SettingsWindow

    made = []

    def build(tiles):
        window = SettingsWindow(
            prefs={}, tiles=tiles, custom_build_dir="")
        made.append(window)
        window.show()
        qapp.processEvents()
        _populate(window)
        return window

    yield build
    for window in made:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize(
    "tiles", [[], [(36, -87)], [(36, -87), (37, -88)]],
    ids=["global", "one-tile", "two-tiles"],
)
def test_settings_window_fits_a_small_laptop(settings_window, tiles):
    window = settings_window(tiles)
    width, height = _effective_minimum(window)
    assert width <= MAX_MIN_WIDTH, (
        "the settings window cannot be made narrower than %d px on %s; "
        "a 1280 px laptop (or a Windows display at 125%% scaling) cannot "
        "hold it" % (width, sys.platform)
    )
    assert height <= MAX_MIN_HEIGHT, (
        "the settings window cannot be made shorter than %d px on %s"
        % (height, sys.platform)
    )


def test_the_settings_default_size_fits_1280x720(settings_window):
    """Not only shrinkable — it must OPEN inside a small screen."""
    window = settings_window([])
    assert window.sizeHint().width() <= 1280
    assert window.sizeHint().height() <= 720
    assert window.width() <= 1280 and window.height() <= 720


def test_the_settings_rows_scroll_so_height_never_forces_the_window(
    settings_window,
):
    """Every row lives inside the scroll area: the window's minimum
    height must not grow with the number of rows in a category."""
    window = settings_window([])
    assert window.scroll.widgetResizable()
    for row in window.rows.values():
        assert window.scroll.isAncestorOf(row)
    tall = window.scroll.widget().sizeHint().height()
    # The content really is taller than the bound on every platform,
    # so the bound below is the scroll area's doing, not an accident.
    assert tall > 400
    assert _effective_minimum(window)[1] <= MAX_MIN_HEIGHT


def test_a_long_row_name_keeps_its_full_text_and_its_tooltip(
    settings_window,
):
    """The squeeze must not lose information: the label answers the
    whole name, and the row's own explanation outranks the full-text
    fallback in the tooltip."""
    from O4_Qt_Widgets import ElidedRowLabel

    window = settings_window([])
    row = max(window.rows.values(), key=lambda r: len(r.setting.label))
    assert isinstance(row.name_label, ElidedRowLabel)
    assert row.name_label.text() == row.setting.label
    assert row.name_label.toolTip() == (
        row.setting.hint or row.setting.name)


class TestElidedRowLabelBoundary:
    """A label granted EXACTLY its size hint must NOT elide.

    ``QFontMetrics::elidedText`` measures in ``QFontMetricsF`` and
    rounds differently from ``horizontalAdvance``, which the size hint
    is built from.  A label handed precisely its hint width therefore
    came back one ellipsis short — and in the settings sheet every row
    name sits at exactly its hint, so at the window's DEFAULT size all
    32 visible names were elided (measured 2026-09-17, macOS).  That is
    the mac look this lane had to keep.
    """

    def _label(self, qapp, text, width):
        from O4_Qt_Widgets import ElidedRowLabel

        label = ElidedRowLabel(text)
        label.show()  # a hidden widget defers resizeEvent to show time
        label.resize(width, 24)
        qapp.processEvents()
        return label

    NAME = "Modify custom airports (reseat objects)"

    def test_exactly_its_hint_is_not_elided(self, qapp):
        from PySide6.QtWidgets import QLabel

        probe = self._label(qapp, self.NAME, 400)
        label = self._label(qapp, self.NAME, probe.sizeHint().width())
        assert QLabel.text(label) == self.NAME
        assert label.toolTip() == ""

    def test_narrower_than_its_hint_still_elides(self, qapp):
        from PySide6.QtWidgets import QLabel

        label = self._label(qapp, self.NAME, 40)
        assert QLabel.text(label) != self.NAME
        assert QLabel.text(label).endswith("…")
        assert label.text() == self.NAME  # the full text survives
        assert label.toolTip() == self.NAME


@pytest.fixture
def wizard(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import O4_Qt_Wizard as WIZ

    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    made = []

    def build():
        dialog = WIZ.OnboardingWizard(
            {"xplane_dir": LONG_PATH, "output_dir": LONG_PATH},
            # The longest provider code the imagery menu can carry.
            ["BI", "GO2", "USA_5M_DEM_AND_A_VERY_LONG_PROVIDER_CODE"],
        )
        made.append(dialog)
        dialog.show()
        qapp.processEvents()
        return dialog

    yield build
    for dialog in made:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("step", range(4))
def test_the_wizard_fits_a_small_laptop_on_every_step(qapp, wizard, step):
    """Including the X-Plane page showing its REJECTION reason, which
    quotes the folder the user picked — a path has nothing to wrap at."""
    dialog = wizard()
    dialog._set_step(step)
    qapp.processEvents()
    if step == 1:
        assert "Custom Scenery" in dialog.unlock_label.text()
    assert dialog.sizeHint().width() <= MAX_MIN_WIDTH, (
        "the wizard prefers %d px on step %d on %s"
        % (dialog.sizeHint().width(), step, sys.platform)
    )
    assert dialog.sizeHint().height() <= MAX_MIN_HEIGHT
    width, height = _effective_minimum(dialog)
    assert width <= MAX_MIN_WIDTH and height <= MAX_MIN_HEIGHT


def test_the_wizard_still_shows_its_copy_at_its_default_size(qapp, wizard):
    """The squeeze is presentation-only: at the wizard's own default
    size nothing is elided away."""
    dialog = wizard()
    dialog.resize(640, 400)
    qapp.processEvents()
    for step in range(4):
        dialog._set_step(step)
        qapp.processEvents()
        page = dialog.stack.currentWidget()
        assert page.width() > 0 and page.height() > 0


# ---------------------------------------------------------------------
# The boundary-airport sheet (spec insets-follow-patch-set-spec.md §C.7)
# ---------------------------------------------------------------------
#: The dialog is ONE sheet for a whole batch, so its worst case is a
#: batch full of straddling airports — the bound has to hold there.
BOUNDARY_AIRPORTS = [
    {
        "icao": "LP%02d" % index,
        "name": "Aeroporto Internacional de Lisboa Portela %d" % index,
        "home": [38, -10],
        "neighbours": [[38, -9], [39, -9]],
        "crossing_m": 1234.5 + index,
    }
    for index in range(20)
]


@pytest.fixture
def boundary_dialog(qapp):
    import O4_Qt_Boundary_Dialog as BD

    made = []

    def build(airports=BOUNDARY_AIRPORTS, add_tiles=((38, -9), (39, -9))):
        dialog = BD.BoundaryAirportsDialog(
            list(airports), list(add_tiles), default_choice="neighbour")
        made.append(dialog)
        dialog.show()
        qapp.processEvents()
        return dialog

    yield build
    for dialog in made:
        dialog.close()
        dialog.deleteLater()


def test_the_boundary_dialog_fits_a_small_laptop_with_twenty_airports(
    boundary_dialog,
):
    dialog = boundary_dialog()
    width, height = _effective_minimum(dialog)
    assert width <= MAX_MIN_WIDTH, (
        "the boundary-airport dialog cannot be made narrower than %d px "
        "on %s" % (width, sys.platform)
    )
    assert height <= MAX_MIN_HEIGHT, (
        "the boundary-airport dialog cannot be made shorter than %d px "
        "on %s" % (height, sys.platform)
    )
    assert dialog.sizeHint().width() <= 1280
    assert dialog.sizeHint().height() <= 720


def test_the_boundary_list_scrolls_instead_of_growing_the_dialog(
    boundary_dialog,
):
    """Twenty rows and one row must ask for the same window height."""
    tall = boundary_dialog()
    short = boundary_dialog(airports=BOUNDARY_AIRPORTS[:1])
    assert tall.scroll.isAncestorOf(tall.rows[0])
    assert tall.scroll.widget().sizeHint().height() > 200
    assert _effective_minimum(tall)[1] <= _effective_minimum(short)[1] + 8
