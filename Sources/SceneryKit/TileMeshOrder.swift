import Foundation

/// The engine's `tile_mesh_order` reply (protocol 1.28, #1729,
/// `Ortho4XP/src/O4_Mesh_Order.py`): which packs' base mesh X-Plane draws
/// instead of a tile (`hiddenBy`, above it in the scenery order) and which
/// local meshes the tile hides (`hides`, below it). The engine owns the
/// check and the ini edit; this app only shows them, in the Qt pane's words.
public struct O4TileMeshOrder: Decodable, Equatable, Sendable {
    public let lat: Int
    public let lon: Int
    /// False when X-Plane does not load the tile from Custom Scenery.
    public let checked: Bool
    /// Highest in the scenery order first.
    public let hiddenBy: [String]
    public let hides: [String]

    private enum CodingKeys: String, CodingKey {
        case lat, lon, checked
        case hiddenBy = "hidden_by", hides
    }

    public init(lat: Int, lon: Int, checked: Bool, hiddenBy: [String], hides: [String]) {
        self.lat = lat
        self.lon = lon
        self.checked = checked
        self.hiddenBy = hiddenBy
        self.hides = hides
    }

    /// `O4_Mesh_Order._names`.
    static func names(_ packs: [String]) -> String {
        guard let first = packs.first else { return "" }
        let quoted = "“\(first)”"
        return packs.count == 1 ? quoted : "\(quoted) and \(packs.count - 1) more"
    }

    /// The tile pane's line when another pack's ground is drawn instead.
    public var hiddenByText: String? {
        hiddenBy.isEmpty ? nil : "Hidden in X-Plane by " + Self.names(hiddenBy)
    }

    /// The tile pane's line when the tile hides a local mesh.
    public var hidesText: String? {
        hides.isEmpty ? nil : "Hides the ground of " + Self.names(hides)
    }
}

/// The row's fixed words (`O4_Mesh_Order.HIDDEN_BY_DETAIL` / `HIDES_DETAIL`
/// and `O4_Qt_Mesh_Order.BUTTONS`; `tests/test_mesh_order_parity.py`).
public enum O4MeshOrderCopy {
    public static let hiddenByDetail = "That scenery ships its own ground for this tile and is above it in X-Plane's scenery order, so X-Plane shows its ground and none of this tile's imagery or graded airports. Move this tile above it, or disable that scenery."
    public static let hidesDetail = "That scenery ships its own ground for a small part of this tile, such as an airport, and is below this tile in X-Plane's scenery order, so X-Plane shows this tile instead. To show its ground, move this tile below it; this tile is then not shown."
    public static let moveAboveButton = "Move Tile Above"
    public static let disableButton = "Disable Scenery"
    public static let showGroundButton = "Show Its Ground"
}

extension OrthoEngineClient {
    /// The scenery order on one tile. An engine before 1.28 answers
    /// ok=false, which throws — the caller shows nothing.
    public func tileMeshOrder(lat: Int, lon: Int, buildDir: String,
                              customSceneryDir: String) async throws -> O4TileMeshOrder {
        try await meshOrderRequest("tile_mesh_order", [
            "lat": lat, "lon": lon, "build_dir": buildDir,
            "custom_scenery_dir": customSceneryDir,
        ])
    }

    /// Write the user's choice into scenery_packs.ini: `action` is
    /// `raise` (the tile above `pack`), `lower` (below it) or `disable`
    /// (the pack). Answers the tile's order afresh; a refusal throws
    /// `O4CommandError` carrying the user's sentence.
    public func applyMeshOrder(lat: Int, lon: Int, buildDir: String,
                               customSceneryDir: String, action: String,
                               pack: String) async throws -> O4TileMeshOrder {
        try await meshOrderRequest("apply_mesh_order", [
            "lat": lat, "lon": lon, "build_dir": buildDir,
            "custom_scenery_dir": customSceneryDir, "action": action, "pack": pack,
        ])
    }

    private func meshOrderRequest(_ command: String,
                                  _ arguments: [String: Any]) async throws -> O4TileMeshOrder {
        try await withCheckedThrowingContinuation { continuation in
            send(command: command, arguments: arguments) { reply in
                let result: Result<O4TileMeshOrder, Error> =
                    Self.decodeReply(reply, command: command)
                continuation.resume(with: result)
            }
        }
    }
}
