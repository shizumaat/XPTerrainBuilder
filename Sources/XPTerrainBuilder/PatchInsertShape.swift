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
/// written.
extension PatchEditModel {
    /// How long a pending plan waits before it is asked again, and how
    /// many times (the Qt app's `PENDING_MS` / `MAX_TRIES`).
    static let insertPendingNanoseconds: UInt64 = 400_000_000
    static let insertMaxTries = 20

    /// Whether the engine has the commands (protocol 1.20).
    var canInsertShape: Bool {
        O4ProtocolVersion.supportsInsertShape(build?.protocolHello?.protocolVersion ?? "")
    }

    func insertShape(lat: Double, lon: Double) {
        guard let build, let client = build.patchEditorClient() else { return }
        let coord = BuildModel.TileCoord(lat: Int(floor(lat)), lon: Int(floor(lon)))
        let buildDir = build.tileFolder(coord)?.path
        Task { @MainActor [weak self] in
            do {
                var plan = try await client.patchInsertShape(lat: lat, lon: lon, buildDir: buildDir)
                var tries = 1
                while plan.pending {
                    guard tries < Self.insertMaxTries else {
                        Self.notifyInsert("The elevation there is still loading; try Insert shape again.")
                        return
                    }
                    try await Task.sleep(nanoseconds: Self.insertPendingNanoseconds)
                    plan = try await client.patchInsertShape(lat: lat, lon: lon, buildDir: buildDir)
                    tries += 1
                }
                guard let self, let tile = plan.tile, let icao = plan.icao, let corners = plan.corners
                else { return }
                if let doc = self.document, doc.tile == tile, doc.icao == icao {
                    self.addShape(corners)
                } else {
                    let reply = try await client.patchAddShape(tile: tile, icao: icao, corners: corners)
                    self.relist(tile: tile)
                    Self.notifyInsert(reply.message)
                }
            } catch {
                Self.notifyInsert("\(error)")
            }
        }
    }

    /// The planned corners into the open document: one step, then Edit
    /// mode with the new shape selected.
    func addShape(_ corners: [[Double]]) {
        let ring = corners.map { (lat: $0[0], lon: $0[1], alt: $0.count > 2 ? Optional($0[2]) : nil) }
        var wayID: Int64?
        if perform("Insert Shape", { wayID = try $0.addShape(ring) }), let wayID {
            mode = .edit
            selectShapes([wayID])
        }
    }

    private static func notifyInsert(_ text: String) {
        let alert = NSAlert()
        alert.messageText = TileContextMenu.insertShapeTitle
        alert.informativeText = text
        alert.runModal()
    }
}
