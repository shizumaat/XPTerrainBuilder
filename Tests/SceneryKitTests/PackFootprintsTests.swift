import Testing
import Foundation
@testable import SceneryKit

/// The map's building footprints (`PackFootprints`) and the one shared
/// `pack_objects` answer (`PackBuildingsStore`) — patch-editor spec §2 as
/// amended before L4, §4.
struct PackFootprintsTests {

    private func objects(heading: Double) throws -> O4PackObjects {
        // A 10 m (x) × 4 m (z) box, authored x east / z south from the anchor
        // at x ∈ [0, 10], z ∈ [-4, 0]; one interior point the hull drops.
        let v: [Float] = [0, 0, 0, 10, 0, 0, 10, 6, -4, 0, 6, -4, 5, 3, -2]
        let b64 = v.withUnsafeBufferPointer { Data(buffer: $0) }.base64EncodedString()
        let json = """
        {"models": [{"key": "m.obj", "vertices_f32_b64": "\(b64)", "triangles_u32_b64": ""}],
         "placements": [{"model": "m.obj", "lat": 45.0, "lon": -122.0, "heading_deg": \(heading), "agl_m": 0},
                        {"model": "gone.obj", "lat": 45.0, "lon": -122.0, "heading_deg": 0, "agl_m": 0}],
         "facades": [{"ring": [[45.1, -122.1], [45.1, -122.09], [45.11, -122.09]], "height_m": 8}],
         "missing": []}
        """
        return try JSONDecoder().decode(O4PackObjects.self, from: Data(json.utf8))
    }

    /// Metres east / north of the anchor.
    private func metres(_ p: O4LatLon) -> (Double, Double) {
        let mLat = PatchLocalFrame.metresPerDegreeLat
        return ((p.lon + 122.0) * mLat * cos(45.0 * .pi / 180), (p.lat - 45.0) * mLat)
    }

    private func near(_ a: (Double, Double), _ b: (Double, Double)) -> Bool {
        abs(a.0 - b.0) < 1e-3 && abs(a.1 - b.1) < 1e-3
    }

    @Test func rotatedPlacementOutline() throws {
        let rings = PackFootprints.outlines(try objects(heading: 90))
        #expect(rings.count == 2)                     // the placement + the facade; unknown model skipped
        let corners = rings[0].map(metres)
        #expect(corners.count == 4)                   // the interior point is not on the hull
        // Heading 90 turns the model's forward (−z, north) to the east:
        // authored (10, 0) lies 10 m south, (0, −4) 4 m east, (10, −4) both.
        for expected in [(0.0, 0.0), (0.0, -10.0), (4.0, 0.0), (4.0, -10.0)] {
            #expect(corners.contains { near($0, expected) }, "missing corner \(expected)")
        }
        #expect(rings[1].count == 3 && rings[1][0] == O4LatLon(lat: 45.1, lon: -122.1))
    }

    @Test func headingZeroKeepsTheAuthoredPlan() throws {
        let corners = PackFootprints.outlines(try objects(heading: 0))[0].map(metres)
        for expected in [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)] {
            #expect(corners.contains { near($0, expected) }, "missing corner \(expected)")
        }
    }

    @Test @MainActor func oneRequestServesTwoConsumers() async throws {
        let store = PackBuildingsStore()
        let calls = Counter()
        let answer = try objects(heading: 0)
        let fetch: PackBuildingsStore.Fetch = { _ in
            await calls.bump()
            try await Task.sleep(nanoseconds: 20_000_000)
            return answer
        }
        let big = O4LatLonBox(minLat: 44.9, minLon: -122.1, maxLat: 45.1, maxLon: -121.9)
        let inner = O4LatLonBox(minLat: 44.95, minLon: -122.05, maxLat: 45.05, maxLon: -121.95)
        // the 3D window and the map ask at once; the map's box lies inside
        async let window = store.objects(tile: "+45-123", icao: "zzzz", box: big, fetch: fetch)
        async let map = store.objects(tile: "+45-123", icao: "ZZZZ", box: inner, fetch: fetch)
        let (a, b) = try await (window, map)
        #expect(a == b)
        #expect(await calls.read() == 1)
        // answered: asked again, still one request; another airport is a new one
        _ = try await store.objects(tile: "+45-123", icao: "ZZZZ", box: big, fetch: fetch)
        #expect(await calls.read() == 1)
        _ = try await store.objects(tile: "+45-123", icao: "YYYY", box: big, fetch: fetch)
        #expect(await calls.read() == 2)
        // a rebuilt tile asks again
        store.invalidate(tile: "+45-123")
        _ = try await store.objects(tile: "+45-123", icao: "ZZZZ", box: inner, fetch: fetch)
        #expect(await calls.read() == 3)
    }

    @Test @MainActor func aFailedRequestIsRetried() async throws {
        let store = PackBuildingsStore()
        let calls = Counter()
        let answer = try objects(heading: 0)
        let box = O4LatLonBox(minLat: 44.9, minLon: -122.1, maxLat: 45.1, maxLon: -121.9)
        await #expect(throws: O4CommandError("engine stopped")) {
            try await store.objects(tile: "+45-123", icao: "ZZZZ", box: box) { _ in
                await calls.bump(); throw O4CommandError("engine stopped")
            }
        }
        let again = try await store.objects(tile: "+45-123", icao: "ZZZZ", box: box) { _ in
            await calls.bump(); return answer
        }
        let n = await calls.value
        #expect(again == answer && n == 2)
    }
}

private actor Counter {
    private(set) var value = 0
    func bump() { value += 1 }
    func read() -> Int { value }
}
