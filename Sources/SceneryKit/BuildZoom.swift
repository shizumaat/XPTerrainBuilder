import Foundation

/// The next build's detail level (#1539). Settings' Detail picker, the
/// presets and first run set the DEFAULT: the zoom for new tiles, the one
/// the preset cards compare. Selecting a built tile adopts the zoom it
/// recorded (#1334) for its rebuild only — session state, never written
/// back to the default — so a never-built tile selected afterwards shows
/// the default again. Before #1539 the adoption overwrote the default:
/// after a ZL17 tile, a new tile showed ZL17 and no preset card matched.
/// The Qt window's `MainWindow.build_zl` keeps the same rule.
public struct BuildZoom: Equatable, Sendable {
    /// The active tile's recorded zoom, if it has one.
    public private(set) var adopted: Int?

    public init() {}

    public func current(default defaultZL: Int) -> Int { adopted ?? defaultZL }

    /// The active tile's imagery (nil: never built, or not reported yet).
    public mutating func adopt(_ choice: TileImageryChoice?) { adopted = choice?.zl }

    /// The user chose a zoom: it becomes the default and outranks the
    /// adoption until the next selection.
    public mutating func chosen() { adopted = nil }
}
