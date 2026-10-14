import Foundation

/// A tile that failed with a cause the user can fix on the spot (#668:
/// its Custom Scenery folder is a link to a drive that is not mounted),
/// waiting for the user's answer.
public struct O4LinkFix: Sendable, Equatable, Identifiable {
    public let tile: O4TileIssues
    public let link: String
    public var id: String { tile.tileKey + "\u{0}" + link }

    /// The alert's title and message: the engine's own three sentences.
    public var title: String { failure?.what ?? "Tile \(tile.tileKey) was not built." }
    public var message: String {
        guard let failure else { return "" }
        return failure.why + "\n\n" + failure.remedy
    }

    private var failure: O4TileFailure? {
        tile.failures.first(where: \.offersLinkRemoval)
    }
}

/// The fixable failures of the running build, asked AS SOON AS each tile
/// fails (#695), one at a time: several in one run never stack dialogs —
/// the next waits until the one on screen is answered. Pure state; the
/// app's `BuildModel` drives it and the Qt window has its twin
/// (`O4_Qt_Link_Fix.LinkFixQueue`).
public struct O4LinkFixQueue: Sendable, Equatable {
    /// The choice on screen, or nil.
    public private(set) var current: O4LinkFix?
    /// The ones behind it, in the order their tiles failed.
    public private(set) var waiting: [O4LinkFix] = []

    public init() {}

    /// No choice on screen or waiting.
    public var isIdle: Bool { current == nil }

    /// A tile's `BuildDone` arrived: queue its choice when it has one.
    /// Returns true when it was queued (a tile already asked about is not
    /// asked twice).
    @discardableResult
    public mutating func offer(_ tile: O4TileIssues) -> Bool {
        guard let link = tile.removableLink else { return false }
        let fix = O4LinkFix(tile: tile, link: link)
        guard current?.id != fix.id, !waiting.contains(where: { $0.id == fix.id }) else {
            return false
        }
        if current == nil { current = fix } else { waiting.append(fix) }
        return true
    }

    /// The user answered the choice on screen: it is returned, and the
    /// next one (if any) takes its place.
    @discardableResult
    public mutating func answer() -> O4LinkFix? {
        let answered = current
        current = waiting.isEmpty ? nil : waiting.removeFirst()
        return answered
    }
}
