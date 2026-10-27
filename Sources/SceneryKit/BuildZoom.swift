import Foundation

/// The next build's detail level (#1539, #1549). Settings' Detail picker
/// and the presets set the DEFAULT while no tile is selected: the zoom for
/// new tiles. Selecting a built tile adopts the zoom it recorded (#1334)
/// for its rebuild only — session state, never written back to the
/// default — so a never-built tile selected afterwards shows the default
/// again. With tiles selected, a zoom chosen in Settings is the
/// selection's (`chooseForSelection`), never the default (RULINGS
/// 2026-10-28j (3)); a new selection drops it (`newSelection`).
/// The Qt window's `MainWindow.build_zl` keeps the same rule.
public struct BuildZoom: Equatable, Sendable {
    /// The active tile's recorded zoom, if it has one.
    public private(set) var adopted: Int?
    /// A zoom chosen in Settings for the current selection.
    public private(set) var selectionChoice: Int?

    public init() {}

    public func current(default defaultZL: Int) -> Int {
        selectionChoice ?? adopted ?? defaultZL
    }

    /// The active tile's imagery (nil: never built, or not reported yet).
    public mutating func adopt(_ choice: TileImageryChoice?) { adopted = choice?.zl }

    /// The user chose a new DEFAULT: it outranks the adoption until the
    /// next selection.
    public mutating func chosen() {
        adopted = nil
        selectionChoice = nil
    }

    /// The user chose a zoom for the selected tiles.
    public mutating func chooseForSelection(_ zl: Int) { selectionChoice = zl }

    /// The selection changed: a choice made for the old one is gone.
    public mutating func newSelection() { selectionChoice = nil }
}
