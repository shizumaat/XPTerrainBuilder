import SwiftUI

/// A selected row's content in a focused list (Apple's emphasized style):
/// the row is filled with the accent colour, so content drawn IN the
/// accent colour — a progress bar's fill, a running step — vanishes, and
/// status colours fight it. AppKit switches a cell to
/// `backgroundStyle == .emphasized`; SwiftUI reports the same as
/// `backgroundProminence == .increased`. There, coloured content is drawn
/// white; `.primary` / `.secondary` already turn vibrant white on their own.
enum SelectedRowStyle {
    static func isEmphasized(_ prominence: BackgroundProminence) -> Bool {
        prominence == .increased
    }

    /// `color`, or white on an emphasized (selected, focused) row.
    static func tint(_ color: Color, _ prominence: BackgroundProminence) -> Color {
        isEmphasized(prominence) ? .white : color
    }

    /// Extra space above and below an Activity row's content, on top of
    /// the sidebar list's own row inset (owner 2026-11-17: the multi-line
    /// rows read tighter than Finder/Mail). A sidebar row of one 13 pt
    /// line is 28 pt at the default (Medium) sidebar size — 16 pt of line
    /// plus 6 pt above and below; the list's own inset gives a multi-line
    /// row about 4 pt, so 2 pt more each side brings it to the same 6 pt.
    static let rowVerticalPadding: CGFloat = 2
}
