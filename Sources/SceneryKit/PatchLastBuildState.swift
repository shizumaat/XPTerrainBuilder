import Foundation

/// "Preview | Last build" (spec §5): which surface the window shows, and
/// whether the last build's mesh can be shown. The mesh is fetched once
/// per build (the tile's mesh date), never live.
public struct PatchLastBuildState: Equatable, Sendable {
    public enum Mode: String, CaseIterable, Sendable { case preview = "Preview", lastBuild = "Last build" }
    public enum Mesh: Equatable, Sendable {
        case unknown
        case loading
        case available
        /// The engine's sentence (shown as the control's help).
        case unavailable(String)
    }

    public private(set) var mode: Mode = .preview
    public private(set) var mesh: Mesh = .unknown
    /// The build whose mesh `mesh` describes (`O4TileInfo.meshDate`).
    public private(set) var meshBuild: Double?

    public init() {}

    /// Last build can be picked unless the engine said there is no mesh.
    public var canShowLastBuild: Bool {
        if case .unavailable = mesh { return false }
        return true
    }

    public var unavailableReason: String? {
        if case .unavailable(let why) = mesh { return why }
        return nil
    }

    /// Pick a mode; returns true when the mesh must be fetched now.
    public mutating func select(_ m: Mode, build: Double?) -> Bool {
        guard m == .preview || canShowLastBuild else { return false }
        mode = m
        return m == .lastBuild && (mesh == .unknown || build != meshBuild) && mesh != .loading
    }

    /// The tile was rebuilt (or first seen): a new mesh date forgets the
    /// old answer; returns true when Last build is showing and must refetch.
    public mutating func tileBuilt(_ build: Double?) -> Bool {
        guard build != meshBuild else { return false }
        mesh = .unknown
        if mode == .lastBuild { return true }
        return false
    }

    public mutating func fetching(build: Double?) { mesh = .loading; meshBuild = build }

    public mutating func fetched(_ ok: Bool, reason: String = "") {
        mesh = ok ? .available : .unavailable(reason)
        if !ok { mode = .preview }
    }
}
