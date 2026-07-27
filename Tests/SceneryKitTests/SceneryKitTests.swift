import Testing
import Foundation
@testable import SceneryKit

@Suite struct SceneryKitTests {

    var fixtureRoot: URL {
        guard let url = Bundle.module.url(forResource: "Fixtures/FakeXP", withExtension: nil) else {
            fatalError("FakeXP fixture missing from test bundle")
        }
        return url
    }

    func scannedInstallation() -> Installation {
        InstallationScanner(root: fixtureRoot).scan()
    }

    // MARK: Installation scanning

    @Test func scannerFindsPacksAndLibrary() {
        let installation = scannedInstallation()
        #expect(installation.packs.count == 3)
        let library = installation.packs.first { $0.name == "OpenSceneryX" }
        #expect(library?.isLibrary == true)
    }

    @Test func aptDatParsing() {
        let installation = scannedInstallation()
        let demo = installation.packs.first { $0.name == "KSEA Demo Airport" }
        #expect(demo?.airports["KSEA"]?.name == "Seattle Tacoma Intl")
        // Position from the runway row (no datum rows in the fixture).
        #expect(abs((demo?.airports["KSEA"]?.latitude ?? 0) - 47.46) < 0.01)
        #expect(abs((demo?.airports["KSEA"]?.longitude ?? 0) - (-122.30)) < 0.01)
        #expect(demo?.iniIndex == 0)
        #expect(demo?.isEnabled == true)
    }

    @Test func packKindIsContentFirst() {
        func pack(_ name: String, overlay: Bool?, terrain: Bool = false,
                  photo: Bool = false) -> SceneryPack {
            SceneryPack(name: name, url: URL(fileURLWithPath: "/tmp/\(name)"),
                        status: .enabled, iniIndex: 0, isLibrary: false, airports: [:],
                        tiles: ["+36-002"], isOverlay: overlay, isLaminar: false,
                        signature: "", hasTerrain: terrain, isPhotoTextured: photo)
        }
        // z_SpainUHDv2: ortho tiles with no "ortho" in the name, photo .dds
        // beside each .ter in terrain/, and (until 7z support) an unreadable
        // sample DSF — content must classify it, not the name.
        #expect(pack("z_SpainUHDv2_+36-002", overlay: nil, terrain: true, photo: true).kind == .ortho)
        #expect(pack("z_SpainUHDv2_+36-002", overlay: false, terrain: true, photo: true).kind == .ortho)
        // Elevation mesh: .ter but only a handful of textures.
        #expect(pack("UHD Mesh Scenery v4", overlay: false, terrain: true).kind == .mesh)
        // Name breaks the tie for small ortho tile packs.
        #expect(pack("zOrtho4XP_+41-073", overlay: false, terrain: true).kind == .ortho)
        // Overlays without terrain are landmarks; base mesh without .ter is mesh.
        #expect(pack("SFD Golden Gate", overlay: true).kind == .landmark)
        #expect(pack("Some Base", overlay: false).kind == .mesh)
        // Unknown overlay flag, no content signals: name hint or landmark.
        #expect(pack("Some Mesh Pack", overlay: nil).kind == .mesh)
        #expect(pack("Mystery Overlay", overlay: nil).kind == .landmark)
    }

    // MARK: Map marks

    @Test func packMarkersOnlyPinSingleAirportPacks() {
        func pack(_ name: String, airports: [String: AirportInfo],
                  tiles: Set<String>) -> SceneryPack {
            SceneryPack(name: name, url: URL(fileURLWithPath: "/tmp/\(name)"),
                        status: .enabled, iniIndex: 0, isLibrary: false,
                        airports: airports, tiles: tiles, isOverlay: true,
                        isLaminar: false, signature: "")
        }
        let one = AirportInfo(name: "One", latitude: 47.5, longitude: -122.3)
        let two = AirportInfo(name: "Two", latitude: 10, longitude: 20)

        let markers = InstallationScanner.packMarkers(for: [
            pack("Single", airports: ["KSEA": one], tiles: ["+47-123"]),
            // Two airports, or coverage beyond one tile: the map's own
            // tile centroid stays authoritative.
            pack("Pair", airports: ["KSEA": one, "KBFI": two], tiles: ["+47-123"]),
            pack("Sprawling", airports: ["KSEA": one], tiles: ["+47-123", "+48-123"]),
            // A placeholder 0/0 position is not a pin.
            pack("Unplaced", airports: ["ZZZZ": AirportInfo(name: "Z", latitude: 0, longitude: 0)],
                 tiles: []),
            pack("NoAirport", airports: [:], tiles: ["+47-123"]),
        ])

        #expect(markers.map { $0.packName } == ["Single"])
        #expect(markers.first?.point == GeoPoint(lon: -122.3, lat: 47.5))
    }
}
