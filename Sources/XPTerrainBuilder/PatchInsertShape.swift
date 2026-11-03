import AppKit
import SceneryKit

/// "Insert shape" from the map's right-click menu (#1314; Qt
/// `O4_Qt_Patch_Insert`). The engine plans it (`patch_insert_shape`: a
/// 20 m square at the click, each corner at the elevation under it, the
/// airport whose extent holds the point), asked again while an elevation
/// source is still loading, as the cursor readout does. The open patch of
/// that airport takes the square as ONE undoable edit (Edit mode, the
/// shape selected, the save bar counts it); any other airport's patch
/// gets it on disk through `patch_add_shape`, which starts the airport's
/// edited patch when it has none, and the engine's sentence says what was
/// written. "Insert tunnel ramp" (#1745, protocol 1.24) is the same insert
/// with `kind: "tunnel_ramp"`: the engine sizes one straight ramp from the
/// tunnel law and names its tags; the shape lands the same way.
extension PatchEditModel {
    /// What the map inserts: the menu item, the undo step, the wire kind.
    @MainActor enum InsertKind {
        case square, tunnelRamp

        var title: String {
            self == .square ? TileContextMenu.insertShapeTitle : TileContextMenu.insertTunnelRampTitle
        }
        var undoName: String { self == .square ? "Insert Shape" : "Insert Tunnel Ramp" }
        var wire: String? { self == .square ? nil : "tunnel_ramp" }
    }

    /// How long a pending plan waits before it is asked again, and how
    /// many times (the Qt app's `PENDING_MS` / `MAX_TRIES`).
    static let insertPendingNanoseconds: UInt64 = 400_000_000
    static let insertMaxTries = 20

    /// Whether the engine has the commands (protocol 1.20).
    var canInsertShape: Bool {
        O4ProtocolVersion.supportsInsertShape(build?.protocolHello?.protocolVersion ?? "")
    }

    /// Whether the engine sizes a tunnel ramp (protocol 1.24).
    var canInsertTunnelRamp: Bool {
        O4ProtocolVersion.supportsInsertTunnelRamp(build?.protocolHello?.protocolVersion ?? "")
    }

    func insertShape(lat: Double, lon: Double, kind: InsertKind = .square) {
        guard let build, let client = build.patchEditorClient() else { return }
        let coord = BuildModel.TileCoord(lat: Int(floor(lat)), lon: Int(floor(lon)))
        let buildDir = build.tileFolder(coord)?.path
        Task { @MainActor [weak self] in
            do {
                var plan = try await client.patchInsertShape(lat: lat, lon: lon, buildDir: buildDir,
                                                             kind: kind.wire)
                var tries = 1
                while plan.pending {
                    guard tries < Self.insertMaxTries else {
                        Self.notifyInsert("The elevation there is still loading; try \(kind.title) again.",
                                          title: kind.title)
                        return
                    }
                    try await Task.sleep(nanoseconds: Self.insertPendingNanoseconds)
                    plan = try await client.patchInsertShape(lat: lat, lon: lon, buildDir: buildDir,
                                                             kind: kind.wire)
                    tries += 1
                }
                guard let self, let tile = plan.tile, let icao = plan.icao, let corners = plan.corners
                else { return }
                let tags = plan.tags ?? [:]
                if let doc = self.document, doc.tile == tile, doc.icao == icao {
                    self.addShape(corners, tags: tags, name: kind.undoName)
                } else {
                    let reply = try await client.patchAddShape(tile: tile, icao: icao, corners: corners,
                                                               tags: tags)
                    self.relist(tile: tile)
                    Self.notifyInsert(reply.message, title: kind.title)
                }
            } catch {
                Self.notifyInsert("\(error)", title: kind.title)
            }
        }
    }

    /// The planned corners into the open document: one step, then Edit
    /// mode with the new shape selected.
    func addShape(_ corners: [[Double]], tags: [String: String] = [:], name: String = "Insert Shape") {
        let ring = corners.map { (lat: $0[0], lon: $0[1], alt: $0.count > 2 ? Optional($0[2]) : nil) }
        var wayID: Int64?
        if perform(name, { wayID = try $0.addShape(ring, tags: tags) }), let wayID {
            mode = .edit
            selectShapes([wayID])
        }
    }

    private static func notifyInsert(_ text: String, title: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = text
        alert.runModal()
    }
}
